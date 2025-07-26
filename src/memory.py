"""
 Memory Manager for the pizzeria chatbot.
Implements hybrid approach: key context + recent messages with intelligent cleanup.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from config import supabase

logger = logging.getLogger(__name__)


class ConversationContext:
    """Represents the context of a conversation with intelligent data management."""
    
    def __init__(self, thread_id: str):
        self.thread_id = thread_id
        self.customer_context: Dict[str, Any] = {}
        self.recent_messages: List[Dict[str, Any]] = []
        self.session_metadata: Dict[str, Any] = {}
        self.last_activity = datetime.now(timezone.utc)
        self.created_at = datetime.now(timezone.utc)
    
    def add_message(self, message: BaseMessage):
        """Add a message to recent messages with intelligent size management."""
        message_data = {
            "role": "human" if isinstance(message, HumanMessage) else "assistant",
            "content": message.content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        self.recent_messages.append(message_data)
        self.last_activity = datetime.now(timezone.utc)
        
        # Keep only the most recent messages (sliding window)
        max_messages = 12
        if len(self.recent_messages) > max_messages:
            # Remove oldest messages but keep the first message if it's important
            if len(self.recent_messages) > max_messages + 2:
                self.recent_messages = self.recent_messages[-max_messages:]
    
    def update_customer_context(self, key: str, value: Any):
        """Update customer context with key information."""
        self.customer_context[key] = value
        self.last_activity = datetime.now(timezone.utc)
    
    def get_messages_for_llm(self) -> List[BaseMessage]:
        """Convert recent messages back to LangChain format."""
        messages = []
        for msg_data in self.recent_messages:
            if msg_data["role"] == "human":
                pass
                messages.append(HumanMessage(content=msg_data["content"]))
            else:
                messages.append(AIMessage(content=msg_data["content"]))
        return messages
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for storage."""
        return {
            "thread_id": self.thread_id,
            "customer_context": self.customer_context,
            "recent_messages": self.recent_messages,
            "session_metadata": self.session_metadata,
            "last_activity": self.last_activity.isoformat(),
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationContext':
        """Deserialize context from storage."""
        context = cls(data["thread_id"])
        context.customer_context = data.get("customer_context", {})
        context.recent_messages = data.get("recent_messages", [])
        context.session_metadata = data.get("session_metadata", {})
        
        if "last_activity" in data:
            context.last_activity = datetime.fromisoformat(data["last_activity"].replace('Z', '+00:00'))
        if "created_at" in data:
            context.created_at = datetime.fromisoformat(data["created_at"].replace('Z', '+00:00'))
        
        return context


class MemoryManager:
    """
    Intelligent memory manager for multi-user conversations.
    Uses hybrid approach with Supabase for persistent storage.
    """
    
    def __init__(self):
        self.table_name = "smart_conversation_memory"
        self.ttl_days = 7  # Auto-cleanup after 7 days of inactivity
        self.max_message_length = 1000  # Truncate very long messages
        
        # In-memory cache for active conversations (optional optimization)
        self._cache: Dict[str, ConversationContext] = {}
        self._cache_ttl = timedelta(minutes=30)
    
    async def get_conversation(self, thread_id: str) -> ConversationContext:
        """
        Get conversation context. Creates new if doesn't exist.
        """
        try:
            # Check cache first
            if thread_id in self._cache:
                cached_context = self._cache[thread_id]
                # Check if cache is still valid
                if datetime.now(timezone.utc) - cached_context.last_activity < self._cache_ttl:
                    logger.info(f"Retrieved conversation from cache: {thread_id}")
                    return cached_context
                else:
                    # Cache expired
                    del self._cache[thread_id]
            
            # Load from database
            result = supabase.table(self.table_name).select("*").eq("thread_id", thread_id).limit(1).execute()
            
            if result.data:
                # Found existing conversation
                context = ConversationContext.from_dict(result.data[0])
                self._cache[thread_id] = context
                logger.info(f"Loaded conversation from DB: {thread_id}, {len(context.recent_messages)} messages")
                return context
            else:
                # Create new conversation
                context = ConversationContext(thread_id)
                logger.info(f"Created new conversation: {thread_id}")
                return context
                
        except Exception as e:
            logger.error(f"Error getting conversation {thread_id}: {e}")
            # Return empty context on error
            return ConversationContext(thread_id)
    
    async def save_conversation(self, context: ConversationContext):
        """
        Save conversation context to database.
        """
        try:
            # Update cache
            self._cache[context.thread_id] = context
            
            # Prepare data for storage
            data = context.to_dict()
            
            # Upsert to database
            result = supabase.table(self.table_name).upsert(
                data, 
                on_conflict="thread_id"
            ).execute()
            
            if result.data:
                logger.info(f"Saved conversation: {context.thread_id}, {len(context.recent_messages)} messages")
            else:
                logger.warning(f"Failed to save conversation: {context.thread_id}")
                
        except Exception as e:
            logger.error(f"Error saving conversation {context.thread_id}: {e}")
    
    async def add_message(self, thread_id: str, message: BaseMessage) -> ConversationContext:
        """
        Add a message to the conversation and save.
        """
        context = await self.get_conversation(thread_id)
        
        # Truncate very long messages to save space
        if len(message.content) > self.max_message_length:
            original_content = message.content
            message.content = message.content[:self.max_message_length] + "... [truncated]"
            logger.info(f"Truncated long message for {thread_id}: {len(original_content)} -> {len(message.content)}")
        
        context.add_message(message)
        await self.save_conversation(context)
        
        return context
    
    async def update_customer_context(self, thread_id: str, key: str, value: Any):
        """
        Update customer context information.
        """
        context = await self.get_conversation(thread_id)
        context.update_customer_context(key, value)
        await self.save_conversation(context)
        
        logger.info(f"Updated customer context for {thread_id}: {key} = {value}")
    
    async def cleanup_old_conversations(self):
        """
        Clean up conversations older than TTL.
        This should be run periodically (e.g., daily cron job).
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)
            
            result = supabase.table(self.table_name).delete().lt(
                "last_activity", 
                cutoff_date.isoformat()
            ).execute()
            
            if result.data:
                cleaned_count = len(result.data)
                logger.info(f"Cleaned up {cleaned_count} old conversations")
                return cleaned_count
            else:
                logger.info("No old conversations to clean up")
                return 0
                
        except Exception as e:
            logger.error(f"Error cleaning up old conversations: {e}")
            return 0
    
    def clear_cache(self):
        """Clear the in-memory cache."""
        self._cache.clear()
        logger.info("Memory cache cleared")
    
    async def get_conversation_stats(self, thread_id: str) -> Dict[str, Any]:
        """
        Get statistics about a conversation.
        """
        context = await self.get_conversation(thread_id)
        
        return {
            "thread_id": thread_id,
            "message_count": len(context.recent_messages),
            "customer_context_keys": list(context.customer_context.keys()),
            "last_activity": context.last_activity.isoformat(),
            "created_at": context.created_at.isoformat(),
            "cache_hit": thread_id in self._cache
        }

    async def clear_user_cache(self, user_id: str) -> bool:
        """
        🧹 CLEAR ALL CACHED DATA FOR A SPECIFIC USER
        
        This function completely removes:
        - All conversation history
        - Customer context 
        - Session metadata
        - Order states
        - Any other cached information
        
        Use this when a user wants to start completely fresh.
        """
        try:
            logger.info(f"🧹 CLEARING ALL CACHE FOR USER: {user_id}")
            
            # 1. Clear from conversations table
            result1 = supabase.table("conversations").delete().eq("thread_id", user_id).execute()
            logger.info(f"   ✅ Conversations cleared: {len(result1.data) if result1.data else 0} records")
            
            # 2. Clear from any other related tables (adjust table names as needed)
            try:
                # Clear customer data cache if separate table exists
                result2 = supabase.table("customer_cache").delete().eq("user_id", user_id).execute()
                logger.info(f"   ✅ Customer cache cleared: {len(result2.data) if result2.data else 0} records")
            except Exception as e:
                logger.info(f"   ℹ️  No customer_cache table or already clean: {e}")
            
            try:
                # Clear order states cache if separate table exists  
                result3 = supabase.table("order_states_cache").delete().eq("user_id", user_id).execute()
                logger.info(f"   ✅ Order states cache cleared: {len(result3.data) if result3.data else 0} records")
            except Exception as e:
                logger.info(f"   ℹ️  No order_states_cache table or already clean: {e}")
            
            # 3. Clear from memory cache
            if user_id in self._cache:
                del self._cache[user_id]
                logger.info(f"   ✅ In-memory cache cleared for user")
            
            logger.info(f"🎉 CACHE COMPLETELY CLEARED for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error clearing cache for user {user_id}: {e}")
            return False
    
    async def clear_all_cache(self) -> dict:
        """
        🧹 CLEAR ALL CACHED DATA FOR ALL USERS (ADMIN FUNCTION)
        
        WARNING: This removes ALL conversation data for ALL users.
        Use only for maintenance or testing.
        """
        try:
            logger.warning("🧹 CLEARING ALL CACHE FOR ALL USERS - ADMIN OPERATION")
            
            results = {}
            
            # Clear conversations table
            result1 = supabase.table("conversations").delete().neq("id", "impossible_id").execute()
            results["conversations"] = len(result1.data) if result1.data else 0
            
            # Clear other cache tables
            for table_name in ["customer_cache", "order_states_cache"]:
                try:
                    result = supabase.table(table_name).delete().neq("id", "impossible_id").execute()
                    results[table_name] = len(result.data) if result.data else 0
                except Exception as e:
                    results[table_name] = f"Table not found or error: {e}"
            
            # Clear in-memory cache
            self._cache.clear()
            results["memory_cache"] = "cleared"
            
            logger.warning(f"🎉 ALL CACHE CLEARED - Results: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error clearing all cache: {e}")
            return {"error": str(e)}
    
    async def get_user_cache_info(self, user_id: str) -> dict:
        """
        📊 GET INFORMATION ABOUT CACHED DATA FOR A USER
        
        Useful for debugging and understanding what's stored.
        """
        try:
            info = {
                "user_id": user_id,
                "conversation_exists": user_id in self._cache,
                "database_records": 0,
                "message_count": 0,
                "last_activity": None,
                "cache_size_estimate": "0 KB"
            }
            
            # Check database
            result = supabase.table("conversations").select("*").eq("thread_id", user_id).execute()
            if result.data:
                info["database_records"] = len(result.data)
                if result.data[0].get("data"):
                    conversation_data = json.loads(result.data[0]["data"])
                    info["message_count"] = len(conversation_data.get("recent_messages", []))
                    info["last_activity"] = conversation_data.get("last_activity")
                    
                    # Estimate cache size
                    data_str = json.dumps(conversation_data)
                    size_bytes = len(data_str.encode('utf-8'))
                    info["cache_size_estimate"] = f"{size_bytes / 1024:.1f} KB"
            
            # Check memory
            if user_id in self._cache:
                context = self._cache[user_id]
                info["memory_message_count"] = len(context.recent_messages)
                info["memory_last_activity"] = context.last_activity.isoformat()
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting cache info for user {user_id}: {e}")
            return {"error": str(e)}


# Global instance
memory = MemoryManager() 
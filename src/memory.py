"""
Memory Manager for the pizzeria chatbot.
Implements hybrid approach: key context + recent messages with intelligent cleanup.
Uses smart_conversation_memory table from Supabase schema.
"""

import json
import logging
import os
# Importar el cliente de Supabase desde config centralizado
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

sys.path.append('..')
try:
    from config import supabase
    SUPABASE_AVAILABLE = True
except ImportError:
    supabase = None
    SUPABASE_AVAILABLE = False
    print("Warning: Could not import supabase from config, using mock for memory")

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
                messages.append(HumanMessage(content=msg_data["content"]))
            else:
                messages.append(AIMessage(content=msg_data["content"]))
        return messages
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize context for storage in smart_conversation_memory table."""
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
        """Deserialize context from smart_conversation_memory table."""
        context = cls(data["thread_id"])
        context.customer_context = data.get("customer_context", {})
        context.recent_messages = data.get("recent_messages", [])
        context.session_metadata = data.get("session_metadata", {})
        
        if "last_activity" in data:
            try:
                # Handle different datetime formats
                last_activity_str = data["last_activity"]
                if isinstance(last_activity_str, str):
                    if last_activity_str.endswith('Z'):
                        last_activity_str = last_activity_str.replace('Z', '+00:00')
                    context.last_activity = datetime.fromisoformat(last_activity_str)
                elif isinstance(last_activity_str, datetime):
                    context.last_activity = last_activity_str
            except Exception as e:
                logger.warning(f"Error parsing last_activity: {e}")
                context.last_activity = datetime.now(timezone.utc)
                
        if "created_at" in data:
            try:
                created_at_str = data["created_at"]
                if isinstance(created_at_str, str):
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                    context.created_at = datetime.fromisoformat(created_at_str)
                elif isinstance(created_at_str, datetime):
                    context.created_at = created_at_str
            except Exception as e:
                logger.warning(f"Error parsing created_at: {e}")
                context.created_at = datetime.now(timezone.utc)
        
        return context


class MemoryManager:
    """
    Intelligent memory manager for multi-user conversations.
    Uses smart_conversation_memory table for persistent storage.
    """
    
    def __init__(self):
        self.table_name = "smart_conversation_memory"  # Usar tabla del esquema real
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
            
            # Load from database if available
            if SUPABASE_AVAILABLE and supabase:
                result = supabase.table(self.table_name).select("*").eq("thread_id", thread_id).limit(1).execute()
                
                if result.data:
                    # Found existing conversation
                    context = ConversationContext.from_dict(result.data[0])
                    self._cache[thread_id] = context
                    logger.info(f"Loaded conversation from DB: {thread_id}, {len(context.recent_messages)} messages")
                    return context
            
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
        Save conversation context to smart_conversation_memory table.
        """
        try:
            # Update cache
            self._cache[context.thread_id] = context
            
            # Save to database if available
            if SUPABASE_AVAILABLE and supabase:
                # Prepare data for storage in smart_conversation_memory format
                data = {
                    "thread_id": context.thread_id,
                    "customer_context": context.customer_context,
                    "recent_messages": context.recent_messages,
                    "session_metadata": context.session_metadata,
                    "last_activity": context.last_activity.isoformat(),
                    "created_at": context.created_at.isoformat()
                }
                
                # Upsert to database
                result = supabase.table(self.table_name).upsert(
                    data, 
                    on_conflict="thread_id"
                ).execute()
                
                if result.data:
                    logger.info(f"Saved conversation: {context.thread_id}, {len(context.recent_messages)} messages")
                else:
                    logger.warning(f"Failed to save conversation: {context.thread_id}")
            else:
                logger.info(f"Saved conversation to cache only: {context.thread_id}")
                
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
            if not SUPABASE_AVAILABLE or not supabase:
                return 0
                
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


# Global instance
memory_manager = MemoryManager()

# Backward compatibility
memory = memory_manager 
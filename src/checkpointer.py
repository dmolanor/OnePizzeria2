"""
 Checkpointer for LangGraph using the hybrid memory approach.
Much more efficient than the original checkpointer.
"""

import logging
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (BaseCheckpointSaver, Checkpoint,
                                       CheckpointMetadata)

from .memory import ConversationContext, memory
from .state import ChatState

logger = logging.getLogger(__name__)


class Checkpointer(BaseCheckpointSaver):
    """
    Optimized checkpointer using MemoryManager.
    
    This checkpointer is much more efficient than the original because:
    1. Only stores essential conversation data
    2. Uses intelligent sliding window for messages
    3. Has built-in caching for active conversations
    4. Auto-cleanup of old conversations
    """
    
    def __init__(self):
        super().__init__()
        self.memory_manager = memory
        logger.info("Checkpointer initialized")
    
    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """
        Load checkpoint from  memory.
        """
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                logger.warning("No thread_id provided in config")
                return None
            
            # Note: We can't use async here due to LangGraph interface
            # In practice, we'll handle this in the graph nodes directly
            logger.info(f"Checkpoint requested for thread_id: {thread_id}")
            return None  # We'll handle state loading in graph nodes
            
        except Exception as e:
            logger.error(f"Error getting checkpoint: {e}")
            return None
    
    async def aget(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """
        Async version of get checkpoint.
        """
        return self.get(config)
    
    def get_tuple(self, config: RunnableConfig) -> Optional[Tuple[Checkpoint, CheckpointMetadata]]:
        """
        Get checkpoint with metadata.
        """
        checkpoint = self.get(config)
        if checkpoint:
            thread_id = config.get("configurable", {}).get("thread_id", "unknown")
            metadata = self._create_metadata(thread_id)
            return (checkpoint, metadata)
        return None
    
    async def aget_tuple(self, config: RunnableConfig) -> Optional[Tuple[Checkpoint, CheckpointMetadata]]:
        """
        Async version of get_tuple.
        """
        return self.get_tuple(config)
    
    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> CheckpointMetadata:
        """
        Save checkpoint to  memory.
        """
        try:
            thread_id = config.get("configurable", {}).get("thread_id")
            if not thread_id:
                logger.warning("No thread_id provided in config")
                return self._create_metadata(thread_id or "unknown")
            
            logger.info(f"Checkpoint saved for thread_id: {thread_id}")
            
            # We'll handle the actual saving in the graph nodes
            # This is just for LangGraph compliance
            return self._create_metadata(thread_id)
            
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
            return self._create_metadata(thread_id or "unknown")
    
    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint) -> CheckpointMetadata:
        """
        Async version of put checkpoint.
        """
        return self.put(config, checkpoint)
    
    def list(self, config: RunnableConfig, **kwargs) -> Iterator[CheckpointMetadata]:
        """
        List checkpoints (for LangGraph compatibility).
        """
        thread_id = config.get("configurable", {}).get("thread_id")
        if thread_id:
            yield self._create_metadata(thread_id)
    
    def _create_metadata(self, thread_id: str) -> CheckpointMetadata:
        """Create checkpoint metadata."""
        return CheckpointMetadata(
            source_id=thread_id,
            source_type="user"
        )


class ChatStateManager:
    """
    Manager for ChatState that integrates with MemoryManager.
    This handles the conversion between LangGraph state and our  memory.
    """
    
    def __init__(self):
        self.memory_manager = memory
    
    async def load_state_for_user(self, user_id: str, new_message: str) -> ChatState:
        """
        Load complete chat state for a user including memory.
        """
        try:
            # Get conversation context from  memory
            context = await self.memory_manager.get_conversation(user_id)
            
            # Get customer data from database
            try:
                from .tools import get_customer
                customer = get_customer.invoke({"user_id": user_id})
            except (ImportError, Exception) as e:
                print(f"Warning: Could not get customer data: {e}")
                customer = None
            
            # Get active order if exists
            try:
                from .tools import get_active_order
                active_order = get_active_order.invoke({"user_id": user_id})
            except (ImportError, Exception) as e:
                print(f"Warning: Could not get active order: {e}")
                active_order = None
            
            # Build the ChatState
            from langchain_core.messages import HumanMessage

            from .state import ChatState

            # Get conversation history as LangChain messages
            historical_messages = context.get_messages_for_llm()
            
            # Add the new message
            #new_human_message = HumanMessage(content=new_message)
            #all_messages = historical_messages + [new_human_message]
            all_messages = historical_messages
            
            # Determine current step and flags
            needs_customer_info = not customer or not customer.get("last_name")
            ready_to_order = bool(customer and customer.get("last_name"))
            
            # Determine current step based on context
            current_step = self._determine_current_step(context, new_message, needs_customer_info)
            
            state = ChatState(
                user_id=user_id,
                messages=all_messages,
                customer=customer,
                current_step=current_step,
                active_order=active_order,
                needs_customer_info=needs_customer_info,
                ready_to_order=ready_to_order
            )
            
            logger.info(f"Loaded state for {user_id}: {len(all_messages)} messages, step: {current_step}")
            return state
            
        except Exception as e:
            logger.error(f"Error loading state for {user_id}: {e}")
            # Return minimal state on error
            from langchain_core.messages import HumanMessage

            from .state import ChatState
            
            return ChatState(
                user_id=user_id,
                #messages=[HumanMessage(content=new_message)],
                customer={},
                current_step="greeting",
                active_order={},
                needs_customer_info=True,
                ready_to_order=False
            )
    
    async def save_state_for_user(self, state: ChatState, ai_response):
        """
        Save chat state to  memory.
        """
        try:
            user_id = state["user_id"]
            
            # Save the AI response to conversation memory
            from langchain_core.messages import AIMessage
            ai_message = AIMessage(content=ai_response)
            
            # Add both human message and AI response
            if state["messages"]:
                # Add the human message (last one in state)
                human_message = state["messages"][-1]
                await self.memory_manager.add_message(user_id, human_message)
            
            # Add the AI response
            await self.memory_manager.add_message(user_id, ai_message)
            
            # Update customer context if we have relevant info
            if state.get("customer") and state["customer"].get("first_name"):
                await self.memory_manager.update_customer_context(
                    user_id, 
                    "customer_name", 
                    f"{state['customer'].get('first_name', '')} {state['customer'].get('last_name', '')}"
                )
            
            # Update order context if we have an active order
            if state.get("active_order") and state["active_order"]:
                await self.memory_manager.update_customer_context(
                    user_id,
                    "current_order",
                    state["active_order"]
                )
            
            logger.info(f"Saved state for {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving state for {user_id}: {e}")
    
    def _determine_current_step(self, context: ConversationContext, new_message: str, needs_customer_info: bool) -> str:
        """
        Determine the current step in the conversation.
        """
        message_lower = new_message.lower()
        
        # Check customer context for clues
        if needs_customer_info:
            return "greeting"
        
        # Check recent conversation for context
        recent_messages = context.recent_messages[-3:] if context.recent_messages else []
        recent_content = " ".join([msg.get("content", "") for msg in recent_messages]).lower()
        
        # Determine step based on message content and recent context
        if any(word in message_lower for word in ["menú", "menu", "pizzas", "precios", "qué tienen"]):
            return "menu"
        elif any(word in message_lower for word in ["ordenar", "pedido", "quiero", "pizza"]):
            return "order"
        elif any(word in recent_content for word in ["pedido", "orden", "pizza"]):
            return "order"
        elif any(word in recent_content for word in ["menú", "menu", "precios"]):
            return "menu"
        else:
            return "general"


# Global instances
checkpointer = Checkpointer()
state_manager = ChatStateManager() 
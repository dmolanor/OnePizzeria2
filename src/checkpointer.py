"""
Simplified checkpointer for LangGraph using hybrid memory approach.
"""

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage, HumanMessage

from .memory import memory
from .models import ChatState

logger = logging.getLogger(__name__)


class ChatStateManager:
    """
    Simplified manager for ChatState that integrates with MemoryManager.
    """
    
    def __init__(self):
        self.memory_manager = memory
    
    async def load_state_for_user(self, user_id: str, new_message: str) -> ChatState:
        """
        Load complete chat state for a user including memory.
        """
        try:
            # Get conversation context from memory
            context = await self.memory_manager.get_conversation(user_id)
            
            # Get historical messages as LangChain messages
            historical_messages = context.get_messages_for_llm()
            
            # Add the new message
            new_human_message = HumanMessage(content=new_message)
            all_messages = historical_messages + [new_human_message]
            
            # Build the simplified ChatState
            state = ChatState(
                user_id=user_id,
                messages=all_messages,
                customer={},  # Will be populated by tools
                active_order={},  # Will be populated by tools
                response=None
            )
            
            logger.info(f"Loaded state for {user_id}: {len(all_messages)} messages")
            return state
            
        except Exception as e:
            logger.error(f"Error loading state for {user_id}: {e}")
            # Return minimal state on error
            return ChatState(
                user_id=user_id,
                messages=[HumanMessage(content=new_message)],
                customer={},
                active_order={},
                response=None
            )
    
    async def save_state_for_user(self, state: ChatState, ai_response: str):
        """
        Save chat state to memory.
        """
        try:
            user_id = state["user_id"]
            
            # Add both human message and AI response to memory
            if state["messages"]:
                # Add the human message (last one in state)
                human_message = state["messages"][-1]
                await self.memory_manager.add_message(user_id, human_message)
            
            # Add the AI response
            ai_message = AIMessage(content=ai_response)
            await self.memory_manager.add_message(user_id, ai_message)
            
            # Update customer context if we have relevant info
            if state.get("customer") and state["customer"]:
                await self.memory_manager.update_customer_context(
                    user_id, 
                    "customer_data", 
                    state["customer"]
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


# Global instance
state_manager = ChatStateManager() 
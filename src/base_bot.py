import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from src.checkpointer import state_manager
from src.memory import memory
from src.workflow import Workflow

logger = logging.getLogger(__name__)

class BaseBot(ABC):
    """
    Base class for all bot implementations (Telegram, WhatsApp, etc.).
    
    This class provides common functionality for:
    - Message processing and workflow integration
    - State management and memory persistence
    - Message grouping and rate limiting
    - Error handling and logging
    """
    
    def __init__(self):
        """Initialize the base bot with common components."""
        self.workflow = Workflow()
        
        # Message grouping mechanism - prevents multiple responses for rapid messages
        self.pending_tasks: Dict[str, asyncio.Task] = {}  # cliente_id -> processing task
        self.pending_messages: Dict[str, List[str]] = {}  # cliente_id -> list of messages
        self.message_delay = 3.0  # seconds to wait for additional messages
        
        # Rate limiting
        self.rate_limiter: Dict[str, float] = {}  # cliente_id -> last_message_time
        self.min_message_interval = 1.0  # seconds between messages per user
        
    @abstractmethod
    async def send_message(self, recipient: str, message: str, **kwargs) -> bool:
        """
        Send a message to a recipient.
        
        Args:
            recipient: The recipient identifier (phone number, chat_id, etc.)
            message: The message content
            **kwargs: Platform-specific parameters
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_typing_action(self, recipient: str) -> bool:
        """
        Send a typing indicator to show the bot is processing.
        
        Args:
            recipient: The recipient identifier
            
        Returns:
            bool: True if action was sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def format_recipient_id(self, raw_id: str) -> str:
        """
        Format the recipient ID according to platform requirements.
        
        Args:
            raw_id: Raw recipient identifier from the platform
            
        Returns:
            str: Formatted recipient identifier
        """
        pass
    
    async def is_rate_limited(self, cliente_id: str) -> bool:
        """
        Check if a user is rate limited.
        
        Args:
            cliente_id: User identifier
            
        Returns:
            bool: True if user is rate limited
        """
        import time
        current_time = time.time()
        last_message_time = self.rate_limiter.get(cliente_id, 0)
        
        if current_time - last_message_time < self.min_message_interval:
            return True
            
        self.rate_limiter[cliente_id] = current_time
        return False
    
    async def process_user_message(self, cliente_id: str, message_text: str, user_name: str = None) -> None:
        """
        Process a user message with grouping and workflow integration.
        
        Args:
            cliente_id: User identifier
            message_text: The message content
            user_name: Optional user name for logging
        """
        try:
            # Check rate limiting
            if await self.is_rate_limited(cliente_id):
                logger.warning(f"Rate limiting user {cliente_id}")
                return
            
            logger.info(f"📥 Received message from {user_name or cliente_id}: {message_text}")
            
            # Cancel any existing processing task for this user
            if cliente_id in self.pending_tasks:
                self.pending_tasks[cliente_id].cancel()
                logger.info(f"⏹️ Cancelled previous processing task for user {cliente_id}")
            
            # Add message to pending messages for this user
            if cliente_id not in self.pending_messages:
                self.pending_messages[cliente_id] = []
            self.pending_messages[cliente_id].append(message_text)
            
            logger.info(f"📋 Total pending messages for {user_name or cliente_id}: {len(self.pending_messages[cliente_id])}")
            
            # Create new delayed processing task
            self.pending_tasks[cliente_id] = asyncio.create_task(
                self._delayed_message_processing(cliente_id, user_name)
            )
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error in process_user_message: {str(e)}")
            logger.error(f"Full traceback:\n{error_traceback}")
            await self.send_error_message(cliente_id, "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo.")
    
    async def _delayed_message_processing(self, cliente_id: str, user_name: str = None) -> None:
        """
        Process messages after a delay, allowing for message grouping.
        
        Args:
            cliente_id: User identifier
            user_name: Optional user name for logging
        """
        try:
            # Wait for the delay period
            await asyncio.sleep(self.message_delay)
            
            # Get all pending messages for this user
            messages = self.pending_messages.get(cliente_id, [])
            if not messages:
                logger.warning(f"No pending messages found for user {cliente_id}")
                return
            
            # Clear pending messages for this user
            self.pending_messages[cliente_id] = []
            
            # Combine multiple messages into one if needed
            if len(messages) == 1:
                combined_message = messages[0]
                logger.info(f"🔄 Processing single message from {user_name or cliente_id}")
            else:
                combined_message = "\n".join(messages)
                logger.info(f"🔄 Processing {len(messages)} grouped messages from {user_name or cliente_id}")
                logger.info(f"📝 Combined message: {combined_message}")
            
            # Send typing indicator
            await self.send_typing_action(cliente_id)
            
            # Process combined message through workflow
            initial_state = await state_manager.load_state_for_user(cliente_id, HumanMessage(combined_message))
            initial_state["messages"] += [HumanMessage(combined_message)]
            
            logger.info("Starting workflow execution...")
            response_state = await self.workflow.workflow.ainvoke(initial_state)
            logger.info(f"Workflow completed. Response state keys: {list(response_state.keys()) if response_state else 'None'}")
            
            # Get the last message from the response state
            if response_state and response_state.get("messages"):
                response = response_state["messages"][-1]
                logger.info(f"Extracted response: {response.content[:100]}..." if len(response.content) > 100 else response.content)
                
                # Send response to user
                success = await self.send_message(cliente_id, response.content)
                if success:
                    logger.info(f"✅ Response sent to {user_name or cliente_id}")
                else:
                    logger.error(f"❌ Failed to send response to {user_name or cliente_id}")
            else:
                await self.send_error_message(
                    cliente_id,
                    "Lo siento, no pude procesar tu mensaje. ¿Podrías intentar de nuevo?"
                )
                logger.warning("No messages found in response state")
            
            # Clean up pending task
            if cliente_id in self.pending_tasks:
                del self.pending_tasks[cliente_id]
                
        except asyncio.CancelledError:
            logger.info(f"⏹️ Message processing cancelled for user {cliente_id}")
            # Don't re-raise CancelledError as it's expected behavior
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error in delayed message processing: {str(e)}")
            logger.error(f"Full traceback:\n{error_traceback}")
            
            await self.send_error_message(
                cliente_id,
                "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
            )
            
            # Clean up on error
            if cliente_id in self.pending_tasks:
                del self.pending_tasks[cliente_id]
            if cliente_id in self.pending_messages:
                self.pending_messages[cliente_id] = []
    
    async def send_error_message(self, recipient: str, error_message: str) -> None:
        """
        Send an error message to the user.
        
        Args:
            recipient: The recipient identifier
            error_message: The error message to send
        """
        try:
            await self.send_message(recipient, error_message)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def clear_user_cache(self, cliente_id: str) -> Dict[str, Any]:
        """
        Clear user cache and return information about what was cleared.
        
        Args:
            cliente_id: User identifier
            
        Returns:
            Dict with cache clearing results
        """
        try:
            # Get cache info before clearing
            cache_info = await memory.get_user_cache_info(cliente_id)
            
            # Clear the cache
            success = await memory.clear_user_cache(cliente_id)
            
            return {
                "success": success,
                "cache_info": cache_info
            }
            
        except Exception as e:
            logger.error(f"Error clearing user cache: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_cache_info(self, cliente_id: str) -> Dict[str, Any]:
        """
        Get information about user's cache.
        
        Args:
            cliente_id: User identifier
            
        Returns:
            Dict with cache information
        """
        try:
            return await memory.get_user_cache_info(cliente_id)
        except Exception as e:
            logger.error(f"Error getting user cache info: {e}")
            return {"error": str(e)}
    
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        logger.info("Stopping bot...")
        
        # Cancel all pending message processing tasks
        if self.pending_tasks:
            logger.info(f"⏹️ Cancelling {len(self.pending_tasks)} pending message tasks...")
            for cliente_id, task in self.pending_tasks.items():
                if not task.cancelled():
                    task.cancel()
                    logger.info(f"   Cancelled task for user {cliente_id}")
            
            # Wait a brief moment for tasks to clean up
            await asyncio.sleep(0.1)
            
            # Clear the dictionaries
            self.pending_tasks.clear()
            self.pending_messages.clear()
            logger.info("✅ All pending tasks cleared")
    
    def get_pending_messages_info(self) -> Dict[str, Any]:
        """
        Get information about pending messages for debugging.
        
        Returns:
            Dictionary with pending tasks and messages information
        """
        return {
            "active_tasks": len(self.pending_tasks),
            "users_with_pending_messages": len(self.pending_messages),
            "total_pending_messages": sum(len(msgs) for msgs in self.pending_messages.values()),
            "message_delay_seconds": self.message_delay,
            "user_details": {
                cliente_id: {
                    "pending_message_count": len(messages),
                    "has_active_task": cliente_id in self.pending_tasks,
                    "task_cancelled": cliente_id in self.pending_tasks and self.pending_tasks[cliente_id].cancelled()
                }
                for cliente_id, messages in self.pending_messages.items() if messages
            }
        }
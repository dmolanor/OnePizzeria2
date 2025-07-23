import logging
import signal
import sys
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from src.state import ChatState
from src.workflow import Workflow

# Set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        """Initialize the bot with the given token."""
        # Enable concurrent updates for better performance
        self.application = (
            Application.builder()
            .token(token)
            .concurrent_updates(True)
            .build()
        )
        self.workflow = Workflow()  # Initialize workflow
        self._setup_handlers()
        self._setup_shutdown_handlers()

    def _setup_handlers(self) -> None:
        """Set up all command and message handlers."""
        # Command handlers with non-blocking execution for better performance
        self.application.add_handler(
            CommandHandler("start", self.start_command, block=False)
        )
        self.application.add_handler(
            CommandHandler("help", self.help_command, block=False)
        )
        
        # Message handler for text messages with non-blocking execution
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, 
                self.handle_message, 
                block=False
            )
        )
        
        # Error handler
        self.application.add_error_handler(self.error_handler)

    def _setup_shutdown_handlers(self) -> None:
        """Set up graceful shutdown handlers."""
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal, stopping bot gracefully...")
            self.application.stop_running()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        user = update.effective_user
        welcome_message = (
            f"¡Hola {user.first_name}! 👋\n\n"
            "Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?\n"
            "Usa /help para ver los comandos disponibles."
        )
        await update.message.reply_text(welcome_message)
        logger.info(f"User {user.id} ({user.first_name}) started the bot")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command."""
        help_text = (
            "Estos son los comandos disponibles:\n\n"
            "/start - Iniciar el bot\n"
            "/help - Mostrar este mensaje de ayuda\n\n"
            "También puedes enviarme cualquier mensaje de texto y te responderé."
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        try:
            # Get the user's message and info
            message_text = update.message.text
            user = update.effective_user
            user_id = str(user.id)  # Convert to string as workflow expects string
            user_name = user.first_name
            
            logger.info(f"Received message from {user_name} ({user_id}): {message_text}")
            
            # Process message through workflow asynchronously
            initial_state = {"messages": [HumanMessage(content=message_text)], "user_id": user_id}
            logger.info(f"Initial state created: {initial_state}")
            
            logger.info("Starting workflow execution...")
            response_state = await self.workflow.workflow.ainvoke(initial_state)
            logger.info(f"Workflow completed. Response state: {response_state}")
            
            # Get the last message from the response state
            if response_state and response_state.get("messages"):
                response = response_state["messages"][-1].content
                logger.info(f"Extracted response: {response}")
            else:
                response = "Lo siento, no pude procesar tu mensaje. ¿Podrías intentar de nuevo?"
                logger.warning("No messages found in response state")
            
            await update.message.reply_text(response)
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error processing message: {str(e)}")
            logger.error(f"Full traceback:\n{error_traceback}")
            await update.message.reply_text(
                "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        error_msg = str(context.error)
        
        # Handle specific error types
        if "Conflict" in error_msg and "getUpdates" in error_msg:
            logger.warning("Bot conflict detected - another instance may be running")
            return
        
        logger.error(f"Update {update} caused error {context.error}")
        
        # Only send error message to user if it's not a conflict error
        if update and update.effective_message and "Conflict" not in error_msg:
            try:
                await update.effective_message.reply_text(
                    "Lo siento, ocurrió un error. Por favor, intenta de nuevo más tarde."
                )
            except Exception as e:
                logger.error(f"Failed to send error message to user: {e}")

    def run_sync(self) -> None:
        """Run the bot synchronously with improved error handling."""
        logger.info("Starting Telegram bot...")
        logger.info("Press Ctrl+C to stop the bot")
        
        try:
            # Clear any existing webhook first
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True  # Clear any pending updates from previous runs
            )
        except Exception as e:
            if "Conflict" in str(e):
                logger.error(
                    "Bot conflict error: Another instance is already running. "
                    "Please make sure only one bot instance is active."
                )
            else:
                logger.error(f"Unexpected error: {e}")
            raise
        
    async def run(self) -> None:
        """Run the bot asynchronously."""
        logger.info("Starting bot asynchronously...")
        await self.application.run_polling(drop_pending_updates=True)
        
    async def stop(self) -> None:
        """Stop the bot gracefully."""
        logger.info("Stopping bot...")
        await self.application.stop()
        logger.info("Bot stopped successfully")

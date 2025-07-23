import logging
from typing import Any, Dict, Optional

from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str):
        """Initialize the bot with the given token."""
        self.application = Application.builder().token(token).build()
        self._setup_handlers()

    def _setup_handlers(self) -> None:
        """Set up all command and message handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Message handler for text messages
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command."""
        user = update.effective_user
        welcome_message = (
            f"¡Hola {user.first_name}! 👋\n\n"
            "Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?\n"
            "Usa /help para ver los comandos disponibles."
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command."""
        help_text = (
            "Estos son los comandos disponibles:\n\n"
            "/start - Iniciar el bot\n"
            "/help - Mostrar este mensaje de ayuda\n"
        )
        await update.message.reply_text(help_text)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages."""
        try:
            # Get the user's message
            message_text = update.message.text
            user_id = update.effective_user.id
            
            # Here you can add your custom logic to process the message
            # For example, calling an AI service, database operations, etc.
            response = f"Recibí tu mensaje: {message_text}"
            
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await update.message.reply_text(
                "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Lo siento, ocurrió un error. Por favor, intenta de nuevo más tarde."
            )

    async def run(self) -> None:
        """Run the bot."""
        logger.info("Starting bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.run_polling()
        
    async def stop(self) -> None:
        """Stop the bot."""
        logger.info("Stopping bot...")
        await self.application.stop()

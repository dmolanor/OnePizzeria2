"""
Telegram bot integration for OnePizzeria chatbot.
"""

import logging
import os
from typing import Any, Dict

from telegram._update import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from .workflow import Workflow

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load bot token from config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set")

class OnePizzeriaTelegramBot:
    """Telegram bot for OnePizzeria chatbot."""
    
    def __init__(self):
        """Initialize bot with workflow."""
        self.workflow = Workflow()
        self.application = None
    
    async def setup(self):
        """Setup bot application and handlers."""
        # Create application
        self.application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("pedido", self.order_command))
        
        # Message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
        
        # Initialize application
        await self.application.initialize()
        await self.application.start()
        
        logger.info("Bot setup completed successfully")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user = update.effective_user
        await update.message.reply_text(
            f"¡Hola {user.first_name}! 👋\n\n"
            "Soy el asistente virtual de OnePizzeria. Estoy aquí para ayudarte a:\n\n"
            "🍕 Hacer pedidos\n"
            "📋 Consultar el menú\n"
            "❓ Responder tus preguntas\n\n"
            "¿En qué puedo ayudarte hoy?"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /help is issued."""
        await update.message.reply_text(
            "Estos son los comandos disponibles:\n\n"
            "/start - Iniciar conversación\n"
            "/menu - Ver el menú\n"
            "/pedido - Ver estado de tu pedido\n"
            "/help - Ver esta ayuda\n\n"
            "También puedes escribirme directamente lo que necesitas y te ayudaré."
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send menu when the command /menu is issued."""
        try:
            response = await self.workflow.run("Quiero ver el menú completo", str(update.effective_user.id))
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in menu command: {e}")
            await update.message.reply_text(
                "Lo siento, tuve un problema al obtener el menú. Por favor intenta de nuevo en un momento."
            )
    
    async def order_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check order status when the command /pedido is issued."""
        try:
            response = await self.workflow.run("¿Cuál es el estado de mi pedido?", str(update.effective_user.id))
            await update.message.reply_text(response)
        except Exception as e:
            logger.error(f"Error in order command: {e}")
            await update.message.reply_text(
                "Lo siento, tuve un problema al verificar tu pedido. Por favor intenta de nuevo en un momento."
            )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all non-command messages."""
        try:
            user_id = str(update.effective_user.id)
            message = update.message.text
            
            # Process message through workflow
            response = await self.workflow.run(message, user_id)
            
            # Send response
            await update.message.reply_text(response)
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await update.message.reply_text(
                "Lo siento, tuve un problema al procesar tu mensaje. Por favor intenta de nuevo en un momento."
            )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log Errors caused by Updates."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Send message to user if possible
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "Lo siento, ocurrió un error inesperado. Por favor intenta de nuevo en un momento."
            )
    
    async def run(self) -> None:
        """Start the bot."""
        try:
            # Setup bot
            await self.setup()
            
            # Start polling
            logger.info("🤖 Bot iniciado y listo para recibir mensajes!")
            await self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            if self.application:
                await self.application.stop()
            raise
        finally:
            if self.application:
                await self.application.stop()

def run_bot():
    """Run the bot."""
    bot = OnePizzeriaTelegramBot()
    try:
        import asyncio
        asyncio.run(bot.run())
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        raise 
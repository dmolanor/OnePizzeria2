import asyncio
import json
import logging
import signal
import sys
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage
from telegram import BotCommand, Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from src.core.checkpointer import state_manager
from src.core.memory import memory
from src.core.state import ChatState
from src.core.workflow import Workflow

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
        
        # Message grouping mechanism - prevents multiple responses for rapid messages
        self.pending_tasks: Dict[str, asyncio.Task] = {}  # cliente_id -> processing task
        self.pending_messages: Dict[str, List[str]] = {}  # cliente_id -> list of messages
        self.message_delay = 3.0  # seconds to wait for additional messages

    def _setup_handlers(self) -> None:
        """Set up all command and message handlers."""
        # Command handlers with non-blocking execution for better performance
        self.application.add_handler(
            CommandHandler("start", self.start_command, block=False)
        )
        self.application.add_handler(
            CommandHandler("help", self.help_command, block=False)
        )
        self.application.add_handler(
            CommandHandler("clear", self.clear_command, block=False)  # 🧹 NEW
        )
        self.application.add_handler(
            CommandHandler("info", self.info_command, block=False)    # 📊 NEW
        )
        self.application.add_handler(
            CommandHandler("admin_clear", self.admin_clear_command, block=False)  # 🔧 NEW (ADMIN)
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
        """
        Handle incoming messages with 3-second grouping delay.
        
        Multiple consecutive messages from the same user within 3 seconds
        will be grouped together and processed as a single request.
        """
        try:
            # Get the user's message and info
            message_text = update.message.text
            user = update.effective_user
            cliente_id = str(user.id)  # Convert to string as workflow expects string
            user_name = user.first_name
            
            logger.info(f"📥 Received message from {user_name} ({cliente_id}): {message_text}")
            
            # Cancel any existing processing task for this user
            if cliente_id in self.pending_tasks:
                self.pending_tasks[cliente_id].cancel()
                logger.info(f"⏹️ Cancelled previous processing task for user {cliente_id}")
            
            # Add message to pending messages for this user
            if cliente_id not in self.pending_messages:
                self.pending_messages[cliente_id] = []
            self.pending_messages[cliente_id].append(message_text)
            
            logger.info(f"📋 Total pending messages for {user_name}: {len(self.pending_messages[cliente_id])}")
            
            # Create new delayed processing task
            self.pending_tasks[cliente_id] = asyncio.create_task(
                self._delayed_message_processing(update, cliente_id, user_name)
            )
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Error in handle_message: {str(e)}")
            logger.error(f"Full traceback:\n{error_traceback}")
            await update.message.reply_text(
                "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
            )
    
    async def _delayed_message_processing(self, update: Update, cliente_id: str, user_name: str) -> None:
        """
        Process messages after a delay, allowing for message grouping.
        
        Args:
            update: The Telegram update object
            cliente_id: User identifier
            user_name: User's first name
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
                logger.info(f"🔄 Processing single message from {user_name}")
            else:
                combined_message = "\n".join(messages)
                logger.info(f"🔄 Processing {len(messages)} grouped messages from {user_name}")
                logger.info(f"📝 Combined message: {combined_message}")
            
            # Process combined message through workflow
            initial_state = await state_manager.load_state_for_user(cliente_id, HumanMessage(combined_message))
            initial_state["messages"] += [HumanMessage(combined_message)]
            
            logger.info("Starting workflow execution...")
            response_state = await self.workflow.workflow.ainvoke(initial_state)
            logger.info(f"Workflow completed. Response state: {response_state}")
            
            # Get the last message from the response state
            if response_state and response_state.get("messages"):
                response = response_state["messages"][-1]
                logger.info(f"Extracted response: {response}")
                
                # Send response to user
                await update.message.reply_text(response.content)
                logger.info(f"✅ Response sent to {user_name}")
            else:
                await update.message.reply_text(
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
            
            try:
                await update.message.reply_text(
                    "Lo siento, hubo un error procesando tu mensaje. Por favor, intenta de nuevo."
                )
            except Exception as reply_error:
                logger.error(f"Failed to send error message: {reply_error}")
            
            # Clean up on error
            if cliente_id in self.pending_tasks:
                del self.pending_tasks[cliente_id]
            if cliente_id in self.pending_messages:
                self.pending_messages[cliente_id] = []

    async def _handle_tool_response(self, update: Update, tool_call: dict) -> None:
        """Handle different types of tool responses."""
        try:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            if tool_name == "send_text_message":
                await update.message.reply_text(
                    tool_args["message"],
                    parse_mode=tool_args.get("parse_mode", "HTML")
                )
                
            elif tool_name == "send_image_message":
                await update.message.reply_photo(
                    photo=tool_args["image_url"],
                    caption=tool_args.get("caption")
                )
                
            elif tool_name == "send_inline_keyboard":
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                # Create keyboard markup
                keyboard = []
                for row in tool_args["buttons"]:
                    if isinstance(row, list):
                        # Handle multiple buttons per row
                        keyboard_row = [
                            InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])
                            for btn in row
                        ]
                        keyboard.append(keyboard_row)
                    else:
                        # Single button per row
                        keyboard.append([
                            InlineKeyboardButton(row["text"], callback_data=row["callback_data"])
                        ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    tool_args["message"],
                    reply_markup=reply_markup,
                    parse_mode=tool_args.get("parse_mode", "HTML")
                )
                
            elif tool_name == "send_menu_message":
                await update.message.reply_text(
                    tool_args["content"],
                    parse_mode="HTML"
                )
                
            elif tool_name == "send_order_summary":
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                # Create confirmation buttons
                keyboard = [
                    [InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"]) 
                     for btn in tool_args["buttons"]]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    tool_args["message"],
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                
            elif tool_name == "send_pdf_document":
                # Verificar que el archivo existe
                import os
                file_path = tool_args["file_path"]
                
                if not os.path.exists(file_path):
                    logger.error(f"PDF file not found: {file_path}")
                    await update.message.reply_text(
                        "Lo siento, no pude encontrar el menú en este momento. Por favor, intenta más tarde."
                    )
                    return
                    
                # Enviar el documento
                with open(file_path, 'rb') as pdf:
                    await update.message.reply_document(
                        document=pdf,
                        caption=tool_args.get("caption"),
                        parse_mode=tool_args.get("parse_mode", "HTML")
                    )
            
            else:
                logger.warning(f"Unknown tool response type: {tool_name}")
                await update.message.reply_text(str(tool_args))
                
        except Exception as e:
            logger.error(f"Error handling tool response: {e}")
            await update.message.reply_text(
                "Lo siento, hubo un error al procesar la respuesta. Por favor, intenta de nuevo."
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

    async def setup_bot_commands(self):
        """Setup bot commands menu."""
        commands = [
            BotCommand("start", "Iniciar conversación con el bot"),
            BotCommand("clear", "Borrar toda mi conversación y empezar de nuevo"),
            BotCommand("help", "Mostrar ayuda del bot"),
            BotCommand("info", "Ver información de mi cache"),
        ]
        await self.application.bot.set_my_commands(commands)
    
    async def clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        🧹 CLEAR USER CACHE COMMAND
        
        Allows users to completely clear their conversation history 
        and start fresh with the bot.
        """
        try:
            user = update.effective_user
            cliente_id = str(user.id)
            user_name = user.first_name
            
            logger.info(f"🧹 User {user_name} ({cliente_id}) requested cache clear")
            
            # Get cache info before clearing
            cache_info = await memory.get_user_cache_info(cliente_id)
            
            # Clear the cache
            success = await memory.clear_user_cache(cliente_id)
            
            if success:
                if cache_info.get("message_count", 0) > 0:
                    await update.message.reply_text(
                        f"✅ **Cache limpiado completamente**\n\n"
                        f"📊 **Datos eliminados:**\n"
                        f"• Mensajes: {cache_info.get('message_count', 0)}\n"
                        f"• Tamaño: {cache_info.get('cache_size_estimate', '0 KB')}\n"
                        f"• Registros BD: {cache_info.get('database_records', 0)}\n\n"
                        f"🎉 **¡Listo para empezar de nuevo!**\n"
                        f"Escribe cualquier mensaje para iniciar una conversación completamente nueva.",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        "✅ **Cache verificado**\n\n"
                        "No había datos anteriores almacenados. "
                        "Tu conversación ya está completamente limpia.\n\n"
                        "🎉 **¡Listo para empezar!**"
                    )
            else:
                await update.message.reply_text(
                    "❌ **Error al limpiar cache**\n\n"
                    "Hubo un problema técnico. Por favor intenta de nuevo "
                    "o contacta al administrador."
                )
                
        except Exception as e:
            logger.error(f"Error in clear command: {e}")
            await update.message.reply_text(
                "❌ Error inesperado al limpiar el cache. "
                "Por favor intenta de nuevo."
            )
    
    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        📊 SHOW USER CACHE INFO COMMAND
        
        Shows users information about their cached data.
        """
        try:
            user = update.effective_user
            cliente_id = str(user.id)
            
            cache_info = await memory.get_user_cache_info(cliente_id)
            
            if cache_info.get("error"):
                await update.message.reply_text(
                    f"❌ Error obteniendo información: {cache_info['error']}"
                )
                return
            
            message_count = cache_info.get("message_count", 0)
            cache_size = cache_info.get("cache_size_estimate", "0 KB")
            last_activity = cache_info.get("last_activity", "Nunca")
            
            if message_count > 0:
                await update.message.reply_text(
                    f"📊 **Información de tu cache:**\n\n"
                    f"💬 **Mensajes guardados:** {message_count}\n"
                    f"💾 **Tamaño del cache:** {cache_size}\n"
                    f"🕒 **Última actividad:** {last_activity}\n"
                    f"🗃️ **Registros en BD:** {cache_info.get('database_records', 0)}\n\n"
                    f"💡 **Tip:** Usa /clear para borrar todo y empezar de nuevo.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "📊 **Cache limpio**\n\n"
                    "No tienes datos anteriores almacenados. "
                    "Tu próximo mensaje iniciará una conversación nueva."
                )
                
        except Exception as e:
            logger.error(f"Error in info command: {e}")
            await update.message.reply_text(
                "❌ Error obteniendo información del cache."
            )
    
    async def admin_clear_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        🔧 ADMIN CACHE MANAGEMENT COMMAND
        
        For admins to manage cache globally.
        Format: /admin_clear [cliente_id|all]
        """
        try:
            user = update.effective_user
            cliente_id = str(user.id)
            
            # Check if user is admin - Configure your admin IDs here
            ADMIN_IDS = ["123456789"]  # 🔧 TODO: Replace with actual admin Telegram IDs
            
            if cliente_id not in ADMIN_IDS:
                await update.message.reply_text("❌ Solo administradores pueden usar este comando.")
                return
            
            # Get command arguments
            args = context.args
            if not args:
                await update.message.reply_text(
                    "📖 **Uso:** `/admin_clear [cliente_id|all]`\n\n"
                    "**Ejemplos:**\n"
                    "• `/admin_clear 123456789` - Limpiar cache de usuario específico\n"
                    "• `/admin_clear all` - Limpiar cache de todos los usuarios\n\n"
                    "⚠️ **Advertencia:** Esta operación no se puede deshacer.",
                    parse_mode='Markdown'
                )
                return
            
            target = args[0]
            
            if target.lower() == "all":
                # Clear all cache
                results = await memory.clear_all_cache()
                await update.message.reply_text(
                    f"🧹 **Cache global limpiado**\n\n"
                    f"📊 **Resultados:**\n"
                    f"```\n{json.dumps(results, indent=2, ensure_ascii=False)}\n```",
                    parse_mode='Markdown'
                )
            else:
                # Clear specific user cache
                target_cliente_id = target
                success = await memory.clear_user_cache(target_cliente_id)
                
                if success:
                    await update.message.reply_text(
                        f"✅ **Cache limpiado para usuario:** `{target_cliente_id}`",
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        f"❌ **Error limpiando cache para usuario:** `{target_cliente_id}`",
                        parse_mode='Markdown'
                    )
                    
        except Exception as e:
            logger.error(f"Error in admin_clear command: {e}")
            await update.message.reply_text(
                f"❌ Error en comando admin: {str(e)}"
            )

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
        
        # Setup bot commands menu
        await self.setup_bot_commands()
        
        await self.application.run_polling(drop_pending_updates=True)
        
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
        
        await self.application.stop()
        logger.info("Bot stopped successfully")
    
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

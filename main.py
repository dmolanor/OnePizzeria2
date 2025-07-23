"""
Main entry point for OnePizzeria chatbot.
"""

import asyncio
import logging
import os
import sys

from src.telegram_bot import OnePizzeriaTelegramBot

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to run the bot."""
    print("🍕 Iniciando OnePizzeria Chatbot...")
    print("🤖 Conectando con Telegram...")
    
    try:
        bot = OnePizzeriaTelegramBot()
        await bot.run()
    except Exception as e:
        logger.error(f"Error running bot: {e}")
        print(f"❌ Error ejecutando el bot: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        if sys.platform == "win32" and sys.version_info >= (3, 8):
            # Windows-specific event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot detenido por el usuario.")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        print(f"❌ Error fatal: {e}")
        sys.exit(1)
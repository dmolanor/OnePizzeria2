import logging

from config import TELEGRAM_BOT_TOKEN
from src.telegram_bot import TelegramBot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
    
    try:
        # Initialize and run the bot
        bot = TelegramBot(TELEGRAM_BOT_TOKEN)
        # The run method is now synchronous and handles the async internally
        bot.run_sync()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
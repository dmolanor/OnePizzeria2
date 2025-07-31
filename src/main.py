import argparse
import asyncio
import logging
import sys
from typing import Optional

from config.settings import (TELEGRAM_BOT_TOKEN, WHATSAPP_ACCESS_TOKEN,
                             WHATSAPP_PHONE_NUMBER_ID,
                             WHATSAPP_WEBHOOK_VERIFY_TOKEN)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def check_telegram_config() -> bool:
    """Check if Telegram configuration is available."""
    return bool(TELEGRAM_BOT_TOKEN)

def check_whatsapp_config() -> bool:
    """Check if WhatsApp configuration is available."""
    return bool(WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_WEBHOOK_VERIFY_TOKEN)

def run_telegram_bot():
    """Run the Telegram bot."""
    from src.bots.telegram_bot import TelegramBot
    
    logger.info("🤖 Starting Telegram bot...")
    bot = TelegramBot(TELEGRAM_BOT_TOKEN)
    bot.run_sync()

def run_whatsapp_bot(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the WhatsApp bot webhook server."""
    from src.bots.whatsapp_bot import WhatsAppBot
    
    logger.info("📱 Starting WhatsApp bot...")
    bot = WhatsAppBot()
    bot.run_webhook_server(host=host, port=port, debug=debug)

async def run_both_bots(whatsapp_host: str = "0.0.0.0", whatsapp_port: int = 5000):
    """Run both Telegram and WhatsApp bots concurrently."""
    from src.bots.telegram_bot import TelegramBot
    from src.bots.whatsapp_bot import WhatsAppBot
    
    logger.info("🚀 Starting both Telegram and WhatsApp bots...")
    
    # Initialize bots
    telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN)
    whatsapp_bot = WhatsAppBot()
    
    # Create tasks for both bots
    telegram_task = asyncio.create_task(telegram_bot.run())
    
    # Run WhatsApp webhook server in a separate thread
    import threading
    whatsapp_thread = threading.Thread(
        target=whatsapp_bot.run_webhook_server,
        args=(whatsapp_host, whatsapp_port),
        daemon=True
    )
    whatsapp_thread.start()
    
    try:
        # Wait for Telegram bot (WhatsApp runs in background thread)
        await telegram_task
    except KeyboardInterrupt:
        logger.info("Stopping both bots...")
        await telegram_bot.stop()
        await whatsapp_bot.stop()

def print_config_status():
    """Print the configuration status for both platforms."""
    print("\n" + "="*50)
    print("🔧 CONFIGURATION STATUS")
    print("="*50)
    
    telegram_ok = check_telegram_config()
    whatsapp_ok = check_whatsapp_config()
    
    print(f"📱 Telegram Bot: {'✅ Configured' if telegram_ok else '❌ Not configured'}")
    if telegram_ok:
        print(f"   Token: {'*' * 10}{TELEGRAM_BOT_TOKEN[-4:] if len(TELEGRAM_BOT_TOKEN) > 4 else '****'}")
    
    print(f"💬 WhatsApp Bot: {'✅ Configured' if whatsapp_ok else '❌ Not configured'}")
    if whatsapp_ok:
        print(f"   Phone Number ID: {WHATSAPP_PHONE_NUMBER_ID}")
        print(f"   Access Token: {'*' * 10}{WHATSAPP_ACCESS_TOKEN[-4:] if len(WHATSAPP_ACCESS_TOKEN) > 4 else '****'}")
        print(f"   Verify Token: {'*' * 6}{WHATSAPP_WEBHOOK_VERIFY_TOKEN[-2:] if len(WHATSAPP_WEBHOOK_VERIFY_TOKEN) > 2 else '**'}")
    
    print("\n" + "="*50)
    
    if not telegram_ok and not whatsapp_ok:
        print("❌ No bot configurations found!")
        print("Please configure at least one bot in your .env file:")
        print("   - For Telegram: TELEGRAM_BOT_TOKEN")
        print("   - For WhatsApp: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_WEBHOOK_VERIFY_TOKEN")
        return False
    
    return True

def main():
    """Main function with argument parsing for different bot modes."""
    parser = argparse.ArgumentParser(description="One Pizzeria Multi-Platform Bot")
    
    # Bot mode selection
    parser.add_argument(
        "--platform", 
        choices=["telegram", "whatsapp", "both"], 
        help="Choose which platform to run (default: auto-detect)"
    )
    
    # WhatsApp specific options
    parser.add_argument("--host", default="0.0.0.0", help="WhatsApp webhook host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="WhatsApp webhook port (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode for WhatsApp webhook")
    
    # Configuration check
    parser.add_argument("--config", action="store_true", help="Show configuration status and exit")
    
    args = parser.parse_args()
    
    # Show configuration if requested
    if args.config:
        print_config_status()
        return
    
    # Check configurations
    telegram_ok = check_telegram_config()
    whatsapp_ok = check_whatsapp_config()
    
    if not print_config_status():
        sys.exit(1)
    
    # Determine which platform to run
    platform = args.platform
    if not platform:
        if telegram_ok and whatsapp_ok:
            platform = "both"
        elif telegram_ok:
            platform = "telegram"
        elif whatsapp_ok:
            platform = "whatsapp"
        else:
            logger.error("No valid configuration found!")
            sys.exit(1)
    
    # Validate platform choice against available configs
    if platform == "telegram" and not telegram_ok:
        logger.error("Telegram configuration missing!")
        sys.exit(1)
    elif platform == "whatsapp" and not whatsapp_ok:
        logger.error("WhatsApp configuration missing!")
        sys.exit(1)
    elif platform == "both" and not (telegram_ok and whatsapp_ok):
        logger.error("Both Telegram and WhatsApp configurations required for 'both' mode!")
        sys.exit(1)
    
    try:
        # Run the appropriate bot(s)
        if platform == "telegram":
            run_telegram_bot()
        elif platform == "whatsapp":
            run_whatsapp_bot(host=args.host, port=args.port, debug=args.debug)
        elif platform == "both":
            asyncio.run(run_both_bots(whatsapp_host=args.host, whatsapp_port=args.port))
            
    except KeyboardInterrupt:
        logger.info("Bot(s) stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(f"Full traceback:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
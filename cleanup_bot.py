#!/usr/bin/env python3
"""
Utility script to clean up bot state and webhooks.
Run this if you're getting "Conflict: terminated by other getUpdates request" errors.
"""

import asyncio
import logging

from telegram import Bot

from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_bot():
    """Clean up bot webhooks and pending updates."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        # Delete webhook if exists
        logger.info("Deleting webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully")
        
        # Get bot info to verify connection
        bot_info = await bot.get_me()
        logger.info(f"Bot info: @{bot_info.username} ({bot_info.first_name})")
        
        logger.info("Bot cleanup completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
        # Close the bot session
        await bot.close()

if __name__ == "__main__":
    asyncio.run(cleanup_bot()) 
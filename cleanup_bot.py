#!/usr/bin/env python3
"""
🧹 Bot Cache Management Utility

This script provides comprehensive cache management for the pizzeria bot.
Use this for debugging, maintenance, and emergency cache clearing.

Usage:
    python cleanup_bot.py --help
    python cleanup_bot.py --user-info USER_ID
    python cleanup_bot.py --clear-user USER_ID
    python cleanup_bot.py --clear-all
    python cleanup_bot.py --list-users
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.append('src')

from config import supabase
from src.memory import memory


async def get_user_info(user_id: str) -> Dict:
    """Get detailed information about a user's cached data."""
    print(f"🔍 Getting cache information for user: {user_id}")
    
    cache_info = await memory.get_user_cache_info(user_id)
    
    # Also get raw database info
    try:
        result = supabase.table("conversations").select("*").eq("thread_id", user_id).execute()
        raw_data = result.data[0] if result.data else None
        
        if raw_data:
            cache_info["raw_database_data"] = {
                "id": raw_data.get("id"),
                "created_at": raw_data.get("created_at"),
                "updated_at": raw_data.get("updated_at"),
                "data_size_bytes": len(raw_data.get("data", "{}"))
            }
    except Exception as e:
        cache_info["raw_database_data"] = f"Error: {e}"
    
    return cache_info


async def clear_user_cache(user_id: str) -> bool:
    """Clear cache for a specific user."""
    print(f"🧹 Clearing cache for user: {user_id}")
    
    # Get info before clearing
    info_before = await get_user_info(user_id)
    print(f"📊 Data before clearing: {info_before.get('message_count', 0)} messages, {info_before.get('cache_size_estimate', '0 KB')}")
    
    # Clear the cache
    success = await memory.clear_user_cache(user_id)
    
    if success:
        print(f"✅ Cache cleared successfully for user {user_id}")
        
        # Verify clearing worked
        info_after = await get_user_info(user_id)
        if info_after.get('message_count', 0) == 0:
            print(f"✅ Verification: Cache is now clean")
        else:
            print(f"⚠️  Warning: {info_after.get('message_count', 0)} messages still remain")
    else:
        print(f"❌ Failed to clear cache for user {user_id}")
    
    return success


async def clear_all_cache() -> Dict:
    """Clear cache for all users."""
    print("🧹 Clearing cache for ALL users...")
    print("⚠️  This will remove ALL conversation data for ALL users!")
    
    confirm = input("Type 'CONFIRM' to proceed: ")
    if confirm != "CONFIRM":
        print("❌ Operation cancelled")
        return {"cancelled": True}
    
    results = await memory.clear_all_cache()
    print(f"✅ All cache cleared. Results: {results}")
    return results


async def list_all_users() -> List[Dict]:
    """List all users with cached data."""
    print("👥 Getting list of all users with cached data...")
    
    try:
        # Get all conversations from database
        result = supabase.table("conversations").select("thread_id, created_at, updated_at, data").execute()
        
        users = []
        for row in result.data:
            user_id = row["thread_id"]
            
            # Get detailed info for each user
            cache_info = await memory.get_user_cache_info(user_id)
            
            user_data = {
                "user_id": user_id,
                "message_count": cache_info.get("message_count", 0),
                "cache_size": cache_info.get("cache_size_estimate", "0 KB"),
                "last_activity": cache_info.get("last_activity", "Unknown"),
                "created_at": row.get("created_at", "Unknown"),
                "updated_at": row.get("updated_at", "Unknown")
            }
            users.append(user_data)
        
        # Sort by last activity
        users.sort(key=lambda x: x.get("last_activity", ""), reverse=True)
        
        print(f"\n📊 Found {len(users)} users with cached data:")
        print("-" * 80)
        for user in users:
            print(f"User ID: {user['user_id']}")
            print(f"  Messages: {user['message_count']}")
            print(f"  Cache Size: {user['cache_size']}")
            print(f"  Last Activity: {user['last_activity']}")
            print(f"  Created: {user['created_at']}")
            print(f"  Updated: {user['updated_at']}")
            print("-" * 40)
        
        return users
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        return []


async def interactive_mode():
    """Interactive mode for cache management."""
    print("🎮 Interactive Cache Management Mode")
    print("=" * 50)
    
    while True:
        print("\nOptions:")
        print("1. List all users")
        print("2. Get user info")
        print("3. Clear user cache")
        print("4. Clear all cache")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            await list_all_users()
        
        elif choice == "2":
            user_id = input("Enter user ID: ").strip()
            if user_id:
                info = await get_user_info(user_id)
                print(f"\n📊 User Info:\n{json.dumps(info, indent=2, ensure_ascii=False)}")
        
        elif choice == "3":
            user_id = input("Enter user ID to clear: ").strip()
            if user_id:
                await clear_user_cache(user_id)
        
        elif choice == "4":
            await clear_all_cache()
        
        elif choice == "5":
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option. Please select 1-5.")


async def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="Bot Cache Management Utility")
    parser.add_argument("--user-info", help="Get cache info for specific user ID")
    parser.add_argument("--clear-user", help="Clear cache for specific user ID")
    parser.add_argument("--clear-all", action="store_true", help="Clear cache for all users")
    parser.add_argument("--list-users", action="store_true", help="List all users with cached data")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    print("🧹 Bot Cache Management Utility")
    print("=" * 40)
    print(f"🕒 Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        if args.user_info:
            info = await get_user_info(args.user_info)
            print(json.dumps(info, indent=2, ensure_ascii=False))
        
        elif args.clear_user:
            await clear_user_cache(args.clear_user)
        
        elif args.clear_all:
            await clear_all_cache()
        
        elif args.list_users:
            await list_all_users()
        
        elif args.interactive:
            await interactive_mode()
        
        else:
            parser.print_help()
            print("\n💡 Tip: Use --interactive for a user-friendly interface")
    
    except KeyboardInterrupt:
        print("\n\n👋 Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 
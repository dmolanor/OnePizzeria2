#!/usr/bin/env python3
"""
Test script to verify message duplication fix.
This simulates the workflow execution and checks for message duplication.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from langchain_core.messages import HumanMessage
from src.workflow import Workflow

async def test_message_duplication():
    """Test that messages don't get duplicated in the workflow."""
    
    print("🧪 Testing Message Duplication Fix")
    print("=" * 50)
    
    # Initialize workflow
    workflow = Workflow()
    
    # Test with a simple greeting
    user_id = "test_user_123"
    test_message = "Buenos días"
    
    # Create initial state (simulating Telegram bot)
    initial_state = {
        "messages": [HumanMessage(content=test_message)], 
        "user_id": user_id
    }
    
    print(f"📥 Initial state:")
    print(f"   - Messages: {len(initial_state['messages'])}")
    print(f"   - Content: {[msg.content for msg in initial_state['messages']]}")
    print()
    
    try:
        # Run the workflow
        print("🔄 Running workflow...")
        result_state = await workflow.workflow.ainvoke(initial_state)
        
        print(f"📤 Final state:")
        print(f"   - Messages: {len(result_state.get('messages', []))}")
        
        # Analyze messages
        messages = result_state.get('messages', [])
        for i, msg in enumerate(messages):
            role = "👤 Usuario" if hasattr(msg, '__class__') and 'Human' in str(msg.__class__) else "🤖 Agente"
            content_preview = msg.content[:50] + "..." if len(msg.content) > 50 else msg.content
            print(f"   {i+1}. {role}: {content_preview}")
        
        # Check for duplicates
        user_messages = [msg for msg in messages if hasattr(msg, '__class__') and 'Human' in str(msg.__class__)]
        user_contents = [msg.content for msg in user_messages]
        
        print(f"\n🔍 Analysis:")
        print(f"   - Total messages: {len(messages)}")
        print(f"   - User messages: {len(user_messages)}")
        print(f"   - Unique user contents: {len(set(user_contents))}")
        
        # Check for duplication
        if len(user_contents) > len(set(user_contents)):
            print(f"❌ DUPLICATION DETECTED!")
            print(f"   - Duplicated contents: {[content for content in user_contents if user_contents.count(content) > 1]}")
            return False
        elif len(user_messages) > 1:
            print(f"⚠️  Multiple user messages found (might be expected if historical messages loaded)")
            for content in user_contents:
                print(f"     - '{content}'")
            return True
        else:
            print(f"✅ No duplication detected!")
            return True
            
    except Exception as e:
        import traceback
        print(f"❌ Error during workflow execution: {e}")
        print(f"Full traceback:\n{traceback.format_exc()}")
        return False

async def main():
    """Main test function."""
    success = await test_message_duplication()
    
    if success:
        print(f"\n🎉 Test completed successfully!")
    else:
        print(f"\n💥 Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 
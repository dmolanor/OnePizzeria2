print("Testing simple import...")

try:
    from src.services.tools import get_client_by_id
    print("✅ Import successful")
    
    result = get_client_by_id("7315133184")
    print(f"✅ Tool call result: {result}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("Test completed.") 
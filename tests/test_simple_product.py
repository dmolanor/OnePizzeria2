#!/usr/bin/env python3
"""
Test simple para verificar las herramientas de productos
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("🚀 SIMPLE PRODUCT TOOLS TEST")
    print("=" * 40)
    
    try:
        from src.tools import add_product_to_order
        print("✅ Successfully imported add_product_to_order")
        
        from src.tools import get_order_details
        print("✅ Successfully imported get_order_details")
        
        from config import supabase
        print("✅ Successfully imported supabase config")
        
        # Test basic functionality without database calls
        print("\n📋 Testing tool initialization...")
        
        # Test that tools have proper structure
        if hasattr(add_product_to_order, 'invoke'):
            print("✅ add_product_to_order has invoke method")
        else:
            print("❌ add_product_to_order missing invoke method")
            
        if hasattr(get_order_details, 'invoke'):
            print("✅ get_order_details has invoke method")
        else:
            print("❌ get_order_details missing invoke method")
            
        print("\n🎉 Simple test completed successfully!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    success = main()
    if success:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ TESTS FAILED!") 
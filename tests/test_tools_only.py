#!/usr/bin/env python3
"""
Test script para verificar solo las herramientas de pedidos
"""
from config import supabase
from src.tools import (create_order, finish_order, get_active_order_by_client,
                       get_client_by_id, update_order)


def test_tools():
    """Test only the order management tools"""
    
    print("🧪 TESTING ORDER TOOLS")
    print("=" * 40)
    
    test_user_id = "7315133184"
    
    # Test 1: Check user exists
    print(f"\n1️⃣ Testing get_client_by_id...")
    client_result = get_client_by_id.invoke({"user_id": test_user_id})
    if "error" in client_result:
        print(f"❌ User not found: {client_result}")
        return
    else:
        print(f"✅ User found: {client_result['nombre_completo']}")
    
    # Test 2: Clean up any existing order
    print(f"\n2️⃣ Cleaning up existing orders...")
    try:
        supabase.table("pedidos_activos").delete().eq("cliente_id", test_user_id).execute()
        print("✅ Cleanup completed")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")
    
    # Test 3: Create order
    print(f"\n3️⃣ Testing create_order...")
    create_result = create_order.invoke({
        "cliente_id": test_user_id,
        "items": [],
        "total": 0.0,
        "direccion_entrega": "Test Address"
    })
    
    if "success" in create_result:
        print(f"✅ Order created: {create_result}")
    else:
        print(f"❌ Failed to create: {create_result}")
        return
    
    # Test 4: Get active order
    print(f"\n4️⃣ Testing get_active_order_by_client...")
    active_order = get_active_order_by_client.invoke({"cliente_id": test_user_id})
    if "error" in active_order:
        print(f"❌ No active order: {active_order}")
        return
    else:
        print(f"✅ Active order found: ID {active_order['id']}")
        order_id = active_order['id']
    
    # Test 5: Update order
    print(f"\n5️⃣ Testing update_order...")
    test_items = [
        {
            "id": "pizza_1",
            "product_name": "Pizza Margherita",
            "product_type": "pizza",
            "base_price": 25000,
            "total_price": 25000,
            "nombre": "Pizza Margherita",
            "precio": 25000,
            "tipo": "pizza"
        }
    ]
    
    update_result = update_order.invoke({
        "id": order_id,
        "items": test_items,
        "total": 25000.0,
        "metodo_pago": "efectivo"
    })
    
    if "success" in update_result:
        print(f"✅ Order updated: {update_result}")
    else:
        print(f"❌ Failed to update: {update_result}")
        return
    
    # Test 6: Verify updated order
    print(f"\n6️⃣ Verifying updated order...")
    updated_order = get_active_order_by_client.invoke({"cliente_id": test_user_id})
    if "error" in updated_order:
        print(f"❌ Error getting updated order: {updated_order}")
    else:
        pedido_data = updated_order.get("pedido", {})
        items = pedido_data.get("items", [])
        total = pedido_data.get("total", 0)
        print(f"✅ Updated order verified:")
        print(f"   - Items: {len(items)}")
        print(f"   - Total: ${total}")
        print(f"   - Method: {updated_order.get('metodo_pago', 'None')}")
        if items:
            print(f"   - First item: {items[0].get('product_name', 'Unknown')}")
    
    # Test 7: Finish order
    print(f"\n7️⃣ Testing finish_order...")
    finish_result = finish_order.invoke({"cliente_id": test_user_id})
    if "success" in finish_result:
        print(f"✅ Order finished: {finish_result}")
    else:
        print(f"❌ Failed to finish: {finish_result}")
        return
    
    # Test 8: Verify order moved to finalized
    print(f"\n8️⃣ Verifying order moved to finalized...")
    final_check = get_active_order_by_client.invoke({"cliente_id": test_user_id})
    if "error" in final_check:
        print("✅ No active order found (correctly moved to finalized)")
        
        # Check in finalized orders
        try:
            finalized = supabase.table("pedidos_finalizados").select("*").eq("cliente_id", test_user_id).execute()
            if finalized.data:
                print(f"✅ Order found in finalized table: ID {finalized.data[0]['id']}")
                pedido_data = finalized.data[0].get("pedido", {})
                print(f"   - Items preserved: {len(pedido_data.get('items', []))}")
                print(f"   - Total preserved: ${pedido_data.get('total', 0)}")
            else:
                print("❌ Order not found in finalized table")
        except Exception as e:
            print(f"❌ Error checking finalized table: {e}")
    else:
        print(f"❌ Order still active (should have been moved): {final_check}")
    
    print(f"\n✅ All tests completed!")
    print("=" * 40)

if __name__ == "__main__":
    test_tools() 
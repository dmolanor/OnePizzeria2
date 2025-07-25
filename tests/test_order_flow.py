#!/usr/bin/env python3
"""
Test script para verificar el flujo completo de pedidos
"""
import asyncio

from config import supabase
from src.tools import (create_order, finish_order, get_active_order_by_client,
                       get_client_by_id, update_order)


async def test_order_flow():
    """Test the complete order management flow"""
    
    print("🧪 TESTING COMPLETE ORDER FLOW")
    print("=" * 50)
    
    test_user_id = "7315133184"
    
    # Step 1: Check if user exists
    print(f"\n1️⃣ Checking if user {test_user_id} exists...")
    client_result = get_client_by_id(test_user_id)
    if "error" in client_result:
        print(f"❌ User not found: {client_result}")
        return
    else:
        print(f"✅ User found: {client_result['nombre_completo']}")
    
    # Step 2: Check for existing active order
    print(f"\n2️⃣ Checking for existing active order...")
    existing_order = get_active_order_by_client(test_user_id)
    if "error" not in existing_order:
        print(f"⚠️ Active order found, cleaning up first...")
        # Clean up existing order for testing
        try:
            supabase.table("pedidos_activos").delete().eq("cliente_id", test_user_id).execute()
            print("✅ Cleaned up existing order")
        except:
            print("⚠️ Could not clean up existing order")
    else:
        print("✅ No existing active order found")
    
    # Step 3: Create new order
    print(f"\n3️⃣ Creating new order...")
    create_result = create_order(
        cliente_id=test_user_id,
        items=[],
        total=0.0,
        direccion_entrega=client_result.get("direccion", "Test Address"),
        estado="PREPARANDO"
    )
    
    if "success" in create_result:
        print(f"✅ Order created successfully")
        print(f"   Data: {create_result['data']}")
        order_id = create_result['data'][0]['id']
    else:
        print(f"❌ Failed to create order: {create_result}")
        return
    
    # Step 4: Add products to order
    print(f"\n4️⃣ Adding products to order...")
    test_items = [
        {
            "product_id": "ONE174",
            "product_name": "Pizza Napolitana",
            "product_type": "pizza",
            "base_price": 23900.0,
            "total_price": 23900.0
        },
        {
            "product_id": "ONE34", 
            "product_name": "Sprite Original",
            "product_type": "bebida",
            "base_price": 6000.0,
            "total_price": 6000.0
        }
    ]
    
    total_price = sum(item["total_price"] for item in test_items)
    
    update_result = update_order(
        id=order_id,
        items=test_items,
        total=total_price
    )
    
    if "success" in update_result:
        print(f"✅ Products added successfully")
        print(f"   Total: ${total_price}")
    else:
        print(f"❌ Failed to add products: {update_result}")
        return
    
    # Step 5: Update payment method
    print(f"\n5️⃣ Adding payment method...")
    payment_result = update_order(
        id=order_id,
        metodo_pago="efectivo"
    )
    
    if "success" in payment_result:
        print(f"✅ Payment method added successfully")
    else:
        print(f"❌ Failed to add payment method: {payment_result}")
        return
    
    # Step 6: Verify order state
    print(f"\n6️⃣ Verifying order state...")
    current_order = get_active_order_by_client(test_user_id)
    if "error" not in current_order:
        print(f"✅ Active order verified:")
        print(f"   ID: {current_order['id']}")
        print(f"   Estado: {current_order['estado']}")
        print(f"   Dirección: {current_order['direccion_entrega']}")
        print(f"   Método de pago: {current_order.get('metodo_pago', 'No especificado')}")
        print(f"   Items: {len(current_order['pedido']['items'])}")
        print(f"   Total: ${current_order['pedido']['total']}")
    else:
        print(f"❌ Could not verify order: {current_order}")
        return
    
    # Step 7: Finalize order
    print(f"\n7️⃣ Finalizing order...")
    finish_result = finish_order(test_user_id)
    
    if "success" in finish_result:
        print(f"✅ Order finalized successfully")
    else:
        print(f"❌ Failed to finalize order: {finish_result}")
        return
    
    # Step 8: Verify order moved to finalized
    print(f"\n8️⃣ Verifying order moved to finalized...")
    active_check = get_active_order_by_client(test_user_id)
    if "error" in active_check:
        print(f"✅ No active order found (correctly moved)")
        
        # Check finalized orders
        try:
            finalized_orders = supabase.table("pedidos_finalizados").select("*").eq("cliente_id", test_user_id).execute()
            if finalized_orders.data:
                latest_order = finalized_orders.data[-1]  # Get latest
                print(f"✅ Order found in finalized table:")
                print(f"   ID: {latest_order['id']}")
                print(f"   Estado: {latest_order['estado']}")
                print(f"   Total: ${latest_order['pedido']['total']}")
            else:
                print(f"⚠️ Order not found in finalized table")
        except Exception as e:
            print(f"❌ Error checking finalized orders: {e}")
    else:
        print(f"⚠️ Order still active: {active_check}")
    
    print(f"\n🎉 ORDER FLOW TEST COMPLETED!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_order_flow()) 
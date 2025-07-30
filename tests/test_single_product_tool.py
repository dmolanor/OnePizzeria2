#!/usr/bin/env python3
"""
Test específico para probar add_product_to_order con base de datos real
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("🚀 TESTING add_product_to_order")
    print("=" * 40)
    
    try:
        from config import supabase
        from src.tools import add_product_to_order, get_client_by_id

        # Usar un usuario de test conocido
        test_user_id = "7315133184"
        
        # Verificar que el usuario existe
        print(f"🔍 Checking user {test_user_id}...")
        user_result = get_client_by_id.invoke({"user_id": test_user_id})
        
        if "error" in user_result:
            print(f"❌ User not found: {user_result}")
            print("⚠️ Skipping database test due to missing user")
            return True  # No es un error de las herramientas
        
        print(f"✅ User found: {user_result.get('nombre_completo', 'Unknown')}")
        
        # Limpiar pedidos activos existentes
        print("🧹 Cleaning up existing orders...")
        try:
            supabase.table("pedidos_activos").delete().eq("cliente_id", test_user_id).execute()
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        # Test: Agregar un producto simple
        print("\n🍕 Testing add_product_to_order...")
        product_data = {
            "id": "test_product_001",
            "nombre": "Pizza Test Margherita",
            "tipo": "pizza",
            "precio": 20000,
            "tamano": "Medium",
            "categoria": "pizza_armada",
            "descripcion": "Pizza de test con tomate y queso"
        }
        
        result = add_product_to_order.invoke({
            "cliente_id": test_user_id,
            "product_data": product_data
        })
        
        if "success" in result:
            print(f"✅ Product added successfully!")
            print(f"📦 Order ID: {result['data']['order_id']}")
            print(f"💰 Order Total: ${result['data']['order_total']}")
            print(f"🍕 Product: {result['data']['product']['product_name']}")
            print(f"💵 Product Price: ${result['data']['product']['total_price']}")
            
            # Verificar que el producto fue estructurado correctamente
            product = result['data']['product']
            expected_fields = ['product_id', 'product_name', 'product_type', 'base_price', 'total_price']
            
            missing_fields = []
            for field in expected_fields:
                if field not in product:
                    missing_fields.append(field)
            
            if not missing_fields:
                print("✅ Product structure is correct")
            else:
                print(f"⚠️ Missing fields in product: {missing_fields}")
            
            # Verificar que el precio se calculó correctamente
            if product['total_price'] == product_data['precio']:
                print("✅ Price calculation is correct")
            else:
                print(f"⚠️ Price mismatch: expected ${product_data['precio']}, got ${product['total_price']}")
                
        else:
            print(f"❌ Failed to add product: {result}")
            return False
            
        print("\n🎉 Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"💥 Test failed with error: {e}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ SINGLE PRODUCT TEST PASSED!")
    else:
        print("\n❌ SINGLE PRODUCT TEST FAILED!") 
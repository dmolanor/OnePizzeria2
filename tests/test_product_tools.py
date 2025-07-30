#!/usr/bin/env python3
"""
Test script comprehensivo para las nuevas herramientas de manejo de productos
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import supabase
from src.tools import (  # Herramientas básicas de productos; Herramientas inteligentes; Herramientas base necesarias; Herramientas de menú
    add_product_to_order, add_product_to_order_smart, calculate_order_total,
    create_order, get_active_order_by_client, get_adition_price_by_name,
    get_beverage_by_name, get_border_price_by_name, get_client_by_id,
    get_order_details, get_pizza_by_name, remove_product_from_order,
    update_product_in_order, update_product_in_order_smart)


def cleanup_test_data(test_user_id: str):
    """Limpia datos de test anteriores"""
    try:
        supabase.table("pedidos_activos").delete().eq("cliente_id", test_user_id).execute()
        print("✅ Test data cleaned up")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")


def test_basic_product_tools():
    """Test de herramientas básicas de productos"""
    print("\n🧪 TESTING BASIC PRODUCT TOOLS")
    print("=" * 50)
    
    test_user_id = "7315133184"
    cleanup_test_data(test_user_id)
    
    # Test 1: Verificar que el usuario existe
    print(f"\n1️⃣ Checking if user exists...")
    client_result = get_client_by_id.invoke({"user_id": test_user_id})
    if "error" in client_result:
        print(f"❌ User not found: {client_result}")
        return False
    print(f"✅ User found: {client_result.get('nombre_completo', 'Unknown')}")
    
    # Test 2: Agregar producto básico
    print(f"\n2️⃣ Testing add_product_to_order...")
    product_data = {
        "id": "test_pizza_1",
        "nombre": "Pizza Test Pepperoni",
        "tipo": "pizza",
        "precio": 25000,
        "tamano": "Large",
        "categoria": "pizza_armada"
    }
    
    add_result = add_product_to_order.invoke({
        "cliente_id": test_user_id,
        "product_data": product_data
    })
    
    if "success" in add_result:
        print(f"✅ Product added: {add_result['success']}")
        order_id = add_result["data"]["order_id"]
        print(f"📦 Order ID: {order_id}, Total: ${add_result['data']['order_total']}")
    else:
        print(f"❌ Failed to add product: {add_result}")
        return False
    
    # Test 3: Agregar producto con personalizaciones
    print(f"\n3️⃣ Testing add_product_to_order with customizations...")
    borde_data = {"nombre": "pimentón", "precio_adicional": 2000}
    adiciones_data = [
        {"nombre": "queso extra", "precio_adicional": 5000},
        {"nombre": "champiñones", "precio_adicional": 3000}
    ]
    
    pizza_data = {
        "id": "test_pizza_2",
        "nombre": "Pizza Test Hawaiana",
        "tipo": "pizza",
        "precio": 23000
    }
    
    add_custom_result = add_product_to_order.invoke({
        "cliente_id": test_user_id,
        "product_data": pizza_data,
        "borde": borde_data,
        "adiciones": adiciones_data
    })
    
    if "success" in add_custom_result:
        print(f"✅ Customized product added: {add_custom_result['success']}")
        expected_total = 23000 + 2000 + 5000 + 3000  # Base + borde + adiciones
        actual_total = add_custom_result["data"]["product"]["total_price"]
        print(f"💰 Expected price: ${expected_total}, Actual: ${actual_total}")
        if actual_total == expected_total:
            print("✅ Price calculation correct")
        else:
            print(f"❌ Price calculation error")
    else:
        print(f"❌ Failed to add customized product: {add_custom_result}")
        return False
    
    # Test 4: Calcular total del pedido
    print(f"\n4️⃣ Testing calculate_order_total...")
    total_result = calculate_order_total.invoke({"cliente_id": test_user_id})
    
    if "success" in total_result:
        print(f"✅ Order total calculated: ${total_result['data']['total']}")
        print(f"📊 Items count: {total_result['data']['items_count']}")
    else:
        print(f"❌ Failed to calculate total: {total_result}")
    
    # Test 5: Obtener detalles del pedido
    print(f"\n5️⃣ Testing get_order_details...")
    details_result = get_order_details.invoke({"cliente_id": test_user_id})
    
    if "success" in details_result:
        print(f"✅ Order details obtained")
        order_data = details_result["data"]
        print(f"📦 Order ID: {order_data['order_id']}")
        print(f"💰 Total: ${order_data['total']}")
        print(f"🍕 Products: {len(order_data['products'])}")
        
        for i, product in enumerate(order_data['products']):
            print(f"   {i+1}. {product['name']} - ${product['total_price']}")
            if product['customizations']['borde']:
                print(f"      🎯 Borde: {product['customizations']['borde']['nombre']}")
            if product['customizations']['adiciones']:
                adiciones_names = [a['nombre'] for a in product['customizations']['adiciones']]
                print(f"      🍕 Adiciones: {', '.join(adiciones_names)}")
    else:
        print(f"❌ Failed to get order details: {details_result}")
    
    # Test 6: Actualizar producto
    print(f"\n6️⃣ Testing update_product_in_order...")
    new_borde = {"nombre": "ajo", "precio_adicional": 1500}
    new_adiciones = [{"nombre": "pepperoni", "precio_adicional": 4000}]
    
    update_result = update_product_in_order.invoke({
        "cliente_id": test_user_id,
        "product_id": "test_pizza_2",
        "new_borde": new_borde,
        "new_adiciones": new_adiciones
    })
    
    if "success" in update_result:
        print(f"✅ Product updated: {update_result['success']}")
        print(f"💰 New total price: ${update_result['data']['updated_product']['total_price']}")
    else:
        print(f"❌ Failed to update product: {update_result}")
    
    # Test 7: Remover producto
    print(f"\n7️⃣ Testing remove_product_from_order...")
    remove_result = remove_product_from_order.invoke({
        "cliente_id": test_user_id,
        "product_id": "test_pizza_1"
    })
    
    if "success" in remove_result:
        print(f"✅ Product removed: {remove_result['success']}")
        print(f"📦 Remaining items: {remove_result['data']['remaining_items']}")
        print(f"💰 New total: ${remove_result['data']['order_total']}")
    else:
        print(f"❌ Failed to remove product: {remove_result}")
    
    return True


def test_smart_product_tools():
    """Test de herramientas inteligentes de productos"""
    print("\n🧪 TESTING SMART PRODUCT TOOLS")
    print("=" * 50)
    
    test_user_id = "test_smart_user"
    cleanup_test_data(test_user_id)
    
    # Test 1: Buscar precios de bordes
    print(f"\n1️⃣ Testing get_border_price_by_name...")
    border_result = get_border_price_by_name.invoke({"name": "pimentón"})
    
    if "success" in border_result:
        print(f"✅ Border price found: {border_result['data']}")
        border_price = border_result['data']['precio_adicional']
    else:
        print(f"⚠️ Border not found in DB, will use fallback: {border_result}")
        border_price = 2000  # Fallback
    
    # Test 2: Buscar precios de adiciones
    print(f"\n2️⃣ Testing get_adition_price_by_name...")
    adition_result = get_adition_price_by_name.invoke({"name": "queso extra"})
    
    if "success" in adition_result:
        print(f"✅ Adition price found: {adition_result['data']}")
        adition_price = adition_result['data']['precio_adicional']
    else:
        print(f"⚠️ Adition not found in DB, will use fallback: {adition_result}")
        adition_price = 5000  # Fallback
    
    # Test 3: Agregar producto con herramienta inteligente
    print(f"\n3️⃣ Testing add_product_to_order_smart...")
    smart_product = {
        "id": "smart_pizza_1",
        "nombre": "Pizza Smart Pepperoni",
        "tipo": "pizza",
        "precio": 28000
    }
    
    smart_add_result = add_product_to_order_smart.invoke({
        "cliente_id": test_user_id,
        "product_data": smart_product,
        "borde_name": "pimentón",
        "adiciones_names": ["queso extra", "champiñones"]
    })
    
    if "success" in smart_add_result:
        print(f"✅ Smart product added: {smart_add_result['success']}")
        total_price = smart_add_result["data"]["product"]["total_price"]
        print(f"💰 Total price with dynamic pricing: ${total_price}")
        
        # Verificar que el precio incluye bordes y adiciones
        base_price = smart_product["precio"]
        expected_min = base_price + border_price + adition_price  # Al menos esto
        if total_price >= expected_min:
            print(f"✅ Price includes customizations (base: ${base_price})")
        else:
            print(f"❌ Price calculation may be incorrect")
    else:
        print(f"❌ Failed to add smart product: {smart_add_result}")
    
    # Test 4: Actualizar con herramienta inteligente
    print(f"\n4️⃣ Testing update_product_in_order_smart...")
    smart_update_result = update_product_in_order_smart.invoke({
        "cliente_id": test_user_id,
        "product_id": "smart_pizza_1",
        "new_borde_name": "ajo",
        "new_adiciones_names": ["pepperoni"]
    })
    
    if "success" in smart_update_result:
        print(f"✅ Smart product updated: {smart_update_result['success']}")
        new_total = smart_update_result["data"]["updated_product"]["total_price"]
        print(f"💰 Updated total price: ${new_total}")
    else:
        print(f"❌ Failed to update smart product: {smart_update_result}")
    
    return True


def test_edge_cases():
    """Test de casos límite y errores"""
    print("\n🧪 TESTING EDGE CASES")
    print("=" * 50)
    
    test_user_id = "edge_case_user"
    cleanup_test_data(test_user_id)
    
    # Test 1: Agregar producto a cliente inexistente
    print(f"\n1️⃣ Testing with non-existent client...")
    fake_user = "fake_user_999"
    fake_product = {
        "id": "fake_pizza",
        "nombre": "Fake Pizza",
        "tipo": "pizza",
        "precio": 20000
    }
    
    fake_result = add_product_to_order.invoke({
        "cliente_id": fake_user,
        "product_data": fake_product
    })
    
    # Esto debería crear un pedido automáticamente
    if "success" in fake_result:
        print(f"✅ Order auto-created for non-existent client: {fake_result['success']}")
        cleanup_test_data(fake_user)  # Limpiar
    else:
        print(f"⚠️ Could not create order for non-existent client: {fake_result}")
    
    # Test 2: Remover producto inexistente
    print(f"\n2️⃣ Testing remove non-existent product...")
    # Primero crear un pedido válido
    create_order.invoke({
        "cliente_id": test_user_id,
        "items": [],
        "total": 0.0
    })
    
    remove_fake_result = remove_product_from_order.invoke({
        "cliente_id": test_user_id,
        "product_id": "non_existent_product"
    })
    
    if "error" in remove_fake_result:
        print(f"✅ Correctly handled non-existent product: {remove_fake_result['error']}")
    else:
        print(f"❌ Should have failed for non-existent product")
    
    # Test 3: Calcular total de pedido vacío
    print(f"\n3️⃣ Testing calculate total for empty order...")
    empty_total_result = calculate_order_total.invoke({"cliente_id": test_user_id})
    
    if "success" in empty_total_result:
        total = empty_total_result["data"]["total"]
        if total == 0:
            print(f"✅ Correctly calculated empty order total: ${total}")
        else:
            print(f"❌ Empty order should have total 0, got ${total}")
    else:
        print(f"⚠️ Failed to calculate empty order total: {empty_total_result}")
    
    # Test 4: Actualizar producto inexistente
    print(f"\n4️⃣ Testing update non-existent product...")
    update_fake_result = update_product_in_order.invoke({
        "cliente_id": test_user_id,
        "product_id": "non_existent_product",
        "new_borde": {"nombre": "test", "precio_adicional": 1000}
    })
    
    if "error" in update_fake_result:
        print(f"✅ Correctly handled non-existent product update: {update_fake_result['error']}")
    else:
        print(f"❌ Should have failed for non-existent product update")
    
    return True


def test_integration_flow():
    """Test de flujo completo de integración"""
    print("\n🧪 TESTING INTEGRATION FLOW")
    print("=" * 50)
    
    test_user_id = "integration_user"
    cleanup_test_data(test_user_id)
    
    # Flujo completo: Crear pedido -> Agregar productos -> Personalizar -> Calcular -> Finalizar
    print(f"\n🔄 Complete order flow for user: {test_user_id}")
    
    # 1. Agregar primera pizza
    pizza1 = {
        "id": "integration_pizza_1",
        "nombre": "Pizza Margherita",
        "tipo": "pizza",
        "precio": 22000
    }
    
    result1 = add_product_to_order_smart.invoke({
        "cliente_id": test_user_id,
        "product_data": pizza1,
        "borde_name": "pimentón"
    })
    
    if "success" not in result1:
        print(f"❌ Failed step 1: {result1}")
        return False
    
    # 2. Agregar segunda pizza con adiciones
    pizza2 = {
        "id": "integration_pizza_2", 
        "nombre": "Pizza Pepperoni",
        "tipo": "pizza",
        "precio": 25000
    }
    
    result2 = add_product_to_order_smart.invoke({
        "cliente_id": test_user_id,
        "product_data": pizza2,
        "adiciones_names": ["queso extra", "champiñones"]
    })
    
    if "success" not in result2:
        print(f"❌ Failed step 2: {result2}")
        return False
    
    # 3. Agregar bebida
    bebida = {
        "id": "integration_bebida_1",
        "nombre": "Coca Cola",
        "tipo": "bebida", 
        "precio": 3000
    }
    
    result3 = add_product_to_order.invoke({
        "cliente_id": test_user_id,
        "product_data": bebida
    })
    
    if "success" not in result3:
        print(f"❌ Failed step 3: {result3}")
        return False
    
    # 4. Obtener resumen completo
    final_details = get_order_details.invoke({"cliente_id": test_user_id})
    
    if "success" in final_details:
        order_data = final_details["data"]
        print(f"\n📊 FINAL ORDER SUMMARY:")
        print(f"   Order ID: {order_data['order_id']}")
        print(f"   Total Items: {order_data['items_count']}")
        print(f"   Total Price: ${order_data['total']}")
        print(f"   Products:")
        
        for i, product in enumerate(order_data['products']):
            print(f"     {i+1}. {product['name']} - ${product['total_price']}")
            if product['customizations']['borde']:
                print(f"        🎯 Borde: {product['customizations']['borde']['nombre']}")
            if product['customizations']['adiciones']:
                adiciones = [a['nombre'] for a in product['customizations']['adiciones']]
                print(f"        🍕 Adiciones: {', '.join(adiciones)}")
        
        print(f"✅ Integration flow completed successfully!")
        return True
    else:
        print(f"❌ Failed to get final details: {final_details}")
        return False


def main():
    """Ejecutar todos los tests"""
    print("🚀 STARTING COMPREHENSIVE PRODUCT TOOLS TESTS")
    print("=" * 60)
    
    tests = [
        ("Basic Product Tools", test_basic_product_tools),
        ("Smart Product Tools", test_smart_product_tools), 
        ("Edge Cases", test_edge_cases),
        ("Integration Flow", test_integration_flow)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name}...")
        try:
            success = test_func()
            results.append((test_name, success))
            if success:
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"💥 {test_name} CRASHED: {e}")
            results.append((test_name, False))
    
    # Resultados finales
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10} | {test_name}")
        if success:
            passed += 1
    
    print("=" * 60)
    print(f"Results: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️ Some tests failed. Check the logs above.")


if __name__ == "__main__":
    main() 
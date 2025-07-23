#!/usr/bin/env python3
"""
Test file to understand Supabase database operations and debug issues
"""

import json

from config import supabase


def test_database_structure():
    """Test the current database structure and constraints"""
    print("=== TESTING DATABASE STRUCTURE ===")
    
    # Test 1: Check clientes table structure
    print("\n1. Testing clientes table structure...")
    try:
        # Try to get table info (this might not work directly, but let's see)
        result = supabase.table("clientes").select("*").limit(1).execute()
        print(f"Clientes table query success: {len(result.data)} rows")
        if result.data:
            print(f"Sample row structure: {result.data[0].keys()}")
    except Exception as e:
        print(f"Error querying clientes: {e}")
    
    # Test 2: Check pizzas table
    print("\n2. Testing pizzas_armadas table...")
    try:
        result = supabase.table("pizzas_armadas").select("*").limit(3).execute()
        print(f"Pizzas found: {len(result.data)}")
        for pizza in result.data:
            print(f"- {pizza.get('nombre', 'N/A')} (${pizza.get('precio', 'N/A')})")
    except Exception as e:
        print(f"Error querying pizzas: {e}")
    
    # Test 3: Check bebidas table
    print("\n3. Testing bebidas table...")
    try:
        result = supabase.table("bebidas").select("*").limit(3).execute()
        print(f"Bebidas found: {len(result.data)}")
        for bebida in result.data:
            print(f"- {bebida.get('nombre_producto', 'N/A')} (${bebida.get('precio', 'N/A')})")
    except Exception as e:
        print(f"Error querying bebidas: {e}")

def test_client_operations():
    """Test client CRUD operations to understand the exact requirements"""
    print("\n=== TESTING CLIENT OPERATIONS ===")
    
    test_user_id = "TEST_USER_123"
    
    # Test 1: Try to create a client with minimal data
    print("\n1. Testing client creation with minimal data...")
    try:
        client_data = {
            "id": test_user_id,
            "nombre_completo": "Test User", 
            "telefono": "1234567890"
        }
        result = supabase.table("clientes").insert(client_data).execute()
        print(f"✅ Client created successfully: {result.data}")
    except Exception as e:
        print(f"❌ Error creating client: {e}")
        
        # Let's try with separate nombre and apellido based on schema
        print("\n1b. Trying with separate nombre and apellido...")
        try:
            client_data_separate = {
                "id": test_user_id,
                "nombre_completo": "Test User",
                "nombre": "Test",
                "apellido": "User", 
                "telefono": "1234567890"
            }
            result = supabase.table("clientes").insert(client_data_separate).execute()
            print(f"✅ Client created with separate fields: {result.data}")
        except Exception as e2:
            print(f"❌ Error with separate fields: {e2}")
    
    # Test 2: Try to get the client
    print("\n2. Testing client retrieval...")
    try:
        result = supabase.table("clientes").select("*").eq("id", test_user_id).execute()
        if result.data:
            print(f"✅ Client found: {result.data[0]}")
            client = result.data[0]
        else:
            print("❌ Client not found")
            return
    except Exception as e:
        print(f"❌ Error retrieving client: {e}")
        return
    
    # Test 3: Try to update the client
    print("\n3. Testing client update...")
    try:
        update_data = {"direccion": "Test Address 123"}
        result = supabase.table("clientes").update(update_data).eq("id", test_user_id).execute()
        print(f"✅ Client updated: {result.data}")
    except Exception as e:
        print(f"❌ Error updating client: {e}")
    
    # Test 4: Clean up - delete test client
    print("\n4. Cleaning up test client...")
    try:
        result = supabase.table("clientes").delete().eq("id", test_user_id).execute()
        print(f"✅ Test client deleted")
    except Exception as e:
        print(f"❌ Error deleting test client: {e}")

def test_pizza_operations():
    """Test pizza search operations"""
    print("\n=== TESTING PIZZA OPERATIONS ===")
    
    # Test 1: Search for pepperoni pizza
    print("\n1. Testing pepperoni pizza search...")
    try:
        # Exact match
        result = supabase.table("pizzas_armadas").select("*").eq("nombre", "pepperoni").execute()
        print(f"Exact match 'pepperoni': {len(result.data)} results")
        
        # Case insensitive search
        result = supabase.table("pizzas_armadas").select("*").ilike("nombre", "%pepperoni%").execute()
        print(f"ilike search '%pepperoni%': {len(result.data)} results")
        
        if result.data:
            pizza = result.data[0]
            print(f"Found pizza: {pizza['nombre']} - ${pizza['precio']}")
            print(f"Full pizza data: {pizza}")
    except Exception as e:
        print(f"❌ Error searching pizzas: {e}")

def test_order_operations():
    """Test order operations"""
    print("\n=== TESTING ORDER OPERATIONS ===")
    
    test_user_id = "TEST_ORDER_USER"
    
    # First create a test client for orders
    try:
        client_data = {
            "id": test_user_id,
            "nombre_completo": "Order Test User",
            "nombre": "Order",
            "apellido": "User", 
            "telefono": "9876543210"
        }
        supabase.table("clientes").insert(client_data).execute()
        print("✅ Test client created for order testing")
    except Exception as e:
        print(f"Note: {e}")  # Might already exist
    
    # Test creating an order
    print("\n1. Testing order creation...")
    try:
        order_data = {
            "cliente_id": test_user_id,
            "estado": "EN_PROGRESO",  # Based on schema, this might be an enum
            "pedido": {"items": [{"pizza": "pepperoni", "precio": 17900}]},
            "direccion_entrega": "Test Address"
        }
        result = supabase.table("pedidos_activos").insert(order_data).execute()
        print(f"✅ Order created: {result.data}")
        order_id = result.data[0]["id"] if result.data else None
    except Exception as e:
        print(f"❌ Error creating order: {e}")
        order_id = None
    
    # Clean up
    if order_id:
        try:
            supabase.table("pedidos_activos").delete().eq("id", order_id).execute()
            print("✅ Test order cleaned up")
        except Exception as e:
            print(f"Error cleaning up order: {e}")
    
    try:
        supabase.table("clientes").delete().eq("id", test_user_id).execute()
        print("✅ Test client cleaned up")
    except Exception as e:
        print(f"Error cleaning up client: {e}")

def test_enum_values():
    """Test to understand enum values for order states"""
    print("\n=== TESTING ENUM VALUES ===")
    
    # Test different enum values
    test_user_id = "TEST_ENUM_USER"
    
    # Create test client first
    try:
        client_data = {
            "id": test_user_id,
            "nombre_completo": "Enum Test User",
            "nombre": "Enum",
            "apellido": "User", 
            "telefono": "1111111111"
        }
        supabase.table("clientes").insert(client_data).execute()
        print("✅ Test client created for enum testing")
    except Exception as e:
        print(f"Note: {e}")
    
    # Try different enum values
    enum_values = [
        "PENDIENTE",
        "EN_PROCESO", 
        "CONFIRMADO",
        "EN_PREPARACION",
        "EN_CAMINO",
        "ENTREGADO",
        "CANCELADO"
    ]
    
    for enum_val in enum_values:
        try:
            order_data = {
                "cliente_id": test_user_id,
                "estado": enum_val,
                "pedido": {"items": [{"pizza": "test", "precio": 1000}]},
                "direccion_entrega": "Test Address"
            }
            result = supabase.table("pedidos_activos").insert(order_data).execute()
            print(f"✅ Enum '{enum_val}' works!")
            # Clean up immediately
            if result.data:
                supabase.table("pedidos_activos").delete().eq("id", result.data[0]["id"]).execute()
            break  # If one works, we found it
        except Exception as e:
            print(f"❌ Enum '{enum_val}' failed: {str(e)[:100]}...")
    
    # Clean up test client
    try:
        supabase.table("clientes").delete().eq("id", test_user_id).execute()
    except:
        pass

def test_real_user_scenario():
    """Test the exact scenario from the bot logs"""
    print("\n=== TESTING REAL USER SCENARIO ===")
    
    real_user_id = "7315133184"
    
    print("\n1. Testing if user already exists...")
    try:
        result = supabase.table("clientes").select("*").eq("id", real_user_id).execute()
        if result.data:
            print(f"✅ User already exists: {result.data[0]}")
            existing_user = result.data[0]
        else:
            print("❌ User doesn't exist")
            existing_user = None
    except Exception as e:
        print(f"❌ Error checking user: {e}")
        existing_user = None
    
    print("\n2. Testing create_client with proper fields...")
    if not existing_user:
        try:
            # Split "Diego Molano" into nombre and apellido
            nombre_completo = "Diego Molano"
            parts = nombre_completo.split(" ", 1)
            nombre = parts[0] if parts else ""
            apellido = parts[1] if len(parts) > 1 else ""
            
            client_data = {
                "id": real_user_id,
                "nombre_completo": nombre_completo,
                "nombre": nombre,
                "apellido": apellido,
                "telefono": "3203782744"
            }
            result = supabase.table("clientes").insert(client_data).execute()
            print(f"✅ Real user created: {result.data}")
        except Exception as e:
            print(f"❌ Error creating real user: {e}")
    
    print("\n3. Testing update_client with address...")
    try:
        update_data = {"direccion": "Calle 127A #11B-76 Apto 401"}
        result = supabase.table("clientes").update(update_data).eq("id", real_user_id).execute()
        print(f"✅ Real user updated: {result.data}")
    except Exception as e:
        print(f"❌ Error updating real user: {e}")
    
    print("\n4. Testing final user state...")
    try:
        result = supabase.table("clientes").select("*").eq("id", real_user_id).execute()
        if result.data:
            print(f"✅ Final user state: {result.data[0]}")
        else:
            print("❌ User not found after operations")
    except Exception as e:
        print(f"❌ Error getting final state: {e}")

def main():
    """Run all tests"""
    print("🔍 SUPABASE DATABASE TESTING")
    print("=" * 50)
    
    test_database_structure()
    test_client_operations()
    test_pizza_operations()
    test_enum_values()
    test_real_user_scenario()
    test_order_operations()
    
    print("\n" + "=" * 50)
    print("🏁 TESTING COMPLETE")

if __name__ == "__main__":
    main() 
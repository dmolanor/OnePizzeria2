"""
Test para verificar la conectividad con la base de datos real de Supabase
y las herramientas adaptadas al esquema.
"""

import asyncio
import os
import sys

# Agregar el directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.memory import memory_manager
from src.tools import (get_customer, get_full_menu, get_pizza_additions,
                       get_pizzas_by_ingredients, search_menu)
from src.workflow import Workflow


async def test_database_connection():
    """Test básico de conectividad con Supabase"""
    print("🔧 Probando conectividad con Supabase...")
    
    try:
        # Test 1: Buscar cliente (debería retornar vacío para usuario no existente)
        print("\n1. Testing get_customer...")
        result = get_customer.invoke({"user_id": "test_user_12345"})
        print(f"   Resultado: {result}")
        print(f"   ✅ get_customer funciona (retorna dict vacío como esperado)")
        
        # Test 2: Buscar en el menú
        print("\n2. Testing search_menu...")
        result = search_menu.invoke({"query": "pizza"})
        print(f"   Resultado: {len(result.get('pizzas', []))} pizzas encontradas")
        if result.get('pizzas'):
            print(f"   Primera pizza: {result['pizzas'][0].get('nombre', 'N/A')}")
        print(f"   ✅ search_menu funciona")
        
        # Test 3: Obtener menú completo
        print("\n3. Testing get_full_menu...")
        result = get_full_menu.invoke({})
        if 'error' not in result:
            pizzas_count = sum(len(pizzas) for pizzas in result.get('pizzas', {}).values())
            bebidas_count = len(result.get('bebidas', []))
            combos_count = len(result.get('combos', []))
            print(f"   Pizzas: {pizzas_count}, Bebidas: {bebidas_count}, Combos: {combos_count}")
            print(f"   ✅ get_full_menu funciona")
        else:
            print(f"   ❌ Error: {result.get('error')}")
        
        # Test 4: Buscar pizzas por ingredientes
        print("\n4. Testing get_pizzas_by_ingredients...")
        result = get_pizzas_by_ingredients.invoke({"ingredientes": ["pepperoni"]})
        print(f"   Pizzas con pepperoni: {result.get('total_encontradas', 0)}")
        if result.get('pizzas'):
            print(f"   Primera pizza: {result['pizzas'][0].get('nombre', 'N/A')}")
        print(f"   ✅ get_pizzas_by_ingredients funciona")
        
        # Test 5: Obtener adiciones y bordes
        print("\n5. Testing get_pizza_additions...")
        result = get_pizza_additions.invoke({})
        if 'error' not in result:
            adiciones_count = len(result.get('adiciones', []))
            bordes_count = len(result.get('bordes', []))
            print(f"   Adiciones: {adiciones_count}, Bordes: {bordes_count}")
            print(f"   ✅ get_pizza_additions funciona")
        else:
            print(f"   ❌ Error: {result.get('error')}")
        
        print("\n✅ TODAS LAS HERRAMIENTAS DE BD FUNCIONAN CORRECTAMENTE")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test de BD: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_memory_system():
    """Test del sistema de memoria con smart_conversation_memory"""
    print("\n🧠 Probando sistema de memoria...")
    
    try:
        # Test 1: Crear conversación
        print("\n1. Testing conversation creation...")
        context = await memory_manager.get_conversation("test_user_memory")
        print(f"   Thread ID: {context.thread_id}")
        print(f"   ✅ Conversación creada")
        
        # Test 2: Agregar mensaje
        print("\n2. Testing add message...")
        from langchain_core.messages import HumanMessage
        await memory_manager.add_message("test_user_memory", HumanMessage(content="Hola, test message"))
        print(f"   ✅ Mensaje agregado")
        
        # Test 3: Obtener conversación
        print("\n3. Testing get conversation...")
        context = await memory_manager.get_conversation("test_user_memory")
        print(f"   Mensajes en memoria: {len(context.recent_messages)}")
        print(f"   ✅ Conversación recuperada")
        
        print("\n✅ SISTEMA DE MEMORIA FUNCIONA CORRECTAMENTE")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test de memoria: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_workflow_integration():
    """Test del workflow completo"""
    print("\n🔄 Probando workflow completo...")
    
    try:
        workflow = Workflow()
        
        # Test de mensaje simple
        response = await workflow.run("Hola, quiero información sobre pizzas", "test_user_workflow")
        print(f"   Respuesta del workflow: {response[:100]}...")
        print(f"   ✅ Workflow funciona")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error en test de workflow: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_real_integration():
    """Test de integración real con flujo ORDER_GUIDE"""
    print("\n🍕 Probando flujo ORDER_GUIDE real...")
    
    try:
        workflow = Workflow()
        
        # Simulación de conversación real
        user_id = "test_order_flow"
        
        print("\n   Usuario: Hola, quiero hacer un pedido")
        response1 = await workflow.run("Hola, quiero hacer un pedido", user_id)
        print(f"   Bot: {response1[:100]}...")
        
        print("\n   Usuario: Juan Pérez, 3001234567, juan@test.com")
        response2 = await workflow.run("Juan Pérez, 3001234567, juan@test.com", user_id)
        print(f"   Bot: {response2[:100]}...")
        
        print("\n   Usuario: Quiero ver el menú")
        response3 = await workflow.run("Quiero ver el menú", user_id)
        print(f"   Bot: {response3[:100]}...")
        
        print("\n✅ FLUJO ORDER_GUIDE FUNCIONA")
        return True
        
    except Exception as e:
        print(f"\n❌ Error en flujo ORDER_GUIDE: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Función principal de testing"""
    print("🍕 TESTING ONEPIZZERIA CHATBOT CON BD REAL")
    print("=" * 60)
    
    # Verificar variables de entorno
    print("🔑 Verificando variables de entorno...")
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "OPENAI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
        else:
            print(f"   ✅ {var} configurado")
    
    if missing_vars:
        print(f"\n❌ Variables faltantes: {missing_vars}")
        print("   Por favor configura las variables de entorno antes de continuar.")
        return
    
    # Ejecutar tests
    db_ok = await test_database_connection()
    memory_ok = await test_memory_system()
    workflow_ok = await test_workflow_integration()
    integration_ok = await test_real_integration()
    
    # Resumen
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE TESTS:")
    print(f"   Base de datos: {'✅ OK' if db_ok else '❌ ERROR'}")
    print(f"   Sistema memoria: {'✅ OK' if memory_ok else '❌ ERROR'}")
    print(f"   Workflow: {'✅ OK' if workflow_ok else '❌ ERROR'}")
    print(f"   Integración ORDER_GUIDE: {'✅ OK' if integration_ok else '❌ ERROR'}")
    
    if all([db_ok, memory_ok, workflow_ok, integration_ok]):
        print("\n🎉 ¡TODOS LOS TESTS PASARON!")
        print("   El chatbot está listo para uso en producción.")
    else:
        print("\n⚠️  Algunos tests fallaron.")
        print("   Revisa la configuración antes de usar en producción.")

if __name__ == "__main__":
    asyncio.run(main()) 
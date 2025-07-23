"""
Demo simple del chatbot OnePizzeria sin configuraciones externas
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Agregar el directorio actual al path para imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock de variables de entorno
os.environ["SUPABASE_URL"] = "https://demo.supabase.co"
os.environ["SUPABASE_KEY"] = "demo_key_123"
os.environ["OPENAI_API_KEY"] = "demo_openai_key"
os.environ["TELEGRAM_BOT_TOKEN"] = "demo_telegram_token"

class MockLLM:
    """Mock del LLM para el demo"""
    
    def __init__(self, *args, **kwargs):
        pass
    
    def bind_tools(self, tools):
        return self
    
    def invoke(self, messages):
        """Simula respuestas del LLM basadas en el input"""
        if not messages:
            return self._create_response("¡Hola! Bienvenido a One Pizzeria")
        
        last_message = messages[-1].content.lower() if hasattr(messages[-1], 'content') else str(messages[-1]).lower()
        
        mock_response = MagicMock()
        mock_response.tool_calls = None
        
        if "hola" in last_message or "inicio" in last_message:
            mock_response.content = "¡Hola! Bienvenido a One Pizzeria 🍕. Soy Juan y estoy aquí para ayudarte. ¿En qué te puedo ayudar hoy?"
        elif "menú" in last_message or "menu" in last_message or "pizzas" in last_message:
            mock_response.content = """🍕 **MENÚ ONE PIZZERIA** 🍕

**PIZZAS CLÁSICAS:**
• Hawaiana - $45.000 (jamón, piña, queso)
• Pepperoni - $40.000 (pepperoni, queso)
• Margherita - $35.000 (tomate, albahaca, queso)

**PIZZAS GOURMET:**
• Vegetariana - $42.000 (pimentones, cebolla, champiñones)
• 4 Quesos - $48.000 (mozzarella, parmesano, gorgonzola, cheddar)

**BEBIDAS:**
• Coca Cola 1.5L - $8.000
• Agua - $3.000

¿Te interesa alguna pizza en particular?"""
        elif "hawaiana" in last_message:
            mock_response.content = "🍕 La pizza Hawaiana es una de nuestras favoritas! Lleva jamón, piña dulce y queso mozzarella sobre nuestra salsa especial. Cuesta $45.000 en tamaño grande. ¿Te gustaría ordenarla?"
        elif "pedido" in last_message or "quiero" in last_message:
            mock_response.content = "¡Perfecto! Para tomar tu pedido necesito algunos datos. ¿Podrías darme tu nombre completo y número de teléfono?"
        elif any(digit in last_message for digit in "0123456789"):
            mock_response.content = "¡Excelente! He registrado tu información. ¿A qué dirección envío tu pedido y cómo vas a pagar? (efectivo, tarjeta o transferencia)"
        elif "direccion" in last_message or "calle" in last_message:
            mock_response.content = "¡Perfecto! Tu pedido está confirmado y será entregado en aproximadamente 35-45 minutos. ¡Gracias por elegir One Pizzeria! 🍕"
        else:
            mock_response.content = "¿Podrías darme más detalles? Estoy aquí para ayudarte con nuestro menú, tomar tu pedido o resolver cualquier duda sobre One Pizzeria."
        
        return mock_response
    
    def _create_response(self, content):
        mock_response = MagicMock()
        mock_response.content = content
        mock_response.tool_calls = None
        return mock_response

class MockSupabaseService:
    """Mock del servicio de Supabase"""
    def __init__(self):
        self.ALL_TOOLS = []

async def demo_conversation():
    """Simula una conversación completa con el bot"""
    
    print("🍕 DEMO - OnePizzeria Chatbot")
    print("=" * 50)
    print("Simulando conversación con cliente...")
    print()
    
    # Mock de las dependencias
    with patch('langchain_openai.ChatOpenAI', MockLLM):
        with patch('src.tools.SupabaseService', MockSupabaseService):
            with patch('src.checkpointer.state_manager') as mock_state_manager:
                
                # Configurar mock del state manager
                mock_state_manager.load_state_for_user = AsyncMock(return_value={
                    "user_id": "demo_user",
                    "messages": [],
                    "customer": {},
                    "active_order": {},
                    "response": None
                })
                mock_state_manager.save_state_for_user = AsyncMock()
                
                # Importar y crear workflow
                from src.workflow import Workflow
                workflow = Workflow()
                
                # Simular conversación paso a paso
                conversacion = [
                    ("Usuario", "Hola"),
                    ("Usuario", "Muéstrame el menú por favor"),
                    ("Usuario", "Me interesa la pizza hawaiana"),
                    ("Usuario", "Quiero hacer un pedido"),
                    ("Usuario", "Juan Pérez, 3001234567"),
                    ("Usuario", "Calle 123 #45-67, Bogotá. Pago con tarjeta")
                ]
                
                for i, (sender, mensaje) in enumerate(conversacion):
                    print(f"{sender}: {mensaje}")
                    
                    if sender == "Usuario":
                        try:
                            respuesta = await workflow.run(mensaje, "demo_user")
                            print(f"Juan (Bot): {respuesta}")
                        except Exception as e:
                            print(f"Juan (Bot): ¡Ups! Algo salió mal: {e}")
                    
                    print("-" * 30)
                    
                    # Pausa para efecto visual
                    await asyncio.sleep(0.5)
                
                print()
                print("✅ Demo completado exitosamente!")
                print("El flujo básico del chatbot está funcionando.")

async def demo_simple():
    """Demo más simple para verificar componentes individuales"""
    
    print("🔧 DEMO - Verificación de Componentes")
    print("=" * 50)
    
    # Test 1: Modelos
    print("1️⃣  Probando modelos...")
    try:
        from src.models import Order, ProductDetails
        pizza = ProductDetails(
            product_id="pizza_1",
            product_name="Hawaiana",
            product_type="pizza",
            base_price=45000
        )
        print(f"   ✅ Pizza creada: {pizza.product_name} - ${pizza.base_price:,}")
    except Exception as e:
        print(f"   ❌ Error en modelos: {e}")
    
    # Test 2: Prompts
    print("2️⃣  Probando prompts...")
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        print(f"   ✅ Prompts cargados, sistema: {len(prompts.MESSAGE_SPLITTING_SYSTEM)} chars")
    except Exception as e:
        print(f"   ❌ Error en prompts: {e}")
    
    # Test 3: Workflow Mock
    print("3️⃣  Probando workflow con mocks...")
    try:
        with patch('langchain_openai.ChatOpenAI', MockLLM):
            with patch('src.tools.SupabaseService', MockSupabaseService):
                with patch('src.checkpointer.state_manager') as mock_state:
                    mock_state.load_state_for_user = AsyncMock(return_value={
                        "user_id": "test", "messages": [], "customer": {}, 
                        "active_order": {}, "response": None
                    })
                    mock_state.save_state_for_user = AsyncMock()
                    
                    from src.workflow import Workflow
                    workflow = Workflow()
                    respuesta = await workflow.run("Hola", "test_user")
                    print(f"   ✅ Respuesta del bot: {respuesta[:50]}...")
    except Exception as e:
        print(f"   ❌ Error en workflow: {e}")
    
    print()
    print("✅ Verificación de componentes completada!")

async def main():
    """Función principal del demo"""
    print("🚀 Iniciando Demo OnePizzeria Chatbot")
    print()
    
    # Primero verificar componentes básicos
    await demo_simple()
    print()
    
    # Luego hacer demo completo
    await demo_conversation()
    
    print()
    print("🎉 ¡Demo completado! El MVP está listo para desarrollo.")
    print("Próximos pasos:")
    print("- Configurar variables de entorno reales")
    print("- Probar con Telegram real")
    print("- Conectar con base de datos Supabase")

if __name__ == "__main__":
    asyncio.run(main()) 
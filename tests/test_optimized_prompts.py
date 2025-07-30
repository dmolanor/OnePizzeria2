#!/usr/bin/env python3
"""
Test específico para validar los prompts optimizados de One Pizzería

Valida:
- Message splitting con nuevas intenciones
- Tools execution con herramientas inteligentes
- Flujos de personalización optimizados
- Manejo de confirmaciones
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_prompts_structure():
    """Test básico de estructura de prompts"""
    print("🧠 TESTING PROMPTS STRUCTURE")
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        # Test que los prompts principales existen
        required_prompts = [
            'MESSAGE_SPLITTING_SYSTEM',
            'TOOLS_EXECUTION_SYSTEM', 
            'ANSWER_SYSTEM',
            'ORDER_CONFIRMATION_SYSTEM',
            'PERSONALIZATION_DETECTION_SYSTEM',
            'SMART_SUGGESTIONS_SYSTEM',
            'CONTEXTUAL_ERROR_HANDLING',
            'PAYMENT_FLOW_SYSTEM',
            'POST_ORDER_FOLLOW_UP'
        ]
        
        for prompt_name in required_prompts:
            assert hasattr(prompts, prompt_name), f"Missing prompt: {prompt_name}"
            prompt_content = getattr(prompts, prompt_name)
            assert isinstance(prompt_content, str), f"{prompt_name} should be string"
            assert len(prompt_content) > 100, f"{prompt_name} too short"
            print(f"✅ {prompt_name}: OK")
        
        print("\n✅ Todos los prompts principales encontrados")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_message_splitting_enhancements():
    """Test de mejoras en message splitting"""
    print("\n🎯 TESTING MESSAGE SPLITTING ENHANCEMENTS")
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        splitting_system = prompts.MESSAGE_SPLITTING_SYSTEM
        
        # Verificar nuevas intenciones
        new_intents = [
            'personalizacion_productos',
            'modificar_pedido'
        ]
        
        for intent in new_intents:
            assert intent in splitting_system, f"Missing intent: {intent}"
            print(f"✅ Nueva intención '{intent}' encontrada")
        
        # Verificar ejemplos de análisis
        assert 'EJEMPLOS DE ANÁLISIS' in splitting_system
        assert 'RAZONAMIENTO PASO A PASO' in splitting_system
        print("✅ Estructura de razonamiento step-by-step implementada")
        
        # Test de method message_splitting_user
        assert hasattr(prompts, 'message_splitting_user')
        print("✅ Método message_splitting_user existe")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_tools_execution_improvements():
    """Test de mejoras en tools execution"""
    print("\n🛠️ TESTING TOOLS EXECUTION IMPROVEMENTS")  
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        tools_system = prompts.TOOLS_EXECUTION_SYSTEM
        
        # Verificar herramientas inteligentes
        smart_tools = [
            'add_product_to_order_smart',
            'update_product_in_order_smart',
            'get_border_price_by_name',
            'get_adition_price_by_name'
        ]
        
        for tool in smart_tools:
            assert tool in tools_system, f"Missing smart tool: {tool}"
            print(f"✅ Herramienta inteligente '{tool}' documentada")
        
        # Verificar mapeo de intenciones mejorado
        assert 'personalizacion_productos' in tools_system
        assert 'modificar_pedido' in tools_system
        print("✅ Mapeo de nuevas intenciones implementado")
        
        # Verificar ejemplos específicos
        assert 'EJEMPLOS ESPECÍFICOS' in tools_system
        print("✅ Ejemplos específicos incluidos")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_specialized_prompts():
    """Test de prompts especializados nuevos"""
    print("\n🎨 TESTING SPECIALIZED PROMPTS")
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        # Test personalization detection
        detection_system = prompts.PERSONALIZATION_DETECTION_SYSTEM
        assert 'BORDES:' in detection_system
        assert 'ADICIONES:' in detection_system
        assert 'MODIFICACIONES' in detection_system
        print("✅ Sistema de detección de personalizaciones completo")
        
        # Test smart suggestions
        suggestions_system = prompts.SMART_SUGGESTIONS_SYSTEM
        assert 'MOMENTO ADECUADO' in suggestions_system
        assert 'SUGERENCIAS POPULARES' in suggestions_system
        print("✅ Sistema de sugerencias inteligentes completo")
        
        # Test confirmation system
        confirmation_system = prompts.ORDER_CONFIRMATION_SYSTEM
        assert 'RESUMEN DE TU PEDIDO' in confirmation_system
        assert 'VALIDACIONES REQUERIDAS' in confirmation_system
        print("✅ Sistema de confirmación optimizado completo")
        
        # Test error handling
        error_handling = prompts.CONTEXTUAL_ERROR_HANDLING
        assert 'PRODUCTOS NO ENCONTRADOS' in error_handling
        assert 'PERSONALIZACIONES NO DISPONIBLES' in error_handling
        print("✅ Sistema de manejo de errores completo")
        
        # Test payment flow
        payment_flow = prompts.PAYMENT_FLOW_SYSTEM
        assert 'MÉTODOS DE PAGO' in payment_flow
        assert 'FLUJO DE PAGO' in payment_flow
        print("✅ Sistema de flujo de pago completo")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_answer_system_optimization():
    """Test del sistema de respuestas optimizado"""
    print("\n💬 TESTING ANSWER SYSTEM OPTIMIZATION")
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        answer_system = prompts.ANSWER_SYSTEM
        
        # Verificar mejoras clave
        improvements = [
            'PROCESO MENTAL',
            'OBJETIVOS ESCALONADOS',
            'PERSONALIZACIÓN',
            'CONFIRMACIÓN',
            'REGLAS DE ORO',
            'EJEMPLOS DE RESPUESTAS OPTIMIZADAS'
        ]
        
        for improvement in improvements:
            assert improvement in answer_system, f"Missing improvement: {improvement}"
            print(f"✅ Mejora '{improvement}' implementada")
        
        print("✅ Sistema de respuestas completamente optimizado")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_context_methods():
    """Test de métodos de contexto"""
    print("\n🔧 TESTING CONTEXT METHODS")
    print("=" * 60)
    
    try:
        from src.prompts import CustomerServicePrompts
        prompts = CustomerServicePrompts()
        
        # Test métodos principales
        methods = [
            'message_splitting_user',
            'tools_execution_user', 
            'confirmation_user',
            'answer_user'
        ]
        
        for method in methods:
            assert hasattr(prompts, method), f"Missing method: {method}"
            print(f"✅ Método '{method}' existe")
        
        # Test que message_splitting_user funciona básicamente
        # Crear un mock simple de mensaje
        class MockMessage:
            def __init__(self, content):
                self.content = content
        
        test_messages = [MockMessage("Hola")]
        
        result = prompts.message_splitting_user(
            messages=test_messages,
            order_states={"saludo": 0},
            customer_info=None,
            active_order={}
        )
        
        assert isinstance(result, str)
        assert "Hola" in result
        print("✅ message_splitting_user funciona correctamente")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def main():
    """Ejecutar todos los tests de prompts optimizados"""
    print("🚀 TESTING OPTIMIZED PROMPTS SYSTEM")
    print("=" * 60)
    print("Validando mejoras en prompts de One Pizzería...")
    print()
    
    tests = [
        test_prompts_structure,
        test_message_splitting_enhancements,
        test_tools_execution_improvements,
        test_specialized_prompts,
        test_answer_system_optimization,
        test_context_methods
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ {test.__name__} FAILED")
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 RESULTADOS: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 TODOS LOS TESTS DE PROMPTS OPTIMIZADOS PASARON")
        print("✅ Sistema de prompts actualizado correctamente")
        print("✅ Nuevas intenciones implementadas")
        print("✅ Herramientas inteligentes integradas")
        print("✅ Flujos optimizados funcionando")
        print("=" * 60)
        return True
    else:
        print(f"⚠️ {total - passed} tests fallaron")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 
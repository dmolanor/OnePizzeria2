#!/usr/bin/env python3
"""
Test simple para verificar que no hay duplicados
"""

import asyncio
from langchain_core.messages import HumanMessage, AIMessage
from src.memory import memory
from config import supabase

async def test_simple_no_duplicates():
    """Test simple de duplicados usando directamente el sistema de memoria"""
    print("🧪 TEST SIMPLE DE DUPLICADOS")
    print("=" * 40)
    
    test_user_id = "simple_duplicate_test"
    
    # Limpiar datos previos
    try:
        supabase.table("smart_conversation_memory").delete().eq("thread_id", test_user_id).execute()
        print("🧹 Datos previos eliminados")
    except:
        pass
    
    try:
        # Simular guardado de mensajes como lo haría el workflow
        print("\n📝 Guardando mensajes...")
        
        # Mensaje 1: Usuario
        msg1 = HumanMessage(content="Hola")
        await memory.add_message(test_user_id, msg1)
        print("✅ Mensaje 1 guardado: Usuario - Hola")
        
        # Mensaje 2: Agente
        msg2 = AIMessage(content="¡Hola! ¿En qué puedo ayudarte?")
        await memory.add_message(test_user_id, msg2)
        print("✅ Mensaje 2 guardado: Agente - ¡Hola! ¿En qué puedo ayudarte?")
        
        # Intentar guardar el mismo mensaje 1 otra vez (debería evitar duplicado)
        await memory.add_message(test_user_id, msg1)
        print("✅ Mensaje 1 guardado otra vez (debería evitar duplicado)")
        
        # Verificar en BD
        print(f"\n🔍 Verificando en base de datos...")
        db_result = supabase.table("smart_conversation_memory").select("recent_messages").eq("thread_id", test_user_id).execute()
        
        if db_result.data:
            saved_messages = db_result.data[0]['recent_messages']
            print(f"📊 Total mensajes en BD: {len(saved_messages)}")
            
            # Mostrar mensajes
            print(f"\n📋 MENSAJES GUARDADOS:")
            for i, msg in enumerate(saved_messages, 1):
                role_emoji = "👤" if msg['role'] == 'human' else "🤖"
                print(f"   {i}. {role_emoji} {msg['role']}: {msg['content']}")
            
            # Verificar duplicados
            contents = [msg['content'] for msg in saved_messages]
            unique_contents = set(contents)
            
            if len(contents) == len(unique_contents):
                print(f"\n✅ ÉXITO: No hay duplicados")
                return True
            else:
                print(f"\n❌ FALLO: Se encontraron duplicados")
                print(f"   Total mensajes: {len(contents)}")
                print(f"   Mensajes únicos: {len(unique_contents)}")
                return False
        else:
            print("❌ No se encontraron datos en BD")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        # Limpieza
        try:
            supabase.table("smart_conversation_memory").delete().eq("thread_id", test_user_id).execute()
            print(f"\n🧹 Datos de prueba eliminados")
        except:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_simple_no_duplicates())
    
    if success:
        print(f"\n🎉 RESULTADO: Sistema de memoria funciona sin duplicados")
    else:
        print(f"\n💥 RESULTADO: Hay problemas con duplicados") 
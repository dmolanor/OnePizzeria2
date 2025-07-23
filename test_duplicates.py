#!/usr/bin/env python3
"""
Test para identificar y verificar el problema de duplicados en la base de datos
"""

import asyncio
from langchain_core.messages import HumanMessage
from src.workflow import Workflow
from config import supabase

async def test_duplicates():
    """Verificar si se están creando mensajes duplicados"""
    print("🔍 VERIFICANDO PROBLEMA DE DUPLICADOS")
    print("=" * 60)
    
    workflow = Workflow()
    test_user_id = "duplicate_test"
    
    # Limpiar datos previos
    try:
        supabase.table("smart_conversation_memory").delete().eq("thread_id", test_user_id).execute()
        print("🧹 Datos previos eliminados")
    except:
        pass
    
    print("\n📝 PRIMER MENSAJE")
    message1 = "Hola"
    state1 = {
        "messages": [HumanMessage(content=message1)],
        "user_id": test_user_id
    }
    
    try:
        result1 = await workflow.workflow.ainvoke(state1)
        print("✅ Primer mensaje procesado")
        
        # Verificar en BD después del primer mensaje
        db_result = supabase.table("smart_conversation_memory").select("recent_messages").eq("thread_id", test_user_id).execute()
        if db_result.data:
            messages_after_1 = db_result.data[0]['recent_messages']
            print(f"📊 Mensajes en BD después del mensaje 1: {len(messages_after_1)}")
            
            print("📋 DETALLE DESPUÉS DEL MENSAJE 1:")
            for i, msg in enumerate(messages_after_1, 1):
                role_emoji = "👤" if msg['role'] == 'human' else "🤖"
                content_preview = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                print(f"   {i}. {role_emoji} {msg['role']}: {content_preview}")
        
        print(f"\n📝 SEGUNDO MENSAJE")
        message2 = "Quiero una pizza"
        state2 = {
            "messages": [HumanMessage(content=message2)],
            "user_id": test_user_id
        }
        
        result2 = await workflow.workflow.ainvoke(state2)
        print("✅ Segundo mensaje procesado")
        
        # Verificar en BD después del segundo mensaje
        db_result = supabase.table("smart_conversation_memory").select("recent_messages").eq("thread_id", test_user_id).execute()
        if db_result.data:
            messages_after_2 = db_result.data[0]['recent_messages']
            print(f"📊 Mensajes en BD después del mensaje 2: {len(messages_after_2)}")
            
            print("📋 DETALLE DESPUÉS DEL MENSAJE 2:")
            for i, msg in enumerate(messages_after_2, 1):
                role_emoji = "👤" if msg['role'] == 'human' else "🤖"
                content_preview = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
                print(f"   {i}. {role_emoji} {msg['role']}: {content_preview}")
            
            # 🔍 ANÁLISIS DE DUPLICADOS
            print(f"\n🔍 ANÁLISIS DE DUPLICADOS:")
            
            # Contar mensajes por contenido
            content_counts = {}
            for msg in messages_after_2:
                content = msg['content']
                if content in content_counts:
                    content_counts[content] += 1
                else:
                    content_counts[content] = 1
            
            duplicates_found = False
            for content, count in content_counts.items():
                if count > 1:
                    duplicates_found = True
                    print(f"   ❌ DUPLICADO: '{content[:30]}...' aparece {count} veces")
            
            if not duplicates_found:
                print(f"   ✅ No se encontraron duplicados por contenido")
            
            # Verificar orden cronológico
            print(f"\n📅 VERIFICANDO ORDEN CRONOLÓGICO:")
            expected_order = ["Hola", "Quiero una pizza"]
            user_messages = [msg for msg in messages_after_2 if msg['role'] == 'human']
            
            if len(user_messages) >= 2:
                if (expected_order[0] in user_messages[0]['content'] and 
                    expected_order[1] in user_messages[-1]['content']):
                    print(f"   ✅ Orden cronológico correcto")
                else:
                    print(f"   ❌ Orden cronológico incorrecto")
                    print(f"   Esperado: {expected_order}")
                    print(f"   Encontrado: {[msg['content'][:20] for msg in user_messages]}")
            
            return not duplicates_found
                
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
    success = asyncio.run(test_duplicates())
    
    if success:
        print(f"\n✅ RESULTADO: No hay problemas de duplicados")
    else:
        print(f"\n❌ RESULTADO: Se encontraron duplicados en la base de datos")
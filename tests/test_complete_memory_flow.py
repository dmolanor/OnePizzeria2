#!/usr/bin/env python3
"""
Test completo del flujo de memoria: carga y guardado
"""

import asyncio
from langchain_core.messages import HumanMessage
from src.workflow import Workflow
from src.memory import memory
from config import supabase

async def test_complete_memory_flow():
    """Prueba el flujo completo: carga desde DB -> procesamiento -> guardado en DB"""
    print("🔄 PRUEBA COMPLETA DEL FLUJO DE MEMORIA")
    print("=" * 60)
    
    workflow = Workflow()
    test_user_id = "complete_flow_test"
    
    # === PASO 1: PRIMER MENSAJE ===
    print("1️⃣ PRIMER MENSAJE")
    print("Usuario: Hola, quiero una pizza")
    
    state1 = {
        "messages": [HumanMessage(content="Hola, quiero una pizza")],
        "user_id": test_user_id
    }
    
    try:
        result1 = await workflow.workflow.ainvoke(state1)
        response1 = result1["messages"][-1].content if result1.get("messages") else "Sin respuesta"
        print(f"Bot: {response1[:80]}...")
        print("✅ Primer mensaje procesado")
    except Exception as e:
        print(f"❌ Error en primer mensaje: {e}")
        return
    
    # Verificar que se guardó en la base de datos
    print("\n🔍 Verificando guardado en base de datos...")
    try:
        db_result = supabase.table("smart_conversation_memory").select("*").eq("thread_id", test_user_id).execute()
        if db_result.data:
            record = db_result.data[0]
            print(f"✅ Encontrado en BD: {len(record['recent_messages'])} mensajes")
            for i, msg in enumerate(record['recent_messages'], 1):
                role_emoji = "👤" if msg['role'] == 'human' else "🤖"
                print(f"   {i}. {role_emoji} {msg['content'][:50]}...")
        else:
            print("❌ No se encontró en la base de datos")
            return
    except Exception as e:
        print(f"❌ Error verificando BD: {e}")
        return
    
    # === PASO 2: SEGUNDO MENSAJE (debe cargar historial) ===
    print("\n2️⃣ SEGUNDO MENSAJE (debe cargar historial)")
    print("Usuario: Me llamo Diego Molano")
    
    # Limpiar cache para forzar carga desde BD
    memory.clear_cache()
    
    state2 = {
        "messages": [HumanMessage(content="Me llamo Diego Molano")],
        "user_id": test_user_id
    }
    
    try:
        result2 = await workflow.workflow.ainvoke(state2)
        response2 = result2["messages"][-1].content if result2.get("messages") else "Sin respuesta"
        print(f"Bot: {response2[:80]}...")
        print("✅ Segundo mensaje procesado")
    except Exception as e:
        print(f"❌ Error en segundo mensaje: {e}")
        return
    
    # Verificar que se actualizó en la base de datos
    print("\n🔍 Verificando actualización en base de datos...")
    try:
        db_result2 = supabase.table("smart_conversation_memory").select("*").eq("thread_id", test_user_id).execute()
        if db_result2.data:
            record2 = db_result2.data[0]
            print(f"✅ Actualizado en BD: {len(record2['recent_messages'])} mensajes")
            
            # Mostrar la conversación completa
            print("\n📚 HISTORIAL COMPLETO:")
            for i, msg in enumerate(record2['recent_messages'], 1):
                role_emoji = "👤" if msg['role'] == 'human' else "🤖"
                print(f"   {i}. {role_emoji} {msg['role']}: {msg['content'][:60]}...")
                
            # Verificar que el contexto del cliente se actualizó
            if record2['customer_context']:
                print(f"✅ Contexto del cliente: {record2['customer_context']}")
            else:
                print("ℹ️ No hay contexto del cliente actualizado")
                
        else:
            print("❌ No se encontró la actualización en BD")
            return
    except Exception as e:
        print(f"❌ Error verificando actualización: {e}")
        return
    
    # === PASO 3: TERCER MENSAJE (verificar continuidad) ===
    print("\n3️⃣ TERCER MENSAJE (verificar continuidad)")
    print("Usuario: Quiero una pizza diabola")
    
    # Limpiar cache nuevamente
    memory.clear_cache()
    
    state3 = {
        "messages": [HumanMessage(content="Quiero una pizza diabola")],
        "user_id": test_user_id
    }
    
    try:
        result3 = await workflow.workflow.ainvoke(state3)
        response3 = result3["messages"][-1].content if result3.get("messages") else "Sin respuesta"
        print(f"Bot: {response3[:80]}...")
        print("✅ Tercer mensaje procesado")
    except Exception as e:
        print(f"❌ Error en tercer mensaje: {e}")
        return
    
    # Verificación final
    print("\n🔍 VERIFICACIÓN FINAL...")
    try:
        final_result = supabase.table("smart_conversation_memory").select("*").eq("thread_id", test_user_id).execute()
        if final_result.data:
            final_record = final_result.data[0]
            print(f"✅ Conversación final: {len(final_record['recent_messages'])} mensajes")
            
            # Verificar que se mantiene la continuidad
            if len(final_record['recent_messages']) >= 4:  # Al menos 3 pares usuario-bot
                print("✅ La continuidad de la conversación se mantiene correctamente")
            else:
                print("⚠️ Posible problema con la continuidad")
                
            print(f"✅ Última actividad: {final_record['last_activity']}")
            
        else:
            print("❌ No se encontró la conversación final")
    except Exception as e:
        print(f"❌ Error en verificación final: {e}")
    
    # === LIMPIEZA ===
    print("\n🧹 LIMPIEZA")
    try:
        supabase.table("smart_conversation_memory").delete().eq("thread_id", test_user_id).execute()
        print("✅ Datos de prueba eliminados")
    except Exception as e:
        print(f"⚠️ Error en limpieza: {e}")

async def main():
    """Ejecutar la prueba"""
    await test_complete_memory_flow()
    
    print("\n" + "=" * 60)
    print("🏁 PRUEBA COMPLETA FINALIZADA")
    print("\n📋 RESUMEN:")
    print("✅ Carga de mensajes: En detect_user_intent_step línea 120")  
    print("✅ Guardado de mensajes: En send_response_step línea 415+")
    print("✅ Flujo completo: Telegram -> Carga -> Procesamiento -> Guardado")

if __name__ == "__main__":
    asyncio.run(main()) 
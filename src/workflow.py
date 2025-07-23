import json
import re
from typing import Annotated, Any, Dict, List, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from config import supabase
from src.checkpointer import state_manager
from src.prompts import CustomerServicePrompts
from src.state import ChatState, Order, ProductDetails
from src.tools import ALL_TOOLS


class Workflow:
    def __init__(self):
        self.supabase = supabase
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
        )
        self.prompts = CustomerServicePrompts()
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """Build the workflow graph with async support."""
        graph = StateGraph(ChatState)
        
        # Add nodes with async functions
        graph.add_node("detect_intent", self.detect_user_intent_step)
        graph.add_node("retrieve_data", self.retrieve_data_step)
        graph.add_node("tools", ToolNode(ALL_TOOLS))
        graph.add_node("process_results", self.process_tool_results_step)
        graph.add_node("send_response", self.send_response_step)
        graph.add_node("save_memory", self.save_memory_step)
        
        # Set up the flow - LINEAR PROGRESSION
        graph.set_entry_point("detect_intent")
        
        # After intent detection, decide next step
        graph.add_conditional_edges(
            "detect_intent",
            self.should_continue_after_intent,
            {
                "retrieve": "retrieve_data",
                "send": "send_response"
            }
        )
        graph.add_conditional_edges(
            "retrieve_data",
            self.should_use_tools,
            "retrieve_data",
            self.should_use_tools,
            {
                "tools": "tools",
                "send": "send_response"
            }
        )
        graph.add_edge("tools", "process_results")  # After tools, process results
        graph.add_node("process_results", self.process_tool_results_step)
        graph.add_conditional_edges(
            "process_results",
            self.should_continue_processing,
            {
                "continue": "retrieve_data",  # Más elementos en divided_message
                "send": "send_response"       # No más elementos, ir a respuesta
            }
        )
        graph.add_edge("send_response", "save_memory")  # 📤 Always save after response
        graph.add_edge("save_memory", END)  # 📤 End after saving
        
        # Compile with async support
        return graph.compile()

    async def detect_user_intent_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Detect user intent from message."""
        try:
            print(f"=== DETECT_USER_INTENT_STEP START ===")
            print(f"State received: {state}")
            print(f"State keys: {list(state.keys())}")
            
            if "messages" not in state or not state["messages"]:
                print("ERROR: No messages in state!")
                return {"divided_message": []}
            
            print(f"Messages in state: {len(state['messages'])}")
            print(f"Last message: {state['messages'][-1]}")
            print(f"Dividing message and identifying intent: {state['messages'][-1].content}")
            
            user_id = state["user_id"]
            print(f"User ID: {user_id}")
            
            # Get existing order states from previous state or initialize
            existing_order_states = state.get("order_states", {
                "saludo": 0,
                "registro_datos_personales": 0,
                "registro_direccion": 0,
                "consulta_menu": 0,
                "crear_pedido": 0,
                "seleccion_productos": 0,
                "confirmacion": 0,
                "finalizacion": 0,
                "general": 0
            })
            print(f"Existing order states: {existing_order_states}")
            
            # Check if user exists in database and update states accordingly
            try:
                customer_result = supabase.table("clientes").select("*").eq("id", user_id).execute()
                if customer_result.data:
                    customer = customer_result.data[0]
                    print(f"Customer found: {customer}")
                    
                    # Update states based on existing customer data
                    if customer.get("nombre_completo") and customer.get("telefono"):
                        existing_order_states["registro_datos_personales"] = 2
                        print("Set registro_datos_personales to completed (2)")
                    
                    if customer.get("direccion"):
                        existing_order_states["registro_direccion"] = 2
                        print("Set registro_direccion to completed (2)")
                else:
                    customer = None
                    print("Customer not found in database")
            except Exception as e:
                print(f"Error checking customer: {e}")
                customer = None
            
            new_message = state["messages"][-1].content if state["messages"] else ""
            print(f"New message content: {new_message}")
            
            # Get complete state for context (commented out for now)
            complete_state = await state_manager.load_state_for_user(user_id, new_message)
            #complete_state = {"messages": []}
            print(f"Complete state: {complete_state}")
            
            context = [
                SystemMessage(content=self.prompts.MESSAGE_SPLITTING_SYSTEM),
                HumanMessage(content=self.prompts.message_splitting_user(
                    messages=state["messages"],
                    order_states=existing_order_states,
                    customer_info=customer,
                    active_order=state.get("active_order", {})
                ))
            ]
            print(f"Context created with {len(context)} messages")
            
            response = await self.llm.ainvoke(context)
            print(f"LLM response received: {response.content}")
            
            raw = response.content
            if not raw.strip():
                print("ERROR: Empty response content")
                raise ValueError("Response content is empty or whitespace")
            
            if raw.startswith("```json") or raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\n?", "", raw)
                raw = re.sub(r"\n?```$", "", raw)
            
            print(f"Raw content after cleaning: {raw}")
            
            try:
                divided = json.loads(raw)
                print(f"JSON parsed successfully: {divided}")
            except json.JSONDecodeError as json_err:
                print(f"JSON parsing error: {json_err}")
                print(f"Raw content was: {repr(raw)}")
                return {"divided_message": [], "order_states": existing_order_states}
            
            # Update states based on current message intents
            for i, section in enumerate(divided):
                print(f"Processing section {i}: {section}")
                intent = section.get("intent", "unknown")
                if intent in existing_order_states:
                    # Only set to 1 (in progress) if not already completed (2)
                    if existing_order_states[intent] != 2:
                        existing_order_states[intent] = 1
                        print(f"Set {intent} to in progress (1)")
                    else:
                        print(f"{intent} already completed (2), keeping status")
                        
                    # Mark saludo as completed immediately if detected
                    if intent == "saludo":
                        existing_order_states["saludo"] = 2
                        print(f"Marked saludo as completed (2)")
                        
                    # Auto-trigger crear_pedido for product selection if no active order
                    elif intent == "seleccion_productos":
                        # Check if we need to create an order first
                        if existing_order_states.get("crear_pedido", 0) == 0:
                            existing_order_states["crear_pedido"] = 1
                            print(f"Auto-triggered crear_pedido for product selection")
                        
                else:
                    existing_order_states["general"] = 1
            
            # 🚫 REMOVED MANUAL MESSAGE COMBINATION - LangGraph handles this automatically
            # The ChatState annotation already concatenates messages, so we don't need to manually combine them
            
            result = {
                "divided_message": divided,
                "order_states": existing_order_states,
                "customer": customer,
                # No manual message manipulation - let LangGraph handle it
                "active_order": state.get("active_order", {}),  # Preserve active_order
                # Individual state fields for ChatState compatibility
                "saludo": existing_order_states.get("saludo", 0),
                "registro_datos_personales": existing_order_states.get("registro_datos_personales", 0),
                "registro_direccion": existing_order_states.get("registro_direccion", 0),
                "consulta_menu": existing_order_states.get("consulta_menu", 0),
                "crear_pedido": existing_order_states.get("crear_pedido", 0),
                "seleccion_productos": existing_order_states.get("seleccion_productos", 0),
                "confirmacion": existing_order_states.get("confirmacion", 0),
                "finalizacion": existing_order_states.get("finalizacion", 0),
                "general": existing_order_states.get("general", 0)
            }
            print(f"=== DETECT_USER_INTENT_STEP END ===")
            print(f"Returning order_states: {existing_order_states}")
            return result
            
        except Exception as e:
            import traceback
            print(f"ERROR in detect_user_intent_step: {e}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            # Return existing states to avoid reset
            existing_states = state.get("order_states", {})
            return {
                "divided_message": [], 
                "order_states": existing_states,
                "active_order": state.get("active_order", {}),  # Preserve active_order
                # Individual state fields for ChatState compatibility
                "saludo": existing_states.get("saludo", 0),
                "registro_datos_personales": existing_states.get("registro_datos_personales", 0),
                "registro_direccion": existing_states.get("registro_direccion", 0),
                "consulta_menu": existing_states.get("consulta_menu", 0),
                "crear_pedido": existing_states.get("crear_pedido", 0),
                "seleccion_productos": existing_states.get("seleccion_productos", 0),
                "confirmacion": existing_states.get("confirmacion", 0),
                "finalizacion": existing_states.get("finalizacion", 0),
                "general": existing_states.get("general", 0)
            }
    
    async def retrieve_data_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve relevant data based on user intent."""
        from datetime import datetime
        
        print(f"Retrieving data based on divided messages... {state['divided_message']}")
        
        if not state["divided_message"]:
            print("No divided messages to process.")
            return {"divided_message": []}
        
        # Get current section to process
        section = state["divided_message"].pop()
        user_id = state.get("user_id", "")
        
        print(f"Processing section: {section}")
        print(f"User ID: {user_id}")
        
        # Get existing order from state or create new one
        active_order = state.get("active_order", {
            "order_id": f"order_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        # Create enhanced prompt with user context
        enhanced_user_prompt = f"""
        INFORMACIÓN DEL USUARIO:
        - User ID: {user_id}
        - Pedido actual: {active_order.get("order_items", [])}
        
        SECCIÓN A PROCESAR:
        - Intent: {section["intent"]}
        - Action: {section["action"]}
        
        INSTRUCCIONES ESPECÍFICAS:
        
        Si es "registro_datos_personales":
        - Extrae nombre completo y teléfono del action
        - Usa create_client con formato: {{"id": "{user_id}", "nombre_completo": "nombre", "telefono": "numero"}}
        
        Si es "registro_direccion":
        - Extrae la dirección del action  
        - Usa update_client con formato: {{"id": "{user_id}", "direccion": "direccion_completa"}}
        
        Si es "crear_pedido":
        - SIEMPRE usa create_order para crear un pedido en pedidos_activos
        - Usa create_order con formato: {{"cliente_id": "{user_id}", "items": [], "total": 0.0, "direccion_entrega": "direccion_del_cliente"}}
        - CRÍTICO: Esto debe ejecutarse ANTES de agregar productos
        
        Si es "seleccion_productos":
        - PRIMERO: Verifica si existe pedido activo con get_active_order_by_client({{"cliente_id": "{user_id}"}})
        - Si NO existe pedido activo: USA create_order PRIMERO
        - LUEGO: Si menciona pizza: usa get_pizza_by_name con name="nombre_pizza_exacto"
        - LUEGO: Si menciona bebida: usa get_beverage_by_name con name="nombre_bebida_exacto"
        - DESPUÉS de obtener productos: USA update_order para agregar al pedido activo
        
        Si es "confirmacion":
        - Si confirma pedido y hay productos: usa update_order para actualizar dirección y método de pago
        - IMPORTANTE: Solo actualizar pedido cuando el usuario CONFIRME explícitamente
        
        Si es "finalizacion":
        - Si el usuario proporciona método de pago: usa finish_order con {{"cliente_id": "{user_id}"}}
        - Esto moverá el pedido de activos a finalizados
        
        FLUJO CRÍTICO PARA PRODUCTOS:
        1. Verificar pedido activo (get_active_order_by_client)
        2. Si no existe → Crear pedido (create_order)
        3. Buscar producto (get_pizza_by_name/get_beverage_by_name)
        4. Actualizar pedido con producto (update_order)
        
        RECUERDA: Extrae la información específica del texto del action, no uses argumentos vacíos.
        """
        
        # Create context with enhanced instructions
        context = [
            SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
            HumanMessage(content=enhanced_user_prompt)
        ]
        
        # Handle different intent types
        if section["intent"] == "confirmacion":
            print("🔄 Detected confirmation intent - handling order confirmation")
            confirmation_result = await self._handle_order_confirmation(state, section)
            # 🚫 REMOVED MANUAL MESSAGE ADDITION - LangGraph handles this automatically
            updated_state = {"messages": confirmation_result["messages"]}  # Only return new messages
        else:   
            print(f"Sending enhanced prompt to LLM with tools...")
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(context)
            
            print(f"Response retrieve_data_step: {response}")
            # 🚫 REMOVED MANUAL MESSAGE ADDITION - LangGraph handles this automatically
            updated_state = {"messages": [response]}  # Only return the new message
            
            # Check for tool calls
            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"🔧 USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")
                # Log the tool arguments for debugging
                for tool_call in response.tool_calls:
                    print(f"Tool: {tool_call['name']}, Args: {tool_call['args']}")
                    
                    # If it's a product search, we'll get the result and add to order
                    if tool_call['name'] in ['get_pizza_by_name', 'get_beverage_by_name']:
                        print(f"Product search detected, will add to order after tool execution")
                    elif tool_call['name'] == 'create_order':
                        print(f"🎯 Order creation detected - this will create pedido_activo")
                    elif tool_call['name'] == 'get_active_order_by_client':
                        print(f"🔍 Checking for existing active order")
            else:
                print("ℹ️  No tools called for this section")
        
        # Preserve active_order in state
        updated_state["active_order"] = active_order
        
        # Also preserve order_states if they exist
        if "order_states" in state:
            updated_state["order_states"] = state["order_states"]
        
        return updated_state
    
    async def save_memory_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """📤 FINAL NODE: Save complete conversation to memory database."""
        try:
            user_id = state["user_id"]
            messages = state.get("messages", [])
            
            print(f"💾 SAVING COMPLETE CONVERSATION TO MEMORY")
            print(f"   - User ID: {user_id}")
            print(f"   - Total messages to save: {len(messages)}")
            
            # 🔍 IDENTIFICAR MENSAJES NUEVOS QUE NO ESTÁN EN BD
            from src.memory import memory

            # Obtener conversación actual de la BD para comparar
            existing_context = await memory.get_conversation(user_id)
            existing_messages = existing_context.recent_messages
            existing_count = len(existing_messages)
            
            print(f"   - Mensajes ya en BD: {existing_count}")
            print(f"   - Mensajes en estado actual: {len(messages)}")
            
            # 📝 GUARDAR SOLO LOS MENSAJES NUEVOS (comparación por contenido)
            # Crear set de contenidos existentes para comparación rápida
            existing_contents = set()
            for existing_msg in existing_messages:
                existing_contents.add(f"{existing_msg['role']}:{existing_msg['content']}")
            
            new_messages_to_save = []
            for message in messages:
                role = "human" if hasattr(message, '__class__') and 'Human' in str(message.__class__) else "assistant"
                message_key = f"{role}:{message.content}"
                
                # Solo agregar si no existe ya en la BD
                if message_key not in existing_contents:
                    new_messages_to_save.append(message)
                    existing_contents.add(message_key)  # Evitar duplicados en esta sesión también
            
            print(f"   - Mensajes nuevos a guardar: {len(new_messages_to_save)}")
            
            if new_messages_to_save:
                # Guardar cada mensaje nuevo individualmente
                for i, message in enumerate(new_messages_to_save):
                    try:
                        await memory.add_message(user_id, message)
                        role = "👤 Usuario" if hasattr(message, '__class__') and 'Human' in str(message.__class__) else "🤖 Agente"
                        content_preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
                        print(f"   ✅ Guardado {i+1}/{len(new_messages_to_save)}: {role} - {content_preview}")
                    except Exception as msg_error:
                        print(f"   ❌ Error guardando mensaje {i+1}: {msg_error}")
            else:
                print(f"   ℹ️ No hay mensajes nuevos que guardar (todos ya existen)")
            
            # 🔄 ACTUALIZAR CONTEXTO DEL CLIENTE Y PEDIDO
            try:
                # Update customer context if we have relevant info
                if state.get("customer") and state["customer"].get("nombre_completo"):
                    await memory.update_customer_context(
                        user_id, 
                        "customer_name", 
                        state["customer"]["nombre_completo"]
                    )
                    print(f"   ✅ Contexto del cliente actualizado")
                
                # Update order context if we have an active order
                if state.get("active_order") and state["active_order"].get("order_items"):
                    await memory.update_customer_context(
                        user_id,
                        "current_order",
                        state["active_order"]
                    )
                    print(f"   ✅ Contexto del pedido actualizado")
            except Exception as context_error:
                print(f"   ⚠️ Error actualizando contexto: {context_error}")
            
            print(f"✅ Conversación completa guardada para usuario {user_id}")
            
            # Return the state unchanged (this is the final node)
            return state
            
        except Exception as e:
            print(f"⚠️ Error saving conversation to memory: {e}")
            import traceback
            print(f"Full traceback:\n{traceback.format_exc()}")
            # Return state even if saving fails (don't break the workflow)
            return state
    
    async def send_response_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and format response to user."""
        user_id = state["user_id"]
        new_message = state["messages"][-1] if state["messages"] else None
        
        if new_message:
            user_input = new_message.content
        else:
            user_input = ""
        
        # Get existing order states (preserve from previous steps)
        order_states = state.get("order_states", {
            "saludo": 0,
            "registro_datos_personales": 0,
            "registro_direccion": 0,
            "consulta_menu": 0,
            "seleccion_productos": 0,
            "confirmacion": 0,
            "finalizacion": 0,
            "general": 0
        })
        
        # Get active order information
        active_order = state.get("active_order", {"order_items": [], "order_total": 0.0})
        order_items = active_order.get("order_items", [])
        order_total = active_order.get("order_total", 0.0)
        
        messages = state.get("messages", [])
        
        # Look for successful tool executions in recent messages and update states
        for message in reversed(messages[-10:]):  # Check last 10 messages
            if hasattr(message, "content") and isinstance(message.content, str):
                content = message.content.lower()
                if "exitosamente" in content or "success" in content:
                    # Try to determine which state was completed based on content
                    if "cliente" in content:
                        if "creado" in content or "actualizado" in content:
                            order_states["registro_datos_personales"] = 2
                            print("Marked registro_datos_personales as completed (2)")
                            if "direccion" in content or "dirección" in content:
                                order_states["registro_direccion"] = 2
                                print("Marked registro_direccion as completed (2)")
                    elif "pedido" in content:
                        if "creado" in content:
                            order_states["seleccion_productos"] = 2
                            print("Marked seleccion_productos as completed (2)")
                        elif "finalizado" in content:
                            order_states["finalizacion"] = 2
                            print("Marked finalizacion as completed (2)")
        
        # Mark saludo as completed if it was detected but not yet marked
        if order_states.get("saludo", 0) == 1:
            order_states["saludo"] = 2
            print("Marking saludo as completed (2) in send_response_step")
        
        # Determine the next incomplete state to progress to
        next_incomplete_state = self._get_next_incomplete_state(order_states, order_items)
        
        # Build context based on current state and next action needed
        print(f"📊 ANTES DE BUILD_CONVERSATION_CONTEXT:")
        print(f"   - Total mensajes en estado: {len(messages)}")
        for i, msg in enumerate(messages):
            role = "👤 Usuario" if hasattr(msg, '__class__') and 'Human' in str(msg.__class__) else "🤖 Agente"
            content_preview = msg.content[:30] + "..." if len(msg.content) > 30 else msg.content
            print(f"   {i+1}. {role}: {content_preview}")
        
        context = self._build_conversation_context(state)
        if context is None:
            context = []
        
        # Add order information to context if there are products
        if len(order_items) > 0:
            products_summary = []
            for item in order_items:
                products_summary.append(f"- {item['product_name']} (${item['total_price']})")
            
            context.append(
                SystemMessage(
                    content=f"PRODUCTOS EN EL PEDIDO ACTUAL:\n" + "\n".join(products_summary) + 
                           f"\nTOTAL: ${order_total}\n\n"
                           "IMPORTANTE: Muestra estos productos al cliente y confirma si están correctos."
                )
            )
        
        # Add guidance for next steps based on incomplete states
        if next_incomplete_state:
            context.append(
                SystemMessage(
                    content=self._get_next_step_guidance(next_incomplete_state, order_states, order_items)
                )
            )
        else:
            # All required states completed
            context.append(
                SystemMessage(
                    content="ESTADO DEL PEDIDO: Todos los datos están completos. "
                           "Muestra el resumen final con productos y total, luego solicita método de pago."
                )
            )
        
        response = await self.llm.ainvoke(context)
        
        print(f"Response: {response.content}")
        print(f"Final order states: {order_states}")
        print(f"Next incomplete state: {next_incomplete_state}")
        
        # NOTE: Memory saving moved to dedicated final node
        
        # 🚫 REMOVED MANUAL MESSAGE ADDITION - LangGraph handles this automatically
        
        return {
            "messages": [response],  # Only return the new response message
            "order_states": order_states,  # Preserve states
            "active_order": active_order,   # Preserve active order
            # Individual state fields for ChatState compatibility
            "saludo": order_states.get("saludo", 0),
            "registro_datos_personales": order_states.get("registro_datos_personales", 0),
            "registro_direccion": order_states.get("registro_direccion", 0),
            "consulta_menu": order_states.get("consulta_menu", 0),
            "crear_pedido": order_states.get("crear_pedido", 0),
            "seleccion_productos": order_states.get("seleccion_productos", 0),
            "confirmacion": order_states.get("confirmacion", 0),
            "finalizacion": order_states.get("finalizacion", 0),
            "general": order_states.get("general", 0)
        }
    
    def _get_next_incomplete_state(self, order_states: Dict[str, int], order_items: List) -> str:
        """Determine the next incomplete state that needs to be addressed."""
        # Define the order of required states
        required_states = [
            "saludo",
            "registro_datos_personales", 
            "registro_direccion",
            "crear_pedido",
            "seleccion_productos",
            "confirmacion",
            "finalizacion"
        ]
        
        print(f"🔍 Checking states for next incomplete: {order_states}")
        print(f"📦 Order items count: {len(order_items)}")
        
        for state_name in required_states:
            current_value = order_states.get(state_name, 0)
            print(f"  - {state_name}: {current_value}")
            
            if current_value != 2:  # Not completed
                # Special logic for some states
                if state_name == "crear_pedido":
                    if len(order_items) == 0 and current_value == 0:
                        print(f"🎯 Next state: {state_name} (no order created yet)")
                        return state_name
                    elif current_value == 1:
                        print(f"🔄 {state_name} in progress, continuing...")
                        continue
                elif state_name == "seleccion_productos":
                    if len(order_items) == 0:
                        # If no order created yet, need to create order first
                        if order_states.get("crear_pedido", 0) != 2:
                            print(f"🎯 Next state: crear_pedido (needed before selecting products)")
                            return "crear_pedido"
                        else:
                            print(f"🎯 Next state: {state_name} (no products selected)")
                            return state_name
                    else:
                        # If we have products, mark this as completed
                        print(f"✅ {state_name} should be completed (has {len(order_items)} products)")
                        continue
                elif state_name == "confirmacion":
                    if len(order_items) > 0 and order_states.get("seleccion_productos", 0) == 2:
                        print(f"🎯 Next state: {state_name} (ready for confirmation)")
                        return state_name
                    else:
                        continue
                else:
                    print(f"🎯 Next state: {state_name}")
                    return state_name
        
        print("✅ All states completed")
        return None  # All states completed
    
    def _get_next_step_guidance(self, next_state: str, order_states: Dict[str, int], order_items: List) -> str:
        """Get guidance message for the next step in the order process."""
        guidance_map = {
            "saludo": "PRÓXIMO PASO: Saluda cordialmente al cliente si aún no lo has hecho.",
            
            "registro_datos_personales": "PRÓXIMO PASO: El cliente ya está registrado, no pidas datos personales nuevamente.",
            
            "registro_direccion": "PRÓXIMO PASO: El cliente ya tiene dirección registrada, no la menciones a menos que sea necesario para el registro.",
            
            "crear_pedido": "PRÓXIMO PASO: El cliente quiere hacer un pedido. Crea un pedido activo en la base de datos.",
            
            "seleccion_productos": "PRÓXIMO PASO: El cliente necesita seleccionar productos. Pregunta qué le gustaría ordenar o muestra opciones del menú.",
            
            "confirmacion": f"PRÓXIMO PASO: El cliente tiene {len(order_items)} productos seleccionados. Muestra el resumen y solicita confirmación del pedido.",
            
            "finalizacion": "PRÓXIMO PASO: El pedido está confirmado. Solicita método de pago y finaliza el proceso."
        }
        
        return guidance_map.get(next_state, "PRÓXIMO PASO: Continúa con el proceso de pedido.")
    
    def _mark_state_completed(self, state: Dict[str, Any], intent: str) -> Dict[str, Any]:
        """Mark a specific intent state as completed (2)."""
        order_states = state.get("order_states", {})
        if intent in order_states:
            order_states[intent] = 2
            print(f"Marked {intent} as completed (2)")
        return order_states
    
    def _build_conversation_context(self, state: Dict[str, Any]) -> list:
        """Build conversation context for LLM."""
        context = []
        
        context.append(SystemMessage(content=self.prompts.ANSWER_SYSTEM))
        user_id = state["user_id"]
        context.append(
            SystemMessage(
                content=f"IMPORTANTE: EL user_id de este cliente es {user_id}. "
                        "Usar siempre user_id para utilizar herramientas que lo requieran"
            )
        )
        if state["order_states"]["registro_datos_personales"] == 2:
            context.append(
                SystemMessage(
                    content=f"El cliente ya está registrado, no pidas datos personales nuevamente."
                )
            )
        else:
            context.append(
                SystemMessage(
                    content=f"El cliente no está registrado, pide datos personales."
                )
            )
        if state.get("customer"):
            context.append(
                SystemMessage(
                    content=f"Esta es la información actual del cliente: {state['customer']}"
                )
            )
        
        context.extend(state["messages"])
        
        return context
        
    
    def should_continue_after_intent(self, state: Dict[str, Any]) -> Literal["retrieve", "send"]:
        """Determine if we should continue processing or send response after intent detection."""
        divided_message = state.get("divided_message", [])
        print(f"After intent detection, remaining messages: {divided_message}")
        
        if not divided_message:
            print("No divided messages to process, going directly to send response.")
            return "send"
        return "retrieve"

    def should_continue_after_processing(self, state: Dict[str, Any]) -> Literal["retrieve", "send"]:
        """Determine if we should continue processing more messages or send response."""
        divided_message = state.get("divided_message", [])
        print(f"After processing results, remaining messages: {len(divided_message)}")
        
        if divided_message:
            print("More messages to process, continuing with retrieve_data...")
            return "retrieve"
        else:
            print("No more messages to process, sending response...")
            return "send"

    def should_use_tools(self, state: Dict[str, Any]) -> Literal["tools", "send"]:
        """Determine if we need to use tools based on the last message."""
        messages = state.get("messages", [])
        if not messages:
            return "send"
        
        last_message = messages[-1]
        
        # Check if the last message has tool calls
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            print(f"🔧 Found tool calls: {[tc['name'] for tc in last_message.tool_calls]}")
            return "tools"
        
        # If no tool calls, go directly to send response
        print("ℹ️ No tool calls needed, going to send response")
        return "send"

    def should_continue_processing(self, state: Dict[str, Any]) -> Literal["continue", "send"]:
        """Determine if we should continue processing divided_message or send response."""
        divided_message = state.get("divided_message", [])
        
        if divided_message:
            print(f"📋 Still have {len(divided_message)} sections to process, continuing...")
            return "continue"
        else:
            print("✅ All sections processed, going to send response")
            return "send"

    async def process_tool_results_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool execution results and sync with pedidos_activos."""
        from datetime import datetime
        
        print(f"=== PROCESSING TOOL RESULTS ===")
        
        messages = state.get("messages", [])
        user_id = state.get("user_id", "unknown")
        
        # Get existing active_order or create new one with proper structure
        active_order_data = state.get("active_order", {
            "order_id": f"order_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        # Get existing order_states and preserve them
        order_states = state.get("order_states", {
            "saludo": 0,
            "registro_datos_personales": 0,
            "registro_direccion": 0,
            "consulta_menu": 0,
            "crear_pedido": 0,
            "seleccion_productos": 0,
            "confirmacion": 0,
            "finalizacion": 0,
            "general": 0
        })
        
        print(f"Current order state: {len(active_order_data.get('order_items', []))} items, total: ${active_order_data.get('order_total', 0)}")
        print(f"Current order_states: {order_states}")
        
        # Track actions completed in this step
        products_added = False
        order_created = False
        order_updated = False
        order_finalized = False
        
        # Look for ToolMessage in recent messages
        for message in reversed(messages[-5:]):  # Check last 5 messages
            if hasattr(message, '__class__') and 'ToolMessage' in str(message.__class__):
                print(f"🔧 Processing tool result: {message.content[:100]}...")
                
                try:
                    import json
                    tool_result = json.loads(message.content)
                    
                    # Handle different tool results
                    if "success" in tool_result:
                        success_msg = tool_result["success"]
                        
                        # Order creation
                        if "Pedido creado exitosamente" in success_msg:
                            order_created = True
                            order_states["crear_pedido"] = 2
                            print("✅ Order created - marking crear_pedido as completed (2)")
                            
                        # Order update
                        elif "Pedido actualizado exitosamente" in success_msg:
                            order_updated = True
                            print("✅ Order updated successfully")
                            
                        # Order finalization
                        elif "Pedido finalizado exitosamente" in success_msg:
                            order_finalized = True
                            order_states["finalizacion"] = 2
                            print("✅ Order finalized - marking finalizacion as completed (2)")
                            # Clear active order since it's been finalized
                            active_order_data = {
                                "order_id": "",
                                "order_date": "",
                                "order_total": 0.0,
                                "order_items": []
                            }
                            
                        # Client operations
                        elif "Cliente" in success_msg:
                            if "creado" in success_msg or "actualizado" in success_msg:
                                order_states["registro_datos_personales"] = 2
                                print("✅ Client data updated - marking registro_datos_personales as completed (2)")
                    
                    # Handle product search results (pizza or beverage found)
                    elif "precio" in tool_result and ("nombre" in tool_result or "nombre_producto" in tool_result):
                        product_name = tool_result.get("nombre", tool_result.get("nombre_producto", ""))
                        product_id = tool_result.get("id", "")
                        
                        # Check if this product is already in the order to prevent duplicates
                        existing_product = None
                        for item in active_order_data["order_items"]:
                            if (item.get("product_id") == product_id and 
                                item.get("product_name") == product_name):
                                existing_product = item
                                break
                        
                        if existing_product:
                            print(f"⚠️ Product {product_name} already in order, skipping duplicate")
                        else:
                            print(f"🍕 Found new product: {tool_result}")
                            
                            # Create ProductDetails object using the class
                            product_detail = ProductDetails(
                                product_id=product_id,
                                product_name=product_name,
                                product_type="pizza" if "categoria" in tool_result else "bebida",
                                base_price=float(tool_result.get("precio", 0)),
                                total_price=float(tool_result.get("precio", 0)),
                                borde={},
                                adiciones=[]
                            )
                            
                            # Convert to dict for state storage with complete product info
                            product_dict = {
                                "id": product_detail.product_id,
                                "product_id": product_detail.product_id,
                                "product_name": product_detail.product_name,
                                "nombre": product_detail.product_name,  # Alternative name field
                                "product_type": product_detail.product_type,
                                "tipo": product_detail.product_type,  # Alternative type field
                                "base_price": product_detail.base_price,
                                "total_price": product_detail.total_price,
                                "precio": product_detail.total_price,  # Alternative price field
                                "borde": product_detail.borde,
                                "adiciones": product_detail.adiciones,
                                # Additional fields from the original tool result
                                "tamano": tool_result.get("tamano", ""),
                                "categoria": tool_result.get("categoria", ""),
                                "descripcion": tool_result.get("descripcion", tool_result.get("texto_ingredientes", "")),
                                "activo": tool_result.get("activo", True)
                            }
                            
                            # Add to local order items
                            active_order_data["order_items"].append(product_dict)
                            active_order_data["order_total"] += product_detail.total_price
                            products_added = True
                            
                            print(f"✅ Added product to local order: {product_detail.product_name} - ${product_detail.total_price}")
                            print(f"📦 Current local order total: ${active_order_data['order_total']}")
                            
                            # 🔥 CRITICAL: Sync with pedidos_activos immediately
                            try:
                                from src.tools import (
                                    get_active_order_by_client, update_order)

                                # Get active order from database
                                db_order = get_active_order_by_client(user_id)
                                
                                if "error" not in db_order:
                                    # Update existing order in database
                                    order_id = db_order["id"]
                                    current_pedido = db_order.get("pedido", {})
                                    current_items = current_pedido.get("items", [])
                                    
                                    # Add the new product to the items list
                                    current_items.append(product_dict)
                                    current_total = sum(item.get("total_price", item.get("base_price", 0)) for item in current_items)
                                    
                                    # Update the order with new items and total
                                    update_result = update_order(
                                        id=order_id,
                                        items=current_items,
                                        total=current_total
                                    )
                                    
                                    if "success" in update_result:
                                        print(f"✅ Product synced to pedidos_activos: {product_detail.product_name}")
                                        print(f"📦 Database updated with {len(current_items)} items, total: ${current_total}")
                                    else:
                                        print(f"❌ Failed to sync product to DB: {update_result}")
                                else:
                                    print(f"⚠️ No active order in DB to update: {db_order}")
                                    # Try to create an order first
                                    from src.tools import create_order
                                    create_result = create_order(
                                        cliente_id=user_id,
                                        items=[product_dict],
                                        total=product_detail.total_price,
                                        direccion_entrega=None
                                    )
                                    if "success" in create_result:
                                        print(f"✅ Created new order with product: {product_detail.product_name}")
                                    else:
                                        print(f"❌ Failed to create order with product: {create_result}")
                                    
                            except Exception as sync_error:
                                print(f"❌ Error syncing product to DB: {sync_error}")
                                import traceback
                                print(f"Full traceback:\n{traceback.format_exc()}")
                            
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error processing tool result: {e}")
        
        # Update order_states based on successful actions
        if products_added:
            order_states["seleccion_productos"] = 2  # Mark as completed
            print("✅ Products added - marking seleccion_productos as completed (2)")
            
        return {
            "active_order": active_order_data,
            "order_states": order_states,
            # Individual state fields for ChatState compatibility
            "saludo": order_states.get("saludo", 0),
            "registro_datos_personales": order_states.get("registro_datos_personales", 0),
            "registro_direccion": order_states.get("registro_direccion", 0),
            "consulta_menu": order_states.get("consulta_menu", 0),
            "crear_pedido": order_states.get("crear_pedido", 0),
            "seleccion_productos": order_states.get("seleccion_productos", 0),
            "confirmacion": order_states.get("confirmacion", 0),
            "finalizacion": order_states.get("finalizacion", 0),
            "general": order_states.get("general", 0)
        }

    def _process_tool_results(self, state: Dict[str, Any], tool_message) -> Dict[str, Any]:
        """Process tool execution results and update active_order with products found."""
        from datetime import datetime

        # Get existing active_order or create new one
        active_order_data = state.get("active_order", {
            "order_id": f"order_{state.get('user_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        # Ensure all required keys exist
        if "order_items" not in active_order_data:
            active_order_data["order_items"] = []
        if "order_total" not in active_order_data:
            active_order_data["order_total"] = 0.0
        
        if hasattr(tool_message, 'content') and tool_message.content:
            try:
                import json
                tool_result = json.loads(tool_message.content)
                
                # Check if it's a product result (pizza or beverage)
                if "precio" in tool_result and ("nombre" in tool_result or "nombre_producto" in tool_result):
                    product_name = tool_result.get("nombre", tool_result.get("nombre_producto", ""))
                    product_id = tool_result.get("id", "")
                    
                    # Check if this product is already in the order to prevent duplicates
                    existing_product = None
                    for item in active_order_data["order_items"]:
                        if (item.get("product_id") == product_id and 
                            item.get("product_name") == product_name):
                            existing_product = item
                            break
                    
                    if existing_product:
                        print(f"⚠️ Product {product_name} already in order, skipping duplicate")
                        return active_order_data
                    
                    print(f"🍕 Found new product: {tool_result}")
                    
                    # Create ProductDetails object using the class
                    product_detail = ProductDetails(
                        product_id=product_id,
                        product_name=product_name,
                        product_type="pizza" if "categoria" in tool_result else "bebida",
                        base_price=float(tool_result.get("precio", 0)),
                        total_price=float(tool_result.get("precio", 0)),
                        borde={},
                        adiciones=[]
                    )
                    
                    # Extract and apply customizations from user context
                    user_messages = state.get("messages", [])
                    if user_messages:
                        # Get the original user message to extract customizations
                        for msg in reversed(user_messages[-3:]):  # Check last 3 messages
                            if hasattr(msg, 'content') and isinstance(msg.content, str):
                                customizations = self._extract_product_customizations(
                                    msg.content, 
                                    product_detail.product_type
                                )
                                if customizations["borde"] or customizations["adiciones"]:
                                    product_detail = self._apply_customizations_to_product(
                                        product_detail, 
                                        customizations
                                    )
                                    break
                    
                    # Convert to dict for state storage (since state expects dicts)
                    product_dict = {
                        "product_id": product_detail.product_id,
                        "product_name": product_detail.product_name,
                        "product_type": product_detail.product_type,
                        "base_price": product_detail.base_price,
                        "total_price": product_detail.total_price,
                        "borde": product_detail.borde,
                        "adiciones": product_detail.adiciones
                    }
                    
                    # Add to order items
                    active_order_data["order_items"].append(product_dict)
                    active_order_data["order_total"] += product_detail.total_price
                    
                    print(f"✅ Added product to order: {product_detail.product_name} - ${product_detail.total_price}")
                    print(f"📦 Current order total: ${active_order_data['order_total']}")
                    
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing tool result: {e}")
        
        return active_order_data
    
    def _create_order_from_active_order(self, active_order_data: Dict[str, Any]) -> Order:
        """Create a structured Order object from active_order data."""
        from datetime import datetime

        # Convert product dicts to ProductDetails objects
        product_details = []
        for item_data in active_order_data.get("order_items", []):
            product_detail = ProductDetails(
                product_id=item_data.get("product_id", ""),
                product_name=item_data.get("product_name", ""),
                product_type=item_data.get("product_type", ""),
                base_price=item_data.get("base_price", 0.0),
                total_price=item_data.get("total_price", 0.0),
                borde=item_data.get("borde", {}),
                adiciones=item_data.get("adiciones", [])
            )
            product_details.append(product_detail)
        
        # Create Order object
        order = Order(
            order_id=active_order_data.get("order_id", f"order_{datetime.now().strftime('%Y%m%d_%H%M%S')}"),
            order_date=active_order_data.get("order_date", datetime.now().isoformat()),
            order_total=active_order_data.get("order_total", 0.0),
            order_items=product_details
        )
        
        return order
    
    def _validate_and_prepare_order_for_creation(self, active_order_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """Validate active order and prepare it for create_order tool."""
        try:
            # Create structured Order object for validation
            order = self._create_order_from_active_order(active_order_data)
            
            # Prepare items for create_order tool (expects list of dicts)
            items_for_tool = []
            for product in order.order_items:
                item_dict = {
                    "id": product.product_id,
                    "nombre": product.product_name,
                    "tipo": product.product_type,
                    "precio": product.total_price
                }
                
                # Add customizations if present
                if product.borde:
                    item_dict["borde"] = product.borde
                if product.adiciones:
                    item_dict["adiciones"] = product.adiciones
                    
                items_for_tool.append(item_dict)
            
            # Return data ready for create_order tool
            return {
                "cliente_id": user_id,
                "items": items_for_tool,
                "total": order.order_total
            }
            
        except Exception as e:
            print(f"Error validating order: {e}")
            return {
                "cliente_id": user_id,
                "items": [],
                "total": 0.0
            }

    async def _handle_order_confirmation(self, state: Dict[str, Any], section: Dict[str, str]) -> Dict[str, Any]:
        """Handle order confirmation by creating order in database if products exist."""
        user_id = state.get("user_id", "")
        active_order = state.get("active_order", {})
        
        print(f"🔄 Handling order confirmation for user {user_id}")
        print(f"📦 Active order has {len(active_order.get('order_items', []))} items")
        
        # Check if there are products to confirm
        if not active_order.get("order_items"):
            print("❌ No products in active order - cannot confirm")
            return {"messages": []}
        
        # Validate and prepare order for creation
        order_data = self._validate_and_prepare_order_for_creation(active_order, user_id)
        
        print(f"✅ Order validated - creating with {len(order_data['items'])} items, total: ${order_data['total']}")
        
        # Create enhanced prompt for order creation
        confirmation_prompt = f"""
        CONFIRMACIÓN DE PEDIDO:
        
        El usuario ha confirmado su pedido. Procede a crear el pedido en la base de datos.
        
        DATOS DEL PEDIDO:
        - Cliente ID: {order_data['cliente_id']}
        - Productos: {len(order_data['items'])} items
        - Total: ${order_data['total']}
        
        USA LA HERRAMIENTA: create_order con estos argumentos exactos:
        - cliente_id: "{order_data['cliente_id']}"
        - items: {order_data['items']}
        - total: {order_data['total']}
        """
        
        # Create context and get LLM response
        context = [
            SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
            HumanMessage(content=confirmation_prompt)
        ]
        
        response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(context)
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"🔧 Creating order with tools: {[tc['name'] for tc in response.tool_calls]}")
            for tool_call in response.tool_calls:
                print(f"Tool: {tool_call['name']}, Args: {tool_call['args']}")
        else:
            print("⚠️ No tools called for order confirmation")
        
        return {"messages": [response]}

    def _extract_product_customizations(self, user_message: str, product_type: str) -> Dict[str, Any]:
        """Extract product customizations (bordes, adiciones) from user message."""
        customizations = {
            "borde": {},
            "adiciones": []
        }
        
        message_lower = user_message.lower()
        
        # Extract borde information
        borde_keywords = {
            "pimenton": "pimentón",
            "pimentón": "pimentón", 
            "ajo": "ajo",
            "ajonjolí": "ajonjolí",
            "miel": "miel mostaza",
            "mostaza": "miel mostaza",
            "queso": "queso"
        }
        
        for keyword, borde_name in borde_keywords.items():
            if f"borde de {keyword}" in message_lower or f"borde {keyword}" in message_lower:
                customizations["borde"] = {
                    "nombre": borde_name,
                    "precio_adicional": 2000  # Default price, should be fetched from DB
                }
                print(f"🎯 Detected borde: {borde_name}")
                break
        
        # Extract adiciones (only for pizzas)
        if product_type == "pizza":
            adicion_keywords = {
                "pollo": "pollo",
                "jamón": "jamón",
                "jamon": "jamón",
                "champiñones": "champiñones",
                "champinones": "champiñones",
                "pepperoni": "pepperoni",
                "queso extra": "queso extra",
                "tocineta": "tocineta"
            }
            
            for keyword, adicion_name in adicion_keywords.items():
                if keyword in message_lower and "sin " not in message_lower:
                    customizations["adiciones"].append({
                        "nombre": adicion_name,
                        "precio_adicional": 5000  # Default price, should be fetched from DB
                    })
                    print(f"🍕 Detected adición: {adicion_name}")
        
        return customizations
    
    def _apply_customizations_to_product(self, product_detail: ProductDetails, customizations: Dict[str, Any]) -> ProductDetails:
        """Apply customizations to a ProductDetails object and update total price."""
        
        # Apply borde
        if customizations.get("borde"):
            product_detail.borde = customizations["borde"]
            product_detail.total_price += customizations["borde"].get("precio_adicional", 0)
            print(f"🎯 Applied borde: {customizations['borde']['nombre']} (+${customizations['borde'].get('precio_adicional', 0)})")
        
        # Apply adiciones
        if customizations.get("adiciones"):
            product_detail.adiciones = customizations["adiciones"]
            for adicion in customizations["adiciones"]:
                product_detail.total_price += adicion.get("precio_adicional", 0)
                print(f"🍕 Applied adición: {adicion['nombre']} (+${adicion.get('precio_adicional', 0)})")
        
        print(f"💰 Updated product total price: ${product_detail.total_price}")
        return product_detail
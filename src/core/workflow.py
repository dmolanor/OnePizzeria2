import json
import re
from typing import Annotated, Any, Dict, List, Literal

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage, ToolMessage)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from config.settings import supabase
from src.core.actions import Handles
from src.core.checkpointer import state_manager
from src.core.prompts import CustomerServicePrompts
from src.core.state import ChatState, Order, ProductDetails
from src.services.tools import (ALL_TOOLS, CUSTOMER_TOOLS, MENU_TOOLS,
                                ORDER_TOOLS, TELEGRAM_TOOLS, get_order_by_id)


class Workflow:
    def __init__(self):
        self.supabase = supabase
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
        )
        self.prompts = CustomerServicePrompts()
        self.workflow = self._build_workflow()
        self.handles = Handles()
    
    
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
        
        # After retrieve_data, decide if tools are needed
        graph.add_conditional_edges(
            "retrieve_data",
            self.should_use_tools,
            {
                "tools": "tools",
                "send": "send_response"
            }
        )
        
        # After tools, always process results
        graph.add_edge("tools", "process_results")
        
        # After processing results, decide next action
        graph.add_conditional_edges(
            "process_results",
            self.should_continue_after_processing,
            {
                "retrieve": "retrieve_data",  # More messages to process
                "send": "send_response"       # Done processing
            }
        )
        
        # After sending response, save memory and end
        graph.add_edge("send_response", "save_memory")
        graph.add_edge("save_memory", END)
        
        # Compile with async support
        return graph.compile()

#=========================================================#
#-------------------- GRAPH WORKFLOW --------------------#
#=========================================================#

    async def detect_user_intent_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Detect user intent from message."""
        try:
            print(f"=== DETECT_USER_INTENT_STEP START ===")
            print(f"State keys: {list(state.keys())}")
            
            if "messages" not in state or not state["messages"]:
                print("ERROR: No messages in state!")
                return {"divided_message": []}
            
            print(f"Messages in state: {len(state['messages'])}")
            print(f"Last message: {state['messages'][-1].content}")
            print(f"Dividing message and identifying intent: {state['messages'][-1].content}")
            
            cliente_id = state["cliente_id"]
            print(f"User ID: {cliente_id}")
            
            # Get existing order states from previous state or initialize
            existing_order_steps = state.get("order_steps", {
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
            print(f"Existing order states: {existing_order_steps}")
            
            # Check if user exists in database and update states accordingly
            try:
                customer_result = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
                if customer_result.data:
                    customer = customer_result.data[0]
                    print(f"Customer found: {customer}")
                    
                    # Update states based on existing customer data
                    if customer.get("nombre_completo") and customer.get("telefono"):
                        existing_order_steps["registro_datos_personales"] = 2
                        print("Set registro_datos_personales to completed (2)")
                    
                    if customer.get("direccion"):
                        existing_order_steps["registro_direccion"] = 2
                        print("Set registro_direccion to completed (2)")
                else:
                    customer_result = supabase.table("clientes").insert({"id": cliente_id}).execute()
                    customer = customer_result.data[0]
                    print("Customer created in database")
            except Exception as e:
                print(f"Error checking customer: {e}")
                customer = None
            
            new_message = state['messages'][-1].content if state['messages'] else ""
            print(f"New message content: {new_message}")
            
            
            context = [
                SystemMessage(content=self.prompts.MESSAGE_SPLITTING_SYSTEM),
                HumanMessage(content=self.prompts.message_splitting_user(
                    messages=state["messages"],
                    order_steps=existing_order_steps,
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
            
            try:
                divided = json.loads(raw)
                print(f"JSON parsed successfully: {divided}")
            except json.JSONDecodeError as json_err:
                print(f"JSON parsing error: {json_err}")
                print(f"Raw content was: {repr(raw)}")
                return {"divided_message": [], "order_steps": existing_order_steps}
            
            # Update states based on current message intents
            for i, section in enumerate(divided):
                print(f"Processing section {i}: {section}")
                intent = section.get("intent", "unknown")
                if intent in existing_order_steps:
                    # Only set to 1 (in progress) if not already completed (2)
                    if existing_order_steps[intent] != 2:
                        existing_order_steps[intent] = 1
                        print(f"Set {intent} to in progress (1)")
                    else:
                        print(f"{intent} already completed (2), keeping status")
                        
                    # Mark saludo as completed immediately if detected
                    if intent == "saludo":
                        existing_order_steps["saludo"] = 2
                        print(f"Marked saludo as completed (2)")
                        
                    # Auto-trigger crear_pedido for product selection if no active order
                    elif intent == "seleccion_productos":
                        # Check if we need to create an order first
                        if existing_order_steps.get("crear_pedido", 0) == 0:
                            existing_order_steps["crear_pedido"] = 1
                            print(f"Auto-triggered crear_pedido for product selection")
                        
                else:
                    existing_order_steps["general"] = 1
            
            result = {
                "divided_message": divided,
                "order_steps": existing_order_steps,
                "customer": customer,
                "active_order": state.get("active_order", {}),  # Preserve active_order
                "customer": customer,
                # Individual state fields for ChatState compatibility
                "saludo": existing_order_steps.get("saludo", 0),
                "registro_datos_personales": existing_order_steps.get("registro_datos_personales", 0),
                "registro_direccion": existing_order_steps.get("registro_direccion", 0),
                "consulta_menu": existing_order_steps.get("consulta_menu", 0),
                "crear_pedido": existing_order_steps.get("crear_pedido", 0),
                "seleccion_productos": existing_order_steps.get("seleccion_productos", 0),
                "confirmacion": existing_order_steps.get("confirmacion", 0),
                "finalizacion": existing_order_steps.get("finalizacion", 0),
                "general": existing_order_steps.get("general", 0)
            }
            print(f"=== DETECT_USER_INTENT_STEP END ===")
            print(f"Returning order_steps: {existing_order_steps}")
            return result
            
        except Exception as e:
            import traceback
            print(f"ERROR in detect_user_intent_step: {e}")
            print(f"Full traceback:\n{traceback.format_exc()}")
            # Return existing states to avoid reset
            existing_states = state.get("order_steps", {})
            return {
                "divided_message": [], 
                "order_steps": existing_states,
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
        print("=== RETRIEVE DATA STEP START ===")
        print(f"Retrieving data based on divided messages... {state['divided_message']}")
        
        if not state["divided_message"]:
            print("No divided messages to process.")
            return {"divided_message": []}
        
        # Get current section to process
        i = len(state["divided_message"])
        section = state["divided_message"].pop()
        cliente_id = state.get("cliente_id", "")
        
        print(f"Processing section {i}: {section}")
        print(f"User ID: {cliente_id}")
        
        # Get existing order from state or create new one
        active_order = state.get("active_order", {
            "order_id": f"order_{cliente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        order_items = []
        if active_order:
            order_items = active_order.get("order_items", [])
        
        # Handle different intent types
        
        #===CONFIRMACION===#
        if section["intent"] == "confirmacion":
            
            print("🔄 Detected confirmation intent - handling order confirmation")
            confirmation_result = await self.handles._handle_order_confirmation(state, section)
            updated_state = {"messages": confirmation_result["messages"]}
            
        #===CREAR PEDIDO===#    
        elif section["intent"] == "crear_pedido":
            
            order_response = get_order_by_id.invoke({"cliente_id": cliente_id})
            
            if hasattr(order_response, "success"):
                print("🔄 Detected crear_pedido intent - order already exists in database")
                updated_state = {"active_order": order_response}
                
            elif hasattr(order_response, "fail"):
                print("🔄 Detected crear_pedido intent - order does not exist in database - creating new order in database")
                
                active_order = supabase.table("pedidos_activos").insert({"cliente_id": cliente_id, "items": [], "total": 0.0}).execute()
                updated_state = {"active_order": active_order.data[0]}
                        
        #===SELECCION DE PRODUCTOS===#
        elif section["intent"] == "seleccion_productos":
            print("🔄 Detected seleccion_productos intent - searching for products and managing order")
            
            # Enhanced prompt specifically for product selection
            product_selection_prompt = self.prompts.tools_execution_system(section["intent"], section["action"])
            
            product_context = [
                SystemMessage(content=product_selection_prompt),
            ]
            
            response = await self.llm.bind_tools(ORDER_TOOLS+MENU_TOOLS).ainvoke(product_context)
            updated_state = {"messages": [response]}
            
            # Log tool usage for product selection
            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"🔧 PRODUCT SELECTION: {[tc['name'] for tc in response.tool_calls]}")
                for tool_call in response.tool_calls:
                    print(f"Product Tool: {tool_call['name']}, Args: {tool_call['args']}")
                    if tool_call['name'] in ['get_pizza_by_name', 'get_beverage_by_name']:
                        print(f"🍕 Searching for product: {tool_call['args']}")
            else:
                print("⚠️ No tools called for product selection")
                
        #===PERSONALIZACION DE PRODUCTOS===#
        elif section["intent"] == "personalizacion_productos":
            print("🎨 Detected personalizacion_productos intent - handling product customizations")
            
            personalization_prompt = f"""
            PERSONALIZACIÓN DE PRODUCTOS - USUARIO: {cliente_id}
            
            ACCIÓN DEL USUARIO: {section["action"]}
            
            CONTEXTO: El cliente quiere personalizar un producto con bordes, adiciones o modificaciones.
            
            FLUJO:
            1. PRIMERO: Obtener detalles del pedido actual con get_order_details({{"cliente_id": "{cliente_id}"}})
            2. IDENTIFICAR: ¿Qué producto quiere personalizar? (si no está claro, el más reciente)
            3. EXTRAER personalización específica del action: {section["action"]}
            4. USAR: update_product_in_order_smart para aplicar la personalización
            
            PERSONALIZACIONES COMUNES:
            - Bordes: ajo, queso, pimentón, tocineta, dulce
            - Adiciones: queso extra, champiñones, tocineta, pepperoni, aceitunas
            
            EXTRAE del texto: nombres específicos de bordes y adiciones mencionados.
            """
            
            personalization_context = [
                SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
                HumanMessage(content=personalization_prompt)
            ]
            
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(personalization_context)
            updated_state = {"messages": [response]}
            
            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"🎨 PERSONALIZATION: {[tc['name'] for tc in response.tool_calls]}")
                for tool_call in response.tool_calls:
                    print(f"Personalization Tool: {tool_call['name']}, Args: {tool_call['args']}")
            else:
                print("⚠️ No tools called for personalization")
                
        #===MODIFICACION DE PEDIDO===#
        elif section["intent"] == "modificar_pedido":
            print("✏️ Detected modificar_pedido intent - handling order modifications")
            
            modification_prompt = f"""
            MODIFICACIÓN DE PEDIDO - USUARIO: {cliente_id}
            
            ACCIÓN DEL USUARIO: {section["action"]}
            
            CONTEXTO: El cliente quiere cambiar algo en su pedido actual.
            
            FLUJO:
            1. PRIMERO: Obtener pedido actual con get_order_details({{"cliente_id": "{cliente_id}"}})
            2. ANALIZAR: ¿Qué tipo de modificación quiere?
               - Cambiar personalización: usar update_product_in_order_smart
               - Remover producto: usar remove_product_from_order
               - Agregar producto nuevo: usar add_product_to_order_smart
            3. EXTRAER información específica del action: {section["action"]}
            
            TIPOS DE MODIFICACIÓN:
            - "cambiar borde" → update_product_in_order_smart con new_borde_name
            - "quitar producto" → remove_product_from_order
            - "sin adición" → update_product_in_order_smart con new_adiciones_names=[]
            - "agregar más" → add_product_to_order_smart
            
            IMPORTANTE: Identificar exactamente qué quiere cambiar del pedido actual.
            """
            
            modification_context = [
                SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
                HumanMessage(content=modification_prompt)
            ]
            
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(modification_context)
            updated_state = {"messages": [response]}
            
            if hasattr(response, "tool_calls") and response.tool_calls:
                print(f"✏️ MODIFICATION: {[tc['name'] for tc in response.tool_calls]}")
                for tool_call in response.tool_calls:
                    print(f"Modification Tool: {tool_call['name']}, Args: {tool_call['args']}")
            else:
                print("⚠️ No tools called for modification")
                
        #===GENERAL===#
        else:
            print(f"Sending enhanced prompt to LLM with tools...")
            # Create context with enhanced instructions
            context = [
            SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
            HumanMessage(content=self.prompts.tools_execution_user(cliente_id, active_order.get("order_items", []), section))
            ]
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(context)
            if response.additional_kwargs:
                print(f"Response retrieve_data_step: {response.additional_kwargs['function']}")
            updated_state = {"messages": list(state["messages"]) + [response]}
            
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
        
        # Also preserve order_steps if they exist
        if "order_steps" in state:
            updated_state["order_steps"] = state["order_steps"]
        
        return updated_state
    
    
    async def process_tool_results_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool execution results and sync with pedidos_activos."""
        from datetime import datetime
        
        print(f"=== PROCESSING TOOL RESULTS ===")
        
        messages = state.get("messages", [])
        cliente_id = state.get("cliente_id", "unknown")
        
        # Get existing active_order or create new one with proper structure
        active_order = state.get("active_order", {
            "order_id": f"order_{cliente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        # Get existing order_steps and preserve them
        order_steps = state.get("order_steps", {
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
    
        
        order_items, order_total = [], 0
        if active_order_data:
            order_items = active_order_data.get("order_items", [])
            order_total = active_order_data.get("order_total", 0)
        
        print(f"Current order state: {len(order_items)} items, total: ${order_total}")
        print(f"Current order_steps: {order_steps}")
        
        # Track actions completed in this step
        products_added = False
        order_created = False
        order_updated = False
        order_finalized = False
        
        # Look for ToolMessage in recent messages
        print(f"Last 5 messages: {reversed(messages[-5:])}")
        for message in reversed(messages[-5:]):  # Check last 5 messages
            if isinstance(message, ToolMessage):
                print(f"🔧 Processing ToolMessage: {message.tool_call_id}")
                print(f"   Content preview: {message.content[:100]}...")
                
                try:
                    import json
                    tool_result = json.loads(message.content)
                    print("=============================================================")
                    print("=============================================================")
                    print("=============================================================")
                    print(f"Tool result: {tool_result}")
                    print("=============================================================")
                    print("=============================================================")
                    # Handle different tool results
                    if "success" in tool_result:
                        success_msg = tool_result["success"]
                        
                        # Order creation
                        if "Pedido creado exitosamente" in success_msg:
                            order_created = True
                            order_steps["crear_pedido"] = 2
                            print("✅ Order created - marking crear_pedido as completed (2)")
                            
                        # Order update
                        elif "Pedido actualizado exitosamente" in success_msg:
                            order_updated = True
                            print("✅ Order updated successfully")
                            
                        # Order finalization
                        elif "Pedido finalizado exitosamente" in success_msg:
                            order_finalized = True
                            order_steps["finalizacion"] = 2
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
                                order_steps["registro_datos_personales"] = 2
                                print("✅ Client data updated - marking registro_datos_personales as completed (2)")
                    
                    # Handle product search results (pizza or beverage found)
                    elif "precio" in tool_result and ("nombre" in tool_result or "nombre_producto" in tool_result):
                        print(f"🍕 Found product in tool result: {tool_result}")
                        
                        # Use the new smart product tool instead of manual sync
                        try:
                            from src.services.tools import \
                                add_product_to_order_smart

                            # Extract product data
                            product_data = {
                                "id": tool_result.get("id", ""),
                                "nombre": tool_result.get("nombre", tool_result.get("nombre_producto", "")),
                                "tipo": "pizza" if "categoria" in tool_result else "bebida",
                                "precio": float(tool_result.get("precio", 0)),
                                "tamano": tool_result.get("tamano", ""),
                                "categoria": tool_result.get("categoria", ""),
                                "descripcion": tool_result.get("descripcion", tool_result.get("texto_ingredientes", "")),
                                "activo": tool_result.get("activo", True)
                            }
                            
                            # TODO: Extract borde and adiciones from user context if needed
                            # For now, we'll add the basic product and let customizations be handled separately
                            
                            add_result = add_product_to_order_smart(
                                cliente_id=cliente_id,
                                product_data=product_data
                            )
                            
                            if "success" in add_result:
                                products_added = True
                                # Update local active_order from database to keep state in sync
                                from src.services.tools import \
                                    get_active_order_by_client
                                updated_order = get_active_order_by_client(cliente_id)
                                if "error" not in updated_order:
                                    active_order.update({
                                        "order_id": str(updated_order["id"]),
                                        "order_date": updated_order.get("hora_ultimo_mensaje", ""),
                                        "order_total": add_result["data"]["order_total"],
                                        "order_items": updated_order.get("pedido", {}).get("items", [])
                                    })
                                    print(f"✅ Product added successfully: {add_result['success']}")
                                    print(f"📦 Updated order total: ${add_result['data']['order_total']}")
                                else:
                                    print(f"⚠️ Could not sync local state after adding product")
                            else:
                                print(f"❌ Failed to add product: {add_result}")
                                
                        except Exception as add_error:
                            print(f"❌ Error adding product with smart tool: {add_error}")
                            import traceback
                            print(f"Full traceback:\n{traceback.format_exc()}")
                            
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Error processing tool result: {e}")
        
        # Update order_steps based on successful actions
        if products_added:
            order_steps["seleccion_productos"] = 2  # Mark as completed
            print("✅ Products added - marking seleccion_productos as completed (2)")
            
        return {
            "active_order": active_order_data,
            "order_steps": order_steps,
            # Individual state fields for ChatState compatibility
            "saludo": order_steps.get("saludo", 0),
            "registro_datos_personales": order_steps.get("registro_datos_personales", 0),
            "registro_direccion": order_steps.get("registro_direccion", 0),
            "consulta_menu": order_steps.get("consulta_menu", 0),
            "crear_pedido": order_steps.get("crear_pedido", 0),
            "seleccion_productos": order_steps.get("seleccion_productos", 0),
            "confirmacion": order_steps.get("confirmacion", 0),
            "finalizacion": order_steps.get("finalizacion", 0),
            "general": order_steps.get("general", 0)
        }
    
    
    async def send_response_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and format response to user."""
        
        # Recupera el id de cliente y el último mensaje del state
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                new_message = msg
                break
            else:
                new_message = None
        
        print(f"Último mensaje: {new_message}")
        
        if new_message:
            user_input = new_message.content
        else:
            user_input = ""
        
        # Get existing order states (preserve from previous steps)
        order_steps = state.get("order_steps", {
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
        print(f"Active order: {active_order}")
        
        order_items, order_total = [], 0
        if active_order:
            order_items = active_order.get("order_items", [])
            order_total = active_order.get("order_total", 0)
        
        messages = state.get("messages", [])
        
        # Mark saludo as completed if it was detected but not yet marked
        if order_steps.get("saludo", 0) == 1:
            order_steps["saludo"] = 2
            print("Marking saludo as completed (2) in send_response_step")
        
        # Determine the next incomplete state to progress to
        next_incomplete_state = self.handles._get_next_incomplete_state(order_steps, order_items)
        
        # Build context based on current state and next action needed
        context = self.handles._build_conversation_context(state)
        
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
                    content=self.handles._get_next_step_guidance(next_incomplete_state, order_steps, order_items)
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
        print(f"Final order states: {order_steps}")
        print(f"Next incomplete state: {next_incomplete_state}")
        
        # NOTE: Memory saving moved to dedicated final node
        
        # 🔄 PRESERVAR TODOS LOS MENSAJES: Históricos + respuesta actual
        all_messages = messages + [response]  # Mantener historial completo + nueva respuesta
        
        return {
            "messages": all_messages,  # 📝 Todos los mensajes preservados
            "order_steps": order_steps,  # Preserve states
            "active_order": active_order,   # Preserve active order
            # Individual state fields for ChatState compatibility
            "saludo": order_steps.get("saludo", 0),
            "registro_datos_personales": order_steps.get("registro_datos_personales", 0),
            "registro_direccion": order_steps.get("registro_direccion", 0),
            "consulta_menu": order_steps.get("consulta_menu", 0),
            "crear_pedido": order_steps.get("crear_pedido", 0),
            "seleccion_productos": order_steps.get("seleccion_productos", 0),
            "confirmacion": order_steps.get("confirmacion", 0),
            "finalizacion": order_steps.get("finalizacion", 0),
            "general": order_steps.get("general", 0)
        }
        
    async def save_memory_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """📤 FINAL NODE: Save complete conversation to memory database."""
        try:
            cliente_id = state["cliente_id"]
            messages = state.get("messages", [])
            
            print(f"💾 SAVING COMPLETE CONVERSATION TO MEMORY")
            print(f"   - User ID: {cliente_id}")
            print(f"   - Total messages to save: {len(messages)}")
            
            # 🔍 IDENTIFICAR MENSAJES NUEVOS QUE NO ESTÁN EN BD
            from src.core.memory import memory

            # Obtener conversación actual de la BD para comparar
            existing_context = await memory.get_conversation(cliente_id)
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
                        await memory.add_message(cliente_id, message)
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
                        cliente_id, 
                        "customer_name", 
                        state["customer"]["nombre_completo"]
                    )
                    print(f"   ✅ Contexto del cliente actualizado")
                
                # Update order context if we have an active order
                if state.get("active_order") and state["active_order"].get("order_items"):
                    await memory.update_customer_context(
                        cliente_id,
                        "current_order",
                        state["active_order"]
                    )
                    print(f"   ✅ Contexto del pedido actualizado")
            except Exception as context_error:
                print(f"   ⚠️ Error actualizando contexto: {context_error}")
            
            print(f"✅ Conversación completa guardada para usuario {cliente_id}")
            
            # Return the state unchanged (this is the final node)
            return state
            
        except Exception as e:
            print(f"⚠️ Error saving conversation to memory: {e}")
            import traceback
            print(f"Full traceback:\n{traceback.format_exc()}")
            # Return state even if saving fails (don't break the workflow)
            return state
    
    
    
    
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
            print(f"Found tool calls: {[tc['name'] for tc in last_message.tool_calls]}")
            return "tools"
        
        # No tools needed, go directly to response
        print("No tools needed for this message")
        return "send"


    
import json
import re
from typing import Annotated, Any, Dict, List, Literal

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage, ToolMessage)
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from config import supabase
from src.checkpointer import state_manager
from src.handles import Handles
from src.prompts import CustomerServicePrompts
from src.state import ChatState, Order, ProductDetails
from src.tools import (ALL_TOOLS, CUSTOMER_TOOLS, MENU_TOOLS, ORDER_TOOLS,
                       TELEGRAM_TOOLS)


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
    
    def _extract_tool_result(self, tool_message: ToolMessage) -> Dict[str, Any]:
        """
        Extract and parse tool result from ToolMessage.
        
        Args:
            tool_message: ToolMessage containing tool execution result
            
        Returns:
            Dictionary with parsed tool result or empty dict if parsing fails
        """
        try:
            import json
            result = json.loads(tool_message.content)
            print(f"✅ Parsed tool result for {tool_message.tool_call_id}: {result}")
            return result
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"❌ Failed to parse tool result: {e}")
            return {}
    
    def _find_recent_tool_messages(self, messages: List[BaseMessage], limit: int = 5) -> List[ToolMessage]:
        """
        Find recent ToolMessage instances in the message list.
        
        Args:
            messages: List of messages to search
            limit: Maximum number of recent messages to check
            
        Returns:
            List of ToolMessage instances found
        """
        tool_messages = []
        for message in reversed(messages[-limit:]):
            if isinstance(message, ToolMessage):
                tool_messages.append(message)
        return tool_messages
    
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
                customer_result = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
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
            
            new_message = state['messages'][-1].content if state['messages'] else ""
            print(f"New message content: {new_message}")
            
            
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
            
            result = {
                "divided_message": divided,
                "order_states": existing_order_states,
                "customer": customer,
                "messages": [],
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
        print("=== RETRIEVE DATA STEP START ===")
        print(f"Retrieving data based on divided messages... {state['divided_message']}")
        
        if not state["divided_message"]:
            print("No divided messages to process.")
            return {"divided_message": []}
        
        # Get current section to process
        section = state["divided_message"].pop()
        cliente_id = state.get("cliente_id", "")
        
        print(f"Processing section: {section}")
        print(f"User ID: {cliente_id}")
        
        # Get existing order from state or create new one
        active_order = state.get("active_order", {
            "order_id": f"order_{cliente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "order_date": datetime.now().isoformat(),
            "order_total": 0.0,
            "order_items": []
        })
        
        print(f"Active order: {active_order}")

        # Create context with enhanced instructions
        context = [
            SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
            HumanMessage(content=self.prompts.tools_execution_user(cliente_id, active_order.get("order_items", []), section))
        ]
        
        # Handle different intent types
        if section["intent"] == "confirmacion":
            print("🔄 Detected confirmation intent - handling order confirmation")
            confirmation_result = await self.handles._handle_order_confirmation(state, section)
            updated_state = {"messages": confirmation_result["messages"]}
        elif section["intent"] == "crear_pedido":
            
            if state["customer"]:
                print("🔄 Detected crear_pedido intent - ensuring order exists in database")
                response = await self.llm.bind_tools(ORDER_TOOLS).ainvoke(context)
                updated_state = {"messages": [response]}
            
                # Log tool usage for order creation
                if hasattr(response, "tool_calls") and response.tool_calls:
                    print(f"🔧 CREATING ORDER: {[tc['name'] for tc in response.tool_calls]}")
                    for tool_call in response.tool_calls:
                        print(f"Order Creation Tool: {tool_call['name']}, Args: {tool_call['args']}")
            else:
                section = {"intent": "crear_cliente", "action": "Crear nuevo cliente con solo user_id"}
                context = [
                    SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
                    HumanMessage(content=self.prompts.tools_execution_user(cliente_id, active_order.get("order_items", []), section))
                ]
                print("Detected crear_cliente intent - creating new client in database")
                response = await self.llm.bind_tools(CUSTOMER_TOOLS).ainvoke(context)
                updated_state = {"messages": [response]}
            
                # Log tool usage for order creation
                if hasattr(response, "tool_calls") and response.tool_calls:
                    print(f"🔧 CREATING CLIENT: {[tc['name'] for tc in response.tool_calls]}")
                    for tool_call in response.tool_calls:
                        print(f"Client Creation Tool: {tool_call['name']}, Args: {tool_call['args']}")
        elif section["intent"] == "seleccion_productos":
            print("🔄 Detected seleccion_productos intent - searching for products and managing order")
            
            # Enhanced prompt specifically for product selection
            product_selection_prompt = f"""
            SELECCIÓN DE PRODUCTOS - USUARIO: {cliente_id}
            
            ACCIÓN DEL USUARIO: {section["action"]}
            
            FLUJO OBLIGATORIO:
            1. PRIMERO: Verificar si existe pedido activo con get_active_order_by_client({{"cliente_id": "{cliente_id}"}})
            2. Si NO existe pedido: Crear pedido con create_order({{"cliente_id": "{cliente_id}", "items": [], "total": 0.0}})
            3. LUEGO: Buscar el producto mencionado:
               - Si menciona pizza: usa get_pizza_by_name con el nombre exacto
               - Si menciona bebida: usa get_beverage_by_name con el nombre exacto
            4. El producto se agregará automáticamente al pedido en el siguiente paso
            
            EXTRAE EL NOMBRE DEL PRODUCTO del action: {section["action"]}
            
            IMPORTANTE: Usa el nombre exacto del producto, no uses argumentos vacíos.
            """
            
            product_context = [
                SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM),
                HumanMessage(content=product_selection_prompt)
            ]
            
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(product_context)
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
        else:
            print(f"Sending enhanced prompt to LLM with tools...")
            response = await self.llm.bind_tools(ALL_TOOLS).ainvoke(context)
            
            print(f"Response retrieve_data_step: {response}")
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
        
        # Also preserve order_states if they exist
        if "order_states" in state:
            updated_state["order_states"] = state["order_states"]
        
        return updated_state
    
    
    async def process_tool_results_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Process tool execution results and sync with pedidos_activos."""
        from datetime import datetime
        
        print(f"=== PROCESSING TOOL RESULTS ===")
        
        messages = state.get("messages", [])
        cliente_id = state.get("cliente_id", "unknown")
        
        # Get existing active_order or create new one with proper structure
        active_order_data = state.get("active_order", {
            "order_id": f"order_{cliente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
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
                                db_order = get_active_order_by_client(cliente_id)
                                
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
                                        cliente_id=cliente_id,
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
    
    
    async def send_response_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate and format response to user."""
        cliente_id = state["cliente_id"]
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
        print(f"Active order: {active_order}")
        order_items = active_order.get("order_items", [])
        order_total = active_order.get("order_total", 0.0)
        
        messages = state.get("messages", [])
        
        # Look for successful tool executions in recent messages and update states
        for message in reversed(messages[-10:]):  # Check last 10 messages
            # Check ToolMessage specifically for tool results
            if isinstance(message, ToolMessage):
                try:
                    import json
                    tool_result = json.loads(message.content)
                    if "success" in tool_result:
                        content = tool_result["success"].lower()
                        print(f"🔧 Processing ToolMessage success: {content}")
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
                except (json.JSONDecodeError, KeyError):
                    pass
            # Also check AIMessage content for backwards compatibility
            elif isinstance(message, AIMessage) and hasattr(message, "content") and isinstance(message.content, str):
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
        next_incomplete_state = self.handles._get_next_incomplete_state(order_states, order_items)
        
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
                    content=self.handles._get_next_step_guidance(next_incomplete_state, order_states, order_items)
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
        
        # 🔄 PRESERVAR TODOS LOS MENSAJES: Históricos + respuesta actual
        all_messages = messages + [response]  # Mantener historial completo + nueva respuesta
        
        return {
            "messages": all_messages,  # 📝 Todos los mensajes preservados
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
        
    async def save_memory_step(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """📤 FINAL NODE: Save complete conversation to memory database."""
        try:
            cliente_id = state["cliente_id"]
            messages = state.get("messages", [])
            
            print(f"💾 SAVING COMPLETE CONVERSATION TO MEMORY")
            print(f"   - User ID: {cliente_id}")
            print(f"   - Total messages to save: {len(messages)}")
            
            # 🔍 IDENTIFICAR MENSAJES NUEVOS QUE NO ESTÁN EN BD
            from src.memory import memory

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


    
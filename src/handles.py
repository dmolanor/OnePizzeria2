from typing import Annotated, Any, Dict, List, Literal

from langchain_core.messages import (AIMessage, BaseMessage, HumanMessage,
                                     SystemMessage, ToolMessage)

from config import supabase
from src.checkpointer import state_manager
from src.prompts import CustomerServicePrompts
from src.state import ChatState, Order, ProductDetails
from src.tools import (ALL_TOOLS, CUSTOMER_TOOLS, MENU_TOOLS, ORDER_TOOLS,
                       TELEGRAM_TOOLS)


class Handles:
    def __init__(self):
        self.prompts = CustomerServicePrompts()
        pass
    
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
        print(f"📦 Order items count: {len(order_items) if order_items else 0}")
        
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
    
    # SIN USAR
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
        """
        context.append(
            SystemMessage(
                content=f"IMPORTANTE: EL user_id de este cliente es {user_id}. "
                        "Usar siempre user_id para utilizar herramientas que lo requieran"
            )
        )
        """
        if state.get("customer"):
            context.append(
                SystemMessage(
                    content=f"Esta es la información actual del cliente: {state['customer']}"
                )
            )
        print("********************************************")
        print("********************************************")
        print("state['messages']")
        print(state["messages"])
        print("********************************************")
        print("********************************************")

        context.extend(state["messages"])
        
        #print(f"Context Loaded: ")
        #for message in context:
        #    print(f"Message: {message}")
        return context
    
    # SIN USAR
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
        confirmation_prompt = self.prompts.confirmation_user(order_data)
        
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
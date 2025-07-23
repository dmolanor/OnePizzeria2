import json
import re
from typing import Annotated, Any, Dict, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .checkpointer import state_manager
from .models import ChatState, Order, ProductDetails
from .prompts import CustomerServicePrompts
from .tools import SupabaseService


class ConversationState(TypedDict):
    """Estado extendido que incluye el progreso de la conversación"""
    user_id: str
    messages: Annotated[list, add_messages]
    customer: Dict[str, Any]
    active_order: Dict[str, Any]
    response: str
    
    # Estados del flujo de conversación
    has_greeted: bool
    has_customer_data: bool
    has_address: bool
    has_seen_menu: bool
    has_selected_products: bool
    needs_confirmation: bool
    is_finalized: bool
    
    # Próximo paso sugerido
    next_step: str


class Workflow:
    def __init__(self):
        self.supabase = SupabaseService()
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.1,
        )
        self.prompts = CustomerServicePrompts()
        self.workflow = self._build_workflow()
    
    def _build_workflow(self):
        """Build workflow following ORDER_GUIDE flow"""
        graph = StateGraph(ConversationState)
        
        # Add nodes
        graph.add_node("analyze_message", self.analyze_message_step)
        graph.add_node("handle_tools", ToolNode(self.supabase.ALL_TOOLS))
        graph.add_node("generate_response", self.generate_response_step)
        
        # Set entry point
        graph.set_entry_point("analyze_message")
        
        # Add edges
        graph.add_conditional_edges(
            "analyze_message",
                                    self.should_use_tools,
                                    {
                "tools": "handle_tools",
                "response": "generate_response"
            }
        )
        graph.add_edge("handle_tools", "generate_response")
        graph.add_edge("generate_response", END)
        
        return graph.compile()
    
    def analyze_message_step(self, state: ConversationState) -> Dict[str, Any]:
        """Analiza el mensaje y determina el estado de la conversación"""
        print(f"Analyzing message: {state['messages'][-1].content}")
        
        user_message = state["messages"][-1].content
        
        # Determinar estado actual de la conversación
        conversation_context = self._get_conversation_context(state)

        # Crear prompt según el estado actual
        system_prompt = self._create_system_prompt(conversation_context)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        # Usar LLM con herramientas
        llm_with_tools = self.llm.bind_tools(self.supabase.ALL_TOOLS)
        response = llm_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    def _get_conversation_context(self, state: ConversationState) -> str:
        """Determina en qué fase de la conversación estamos"""
        if not state.get("has_greeted", False):
            return "saludo"
        elif not state.get("has_customer_data", False):
            return "registro_datos_personales"
        elif not state.get("has_address", False) and state.get("has_selected_products", False):
            return "registro_direccion"
        elif not state.get("has_seen_menu", False):
            return "consulta_menu"
        elif not state.get("has_selected_products", False):
            return "seleccion_productos"
        elif state.get("needs_confirmation", False):
            return "confirmacion"
        elif not state.get("is_finalized", False):
            return "finalizacion"
        else:
            return "general"
    
    def _create_system_prompt(self, context: str) -> str:
        """Crear prompt específico según el contexto de la conversación"""
        base_prompt = """Eres Juan, empleado de One Pizzeria en Bogotá, Colombia. Eres amigable y profesional.
        
INSTRUCCIONES IMPORTANTES:
- Responde de forma natural, sin emojis excesivos ni plantillas
- Usa las herramientas disponibles para obtener información real
- Calcula precios correctamente incluyendo adiciones y bordes
- Mantén el flujo de conversación según ORDER_GUIDE

CONTEXTO ACTUAL: {context}"""

        context_instructions = {
            "saludo": """
FASE: SALUDO INICIAL
- Saluda cordialmente al cliente
- Pregunta en qué puedes ayudarle
- Si menciona productos, guarda la información pero pregunta primero por sus datos
- Usa get_customer para verificar si ya está registrado""",
            
            "registro_datos_personales": """
FASE: REGISTRO DE DATOS PERSONALES
- Solicita nombre completo, teléfono y correo (correo opcional)
- Usa create_customer para registrar cliente nuevo
- Usa update_customer para actualizar datos existentes
- Confirma los datos registrados""",
            
            "registro_direccion": """
FASE: REGISTRO DE DIRECCIÓN
- Solicita dirección completa de entrega
- Pregunta método de pago (efectivo, tarjeta, transferencia)
- Usa update_customer para guardar la dirección""",
            
            "consulta_menu": """
FASE: CONSULTA DE MENÚ
- Usa get_full_menu para mostrar todas las opciones
- Usa search_menu para consultas específicas
- Explica opciones de tamaños, adiciones y bordes disponibles
- Usa get_pizza_additions para mostrar extras disponibles""",
            
            "seleccion_productos": """
FASE: SELECCIÓN DE PRODUCTOS
- Ayuda al cliente a elegir productos
- Usa calculate_pizza_price para calcular precios con adiciones y bordes
- Usa create_or_update_order para agregar productos al pedido
- Muestra el total actualizado después de cada adición""",
            
            "confirmacion": """
FASE: CONFIRMACIÓN DE PEDIDO
- Muestra resumen completo del pedido con precios
- Confirma dirección de entrega y método de pago
- Pregunta si desea hacer cambios o confirmar
- Si confirma, procede a finalización""",
            
            "finalizacion": """
FASE: FINALIZACIÓN
- Usa finalize_order para completar el pedido
- Proporciona tiempo estimado de entrega
- Agradece al cliente""",
            
            "general": """
FASE: CONSULTA GENERAL
- Responde preguntas sobre productos, precios, tiempos
- Mantén el contexto del pedido actual si existe"""
        }
        
        instruction = context_instructions.get(context, context_instructions["general"])
        return base_prompt.format(context=context) + instruction
    
    def should_use_tools(self, state: ConversationState) -> Literal["tools", "response"]:
        """Decide si usar herramientas basado en el último mensaje AI"""
        last_message = state["messages"][-1]
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            print(f"🔧 Using tools: {[tc['name'] for tc in last_message.tool_calls]}")
            return "tools"
        else:
            print("📝 Generating direct response")
            return "response"
    
    def generate_response_step(self, state: ConversationState) -> Dict[str, Any]:
        """Genera respuesta final y determina próximo paso"""
        messages = state["messages"]
        
        # Obtener respuesta del LLM
        last_message = messages[-1]
        
        if hasattr(last_message, "content") and last_message.content:
            response_content = last_message.content
        else:
            # Generar respuesta basada en herramientas usadas
            context = self._get_conversation_context(state)
            system_msg = SystemMessage(content=f"""Basándote en los resultados de las herramientas usadas, 
            genera una respuesta natural y útil para el cliente de One Pizzeria.
            Contexto actual: {context}
            
            IMPORTANTE: Además de responder, guía al cliente hacia el siguiente paso apropiado:
            - Si es saludo -> pide datos personales
            - Si registró datos -> muestra menú o toma pedido
            - Si seleccionó productos -> pide dirección y método de pago
            - Si tiene todo -> confirma pedido
            - Si confirmó -> finaliza
            """)
            response = self.llm.invoke([system_msg] + messages)
            response_content = response.content
        
        # Actualizar estado de conversación
        updated_state = self._update_conversation_state(state, response_content)
        
        return {
            "response": response_content,
            **updated_state
        }
    
    def _update_conversation_state(self, state: ConversationState, response: str) -> Dict[str, Any]:
        """Actualiza el estado de la conversación basado en la respuesta"""
        updates = {}
        
        # Analizar respuesta para determinar cambios de estado
        response_lower = response.lower()
        
        if "bienvenido" in response_lower or "hola" in response_lower:
            updates["has_greeted"] = True
            
        if "registrado" in response_lower or "datos" in response_lower:
            updates["has_customer_data"] = True
            
        if "menú" in response_lower or "pizzas" in response_lower:
            updates["has_seen_menu"] = True
            
        if "pedido" in response_lower and "total" in response_lower:
            updates["has_selected_products"] = True
            updates["needs_confirmation"] = True
            
        if "confirmado" in response_lower:
            updates["is_finalized"] = True
            
        # Determinar próximo paso
        if not updates.get("has_customer_data", state.get("has_customer_data", False)):
            updates["next_step"] = "registro_datos_personales"
        elif not updates.get("has_seen_menu", state.get("has_seen_menu", False)):
            updates["next_step"] = "consulta_menu"
        elif not updates.get("has_selected_products", state.get("has_selected_products", False)):
            updates["next_step"] = "seleccion_productos"
        elif updates.get("needs_confirmation", state.get("needs_confirmation", False)):
            updates["next_step"] = "confirmacion"
        elif not updates.get("is_finalized", state.get("is_finalized", False)):
            updates["next_step"] = "finalizacion"
        else:
            updates["next_step"] = "completado"
            
        return updates
    
    async def run(self, user_message: str, user_id: str = "test_user") -> str:
        """Run the workflow with conversation state management"""
        try:
            # Cargar estado con memoria
            base_state = await state_manager.load_state_for_user(user_id, user_message)
            
            # Convertir a ConversationState con estados adicionales
            conversation_state = ConversationState(
                user_id=base_state["user_id"],
                messages=base_state["messages"],
                customer=base_state.get("customer", {}),
                active_order=base_state.get("active_order", {}),
                response="",
                has_greeted=bool(base_state.get("customer", {})),
                has_customer_data=bool(base_state.get("customer", {}).get("nombre")),
                has_address=bool(base_state.get("customer", {}).get("direccion")),
                has_seen_menu=False,  # Se determinará en el análisis
                has_selected_products=bool(base_state.get("active_order", {}).get("pedido")),
                needs_confirmation=False,
                is_finalized=False,
                next_step="saludo"
            )
            
            # Ejecutar workflow
            final_state = self.workflow.invoke(conversation_state)
            
            # Extraer respuesta
            response = final_state.get("response", "Lo siento, no pude procesar tu mensaje.")
            
            # Guardar estado
            await state_manager.save_state_for_user(final_state, response)
            
            return response
            
        except Exception as e:
            print(f"Error in workflow: {e}")
            return "Lo siento, tuve un problema técnico. ¿Podrías intentar de nuevo?"
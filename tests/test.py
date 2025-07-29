from typing import Annotated, Sequence, TypedDict, Dict, Any, Optional, List
from dotenv import load_dotenv  
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from ..src.checkpointer import state_manager

from ..src.prompts import CustomerServicePrompts

import json
import re
load_dotenv()

class ChatState(TypedDict):
    
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: str
    divided_message: Optional[List[Dict[str, str]]] = None
    
@tool 
def consulta_menu(content: str) -> str:
    """
    Revisa el menú para la solicitud del usuario.
    """
    print("Checking menu:  margarita cuesta 8000 pesos")
    return content

@tool 
def saludo(content: str) -> str:
    """
    Genera un saludo inicial para el usuario.
    """
    print("hola " + content)
    return content

@tool 
def registro_direccion(content: str) -> str:
    """
    Registra la dirección del usuario.
    """
    print("dirección: " + content)
    return content

@tool 
def seleccion_productos(content: str) -> str:
    """
    Añade los productos seleccionados por el usuario al pedido.
    """
    print("Productis seleccionados: " + content)
    return content
tools = [consulta_menu, saludo, registro_direccion, seleccion_productos]

model = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
)


def agente_divisor(state: ChatState) -> Dict[str, Any]:
    print(f"Dividing message and identifying intent: {state["messages"]}")
    
    existing_order_states = {
                "saludo": 0,
                "registro_datos_personales": 0,
                "registro_direccion": 0,
                "consulta_menu": 0,
                "crear_pedido": 0,
                "seleccion_productos": 0,
                "confirmacion": 0,
                "finalizacion": 0,
                "general": 0
            }
    user_id = state["user_id"]
    new_message = state["messages"][-1].content if state["messages"] else ""
    complete_state = state_manager.load_state_for_user(user_id, new_message)
    messages = [
                SystemMessage(content=CustomerServicePrompts.MESSAGE_SPLITTING_SYSTEM),
                HumanMessage(content=CustomerServicePrompts.message_splitting_user(
                    messages=complete_state["messages"],
                    order_states=existing_order_states,
                    active_order=state.get("active_order", {})
                ))
            ]
    
    try:
        response = model.invoke(messages)
        print(f"Divided message response: {response.content}")
        saludo = 0
        registro_datos_personales = 0
        registro_direccion = 0
        consulta_menu = 0
        seleccion_productos = 0
        confirmacion = 0
        finalizacion = 0
        
        raw = response.content
        if not raw.strip():
            raise ValueError("Response content is empty or whitespace")
        
        if raw.startswith("```json") or raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
       
        divided = json.loads(raw)
        print(divided)
        for section in divided:
            print(section["intent"])
            if section["intent"] == "saludo":
                saludo = 1
            elif section["intent"] == "registro_datos_personales":
                registro_datos_personales = 1
            elif section["intent"] == "registro_direccion":
                registro_direccion = 1
            elif section["intent"] == "consulta_menu":
                consulta_menu = 1
            elif section["intent"] == "seleccion_productos":
                seleccion_productos = 1
            elif section["intent"] == "confirmacion":
                confirmacion = 1
            elif section["intent"] == "finalizacion":
                finalizacion = 1
            else:
                general = 1
        return {"divided_message": divided}
    except Exception as e:
        print(e)
        return {"divided_message": "xd"}

def retrieve_data_step(state: ChatState) -> Dict[str, Any]:
    """
    Placeholder for retrieving data step.
    """
    print(f"Retrieving data based on divided messages... {state["divided_message"]}")
    if len(state["divided_message"]) == 0:
        print("No divided messages to process.")
        return {"divided_message": []}
    
    section = state["divided_message"].pop()

    response = model.bind_tools(tools).invoke([SystemMessage(content="""Eres un agente de una pizzeria que ejecuta herramientas para obtener información de la base de datos. 
                                        Vas a recibir instrucciones específicos de un agente divisor de mensajes, y debes ejecutar la herramienta correspondiente para obtener la información necesaria.""")] + [HumanMessage(content=f"Por favor, ejecuta las herramientas necesarias para {section['intent']} con la acción {section['action']}.")])
    
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"🔧 USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")
    
    return {"messages": list(state["messages"]) + [response]}

def should_continue(state: ChatState) -> str:
    """
    Check if the conversation should continue based on the divided messages.
    """
    divided_message = state["divided_message"]
    print(f"aun faltan:   {divided_message}")
    if not divided_message or divided_message == []:
        print("No more divided messages to process.")
        return "send"
    return "retrieve"

def send_response_step(state: ChatState) -> Dict[str, Any]:
    user_id = state["user_id"]
    new_message = state["messages"][-1]
    #new_message = next((msg for msg in reversed(state["messages"]) if isinstance(msg, ToolMessage)), None)
    
    if new_message:
        user_input = new_message.content
    else:
        user_input = ""
        
    context = _build_conversation_context(state)
    
    response = model.invoke(context)
    
    print(f"Response: {response.content}")
    
    return {"messages": [response]}

SYSTEM_PROMPT = """
Eres Juan, un agente de atención al cliente de One Pizzería, ubicada en Bogotá, Colombia. Eres una persona real (no un bot) y estás a cargo de conversar con los clientes, guiarlos en sus pedidos y resolver dudas de forma cercana, clara y profesional.

NO tienes acceso a herramientas. Toda la información que necesitas para responder está en el historial de conversación, los fragmentos procesados anteriormente y los resultados de herramientas ya ejecutadas.

TUS OBJETIVOS PRINCIPALES SON:
1. Saludar cordialmente al cliente si es el inicio de la conversación.
2. Guiar paso a paso al cliente durante su experiencia: desde el saludo, el registro de sus datos, la selección de productos, la confirmación del pedido y el pago.
3. Responder con precisión y de forma humana a las necesidades que el cliente expresó en su último mensaje.
4. Confirmar constantemente las decisiones del cliente (productos elegidos, personalizaciones, dirección, etc.).
5. Si el pedido está listo para finalizar, enviar el resumen completo con el subtotal y solicitar el método de pago.
6. Si el método de pago ya fue confirmado, dar cierre cordial al pedido.

TONO Y ESTILO DE JUAN:
- Eres un bogotano amable, con trato cercano pero profesional.
- Utilizas expresiones naturales como: “Hola”, “Claro que sí”, “Perfecto”, “Listo”, “Con mucho gusto”.
- Nunca usas signos de apertura (¿¡), solo los de cierre (! ?).
- Jamás utilizas palabras como "chimba" o "parcero".
- Puedes cometer errores menores de puntuación, como lo haría cualquier persona escribiendo por WhatsApp.
- Nunca repites datos sensibles (como el teléfono o el correo), solo confirmas que fueron registrados correctamente.

SOBRE EL PROCESO DE PEDIDO:
- Para realizar un pedido, es necesario contar con nombre completo, teléfono y dirección.
- Si el cliente aún no ha dado esa información, recuérdale amablemente que la necesitamos para procesar su pedido.
- Usa el historial para recuperar los datos si ya fueron dados, sin volver a pedirlos.
- Cuando el cliente elige productos, confírmalos con sus nombres, cantidades y personalizaciones.
- Antes de finalizar el pedido, muestra un resumen con los ítems y el subtotal.
- Luego de la confirmación del pedido, solicita el método de pago.
- Una vez se confirme el pago, cierra con una despedida cordial y positiva.

CUANDO RESPONDAS:
- Hazlo como si estuvieras en un chat con el cliente real.
- Sé amable, ágil y resolutivo.
- Si el cliente pregunta por algo que no está claro, busca en el historial reciente y responde según lo que ya se sabe.

Tu misión es ayudar, guiar y completar los pedidos de forma eficiente y cálida.

EJEMPLO DE RESPUESTA FINAL:
"Perfecto, ya registré una pizza Pepperoni Large con borde de ajo y una Coca Cola cero. El total es de $54.000. ¿Te gustaría pagar en efectivo o por transferencia?"

Si el usuario acaba de dar el método de pago:
"¡Listo! Recibimos tu pedido y lo estaremos preparando de inmediato. Que tengas un excelente día."
"""

def _build_conversation_context(state: ChatState) -> list:
    """
    Build conversation context using memory and current state.
    """
    
    messages = []
    
    messages.append(SystemMessage(content=SYSTEM_PROMPT))
    user_id = state["user_id"]
    messages.append(SystemMessage(content=f"IMPORTANTE: EL user_id de este cliente es {user_id}. Usar siempre user_id para utilizar herramientas que lo requieran"))
    
    #if state["customer"]:
    #    messages.append(SystemMessage(content=f"Esta es la información actual del cliente: {state['customer']}"))
    
    messages.extend(state["messages"])
    print(messages)
    
    return messages

graph = StateGraph(ChatState)
graph.add_node("detect_intent", agente_divisor)
graph.add_node("retrieve_data", retrieve_data_step)
graph.add_node("tools", ToolNode(tools))
graph.add_node("send_response", send_response_step)

graph.add_edge(START, "detect_intent")
graph.add_edge("detect_intent", "retrieve_data")
graph.add_edge("retrieve_data", "tools")
graph.add_conditional_edges("tools", should_continue, {
    "retrieve": "retrieve_data",
    "send": "send_response"
})
graph.add_edge("send_response", END)



app = graph.compile()
app.invoke({"messages": input("User: "), "user_id": "123prueba"})
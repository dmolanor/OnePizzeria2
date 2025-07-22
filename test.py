from typing import Annotated, Sequence, TypedDict, Dict, Any, Optional, List
from dotenv import load_dotenv  
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

import json
import re
load_dotenv()

class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    divided_message: Optional[List[Dict[str, str]]] = None
    
@tool 
def consulta_menu(content: str) -> str:
    """
    Revisa el menú para la solicitud del usuario.
    """
    print("Checking menu: " + content)
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
        
    messages = [
        SystemMessage(content="""Eres un divisor de mensajes por intención y semántica. 
                        Tu tarea es dividir un mensaje del usuario en una lista de mensajes, cada uno perteneciente a una intención y acción diferente, y retornar una lista de diccionarios.
                        """),
        HumanMessage(content="Mensaje del usuario:" +  state["messages"][-1].content + """

            Divide el mensaje en una lista de mensajes, cada uno perteneciente a una intención y acción diferente.
            Si el mensaje pertenece a más de una intención y acción, divídelo en tantos mensajes como sea necesario.
            Cada fragmento puede pertenecer a una de las siguientes categorías:
            - saludo
            - registro_datos_personales
            - registro_direccion
            - consulta_menu
            - seleccion_productos
            - confirmacion
            - finalizacion
            - general (si el mensaje no pertenece a ninguna de las categorías anteriores)

            Devuelve la lista de mensajes con la categoría de intensión a la que pertenece y el fragmento del mensaje correspondiente. 
            Este fragmento debe resumir lo que desea el usuario, sin perder información relevante. Si un mensaje recibe múltiples fragmentos con la misma intención, separalos en diferentes mensajes y diccionarios.
            Ejemplo:
            - mensaje: "Hola, quiero pedir una pizza de pepperoni para la direccion Calle 10 #20-30."
                return: [
                    {"intent": "saludo", "action": "saludar"},
                    {"intent": "registro_direccion", "action": "Calle 10 #20-30"},
                    {"intent": "seleccion_productos", "action": "pedido_pizza_pepperoni"},
                ]
            - mensaje: "Necesito actualizar mi número de teléfono."
                return: [
                    {"intent": "registro_datos_personales", "action": "actualizar_telefono"},
                ]
            - mensaje: "¿Qué ingredientes tiene la pizza hawaiana?"
                return: [
                    {"intent": "consulta_menu", "action": "ingredientes_pizza_hawaiana"},
                ]
            - mensaje: "Quiero una pizza de pepperoni y una Coca Cola cero."
                return: [
                    {"intent": "seleccion_productos", "action": "pedido_pizza_pepperoni"},
                    {"intent": "seleccion_productos", "action": "pedido_coca_cola_zero"},
                ]
            
            Para mayor contexto, dada una situación donde un mensaje por si solo no tenga significado en las categorías, el historial de los últimos 3 mensajes chat es: {" ".join(msg.content for msg in message[-4:-1])}
            """)
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
        return "END"
    return "retrieve"

graph = StateGraph(ChatState)
graph.add_node("detect_intent", agente_divisor)
graph.add_node("retrieve_data", retrieve_data_step)
graph.add_node("tools", ToolNode(tools))

graph.add_edge(START, "detect_intent")
graph.add_edge("detect_intent", "retrieve_data")
graph.add_edge("retrieve_data", "tools")
graph.add_conditional_edges("tools", should_continue, {
    "retrieve": "retrieve_data",
    "END": END
})


app = graph.compile()
app.invoke({"messages": input("User: ")})
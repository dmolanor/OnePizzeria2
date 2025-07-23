import json
import re
from typing import Annotated, Any, Dict, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .state import ChatState, Order, ProductDetails
from .prompts import CustomerServicePrompts
from .supabase import SupabaseService


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
        graph = StateGraph(ChatState)
        graph.add_node("detect_intent", self.detect_user_intent_step)
        graph.add_node("retrieve_data", self.retrieve_data_step)
        graph.add_node("tools", ToolNode(self.supabase.ALL_TOOLS))
        graph.add_node("send_response", self.send_response_step)
        graph.set_entry_point("detect_intent")
        graph.add_edge("detect_intent", "retrieve_data")
        graph.add_edge("retrieve_data", "tools")
        graph.add_conditional_edges("tools", 
                                    self.should_use_tools,
                                    {
                                        "retrieve": "retrieve_data",
                                        "send": "send_response"
                                    })
        graph.add_edge("send_response", END)
        return graph.compile()
        
    
    def detect_user_intent_step(self, state: ChatState) -> Dict[str, Any]:
        print(f"Dividing message and identifying intent: {state["messages"][-1].content}")
        
        user_id = state["user_id"]
        costumer = self.supabase.get_client_by_phone_number(user_id)
        
        messages = [
            SystemMessage(content=self.prompts.MESSAGE_SPLITTING_SYSTEM),
            HumanMessage(content=self.prompts.message_splitting_user(state["messages"]))
        ]
        
        try:
            response = self.llm.invoke(messages)
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
                    
            return {"divided_message": divided,
                    "saludo": saludo,
                    "registro_datos_personales": registro_datos_personales,
                    "registro_direccion": registro_direccion,
                    "consulta_menu": consulta_menu,
                    "seleccion_productos": seleccion_productos,
                    "confirmacion": confirmacion,
                    "finalizacion": finalizacion,
                    "general": general,
                    "costumer": costumer}
            
        except Exception as e:
            print(e)
            return {"divided_message": []}
    
    
    def retrieve_data_step(self, state: ChatState) -> Dict[str, Any]:
        """
        Placeholder for retrieving data step.
        """
        print(f"Retrieving data based on divided messages... {state["divided_message"]}")
        if len(state["divided_message"]) == 0:
            print("No divided messages to process.")
            return {"divided_message": []}
        
        section = state["divided_message"].pop()

        response = self.llm.bind_tools(self.supabase.ALL_TOOLS).invoke([SystemMessage(content=self.prompts.TOOLS_EXECUTION_SYSTEM)] + [HumanMessage(content=self.prompts.tool_execution_user(section))])
        
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"🔧 USING TOOLS: {[tc['name'] for tc in response.tool_calls]}")
        
        return {"messages": list(state["messages"]) + [response]}
    
    
    def send_response_step(self, state: ChatState) -> Dict[str, Any]:
        user_id = state["user_id"]
        new_message = state["messages"][-1]
        #new_message = next((msg for msg in reversed(state["messages"]) if isinstance(msg, ToolMessage)), None)

        if new_message:
            user_input = new_message.content
        else:
            user_input = ""
            
        context = self._build_conversation_context(state)

        response = self.llm.invoke(context)

        print(f"Response: {response.content}")

        return {"messages": [response]}
    
    def _build_conversation_context(self, state: ChatState) -> list:
        """
        Build conversation context using memory and current state.
        """
        
        messages = []
        
        messages.append(SystemMessage(content=self.prompts.ANSWER_SYSTEM))
        user_id = state["user_id"]
        messages.append(SystemMessage(content=f"IMPORTANTE: EL user_id de este cliente es {user_id}. Usar siempre user_id para utilizar herramientas que lo requieran"))
        
        #if state["costumer"]:
        #    messages.append(SystemMessage(content=f"Esta es la información actual del cliente: {state['costumer']}"))
        
        messages.extend(state["messages"])
        print(messages)
        
        return messages
    
    def should_use_tools(self, state: ChatState) -> bool:
        """
        Check if the conversation should continue based on the divided messages.
        """
        divided_message = state["divided_message"]
        print(f"aun faltan:   {divided_message}")
        if not divided_message or divided_message == []:
            print("No more divided messages to process.")
            return "send"
        return "retrieve"

    def run(self, query:str) -> ChatState:
        initial_state = ChatState(messages=query)
        final_state = self.workflow.invoke(initial_state)
        return ChatState(**final_state)
from typing import Annotated, Any, Dict, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .models import ChatState, Order, ProductDetails
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
        graph.add_node("detect_intent", self._detect_user_intent_step)
        graph.add_node("retrieve_data", self._retrieve_data_step)
        graph.add_node("tools", ToolNode(self.supabase.ALL_TOOLS))
        graph.add_node("send_response", self._send_response_step)
        graph.set_entry_point("extract_tools")
        graph.add_edge("detect_intent", "retrieve_data")
        graph.add_conditional_edges("retrieve_data", 
                                    self.should_use_tools,
                                    {
                                        True: "tools",
                                        False: "send_response"
                                    })
        graph.add_edge("tools", "retrieve_data")
        graph.add_edge("send_response", END)
        return graph.compile()
        
    
    def _detect_user_intent_step(self, state: ChatState) -> Dict[str, Any]:
        print(f"Dividing message and identifying intent: {state.query}")
        
        messages = [
            SystemMessage(content=self.prompts.MESSAGE_SPLITTING_SYSTEM),
            HumanMessage(content=self.prompts.message_splitting_user(state.messages))
        ]
        
        try:
            response = self.llm.invoke(messages)
            saludo = 0
            registro_datos_personales = 0
            registro_direccion = 0
            consulta_menu = 0
            seleccion_productos = 0
            confirmacion = 0
            finalizacion = 0
            for intent in response.content:
                if intent["intent"] == "saludo":
                    saludo = 1
                elif intent["intent"] == "registro_datos_personales":
                    registro_datos_personales = 1
                elif intent["intent"] == "registro_direccion":
                    registro_direccion = 1
                elif intent["intent"] == "consulta_menu":
                    consulta_menu = 1
                elif intent["intent"] == "seleccion_productos":
                    seleccion_productos = 1
                elif intent["intent"] == "confirmacion":
                    confirmacion = 1
                elif intent["intent"] == "finalizacion":
                    finalizacion = 1
                else:
                    general = 1
                    
            return {"divided_message": response.content,
                    "saludo": saludo,
                    "registro_datos_personales": registro_datos_personales,
                    "registro_direccion": registro_direccion,
                    "consulta_menu": consulta_menu,
                    "seleccion_productos": seleccion_productos,
                    "confirmacion": confirmacion,
                    "finalizacion": finalizacion,
                    "general": general}
        except Exception as e:
            print(e)
            return {"divided_message": []}
    
    
    def _retrieve_data_step(self, state: ChatState) -> Dict[str, Any]:
        return {"data": []}
    
    
    def _send_response_step(self, state: ChatState) -> Dict[str, Any]:
        
        messages = [
            SystemMessage(content=self.prompts.MESSAGE_SPLITTING_SYSTEM),
            HumanMessage(content=self.prompts.message_splitting_user(state.messages))
        ]
        
        try:
            response = self.llm.invoke(messages)
            return {"response": response.content}
        except Exception as e:
            print(e)
            return {"response": []}

    
    def should_use_tools(self, state: ChatState) -> bool:
        if state.saludo == 1:
            return True
        elif state.registro_datos_personales == 1:
            return True
        elif state.registro_direccion == 1:
            return True
        elif state.consulta_menu == 1:
            return True
        elif state.seleccion_productos == 1:
            return True
        elif state.confirmacion == 1:
            return True
        elif state.finalizacion == 1:
            return True
        return False

    def run(self, query:str) -> ChatState:
        initial_state = ChatState(query=query)
        final_state = self.workflow.invoke(initial_state)
        return ChatState(**final_state)
from typing import Annotated, Any, Dict, Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from .models import ChatState, CompanyAnalysis, CompanyInfo
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
        graph.add_node("send_response", self._analyze_step)
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
        
    
    def _analyze_company_content(self, company_name: str, content: str) -> CompanyAnalysis:
        structured_llm = self.llm.with_structured_output(CompanyAnalysis)
        
        messages = [
            SystemMessage(content=self.prompts.TOOL_ANALYSIS_SYSTEM),
            HumanMessage(content=self.prompts.tool_analysis_user(company_name, content))
        ]
        
        try:
            analysis = structured_llm.invoke(messages)
            return analysis
        except Exception as e:
            print(e)
            return CompanyAnalysis(
                pricing_model="Unknown",
                is_open_source=None,
                tech_stack=[],
                description="Failed",
                api_available=None,
                language_support=[],
                integration_capabilities=[]
            )
            
    def _retrieve_data_step(self, state: ChatState) -> Dict[str, Any]:
        divided_messages = getattr(state, "divided_messages", [])
        
        if not divided_messages:
            print("No extracted tools found, falling back to direct search")
            search_results = self.firecrawl.search_companies(state.query, num_results=4)
            tool_names = [
                result.get("metadata", {}).get("title", "Unknown")
                for result in search_results.data
            ]
        else:
            tool_names=extracted_tools[:4]
            
        print(f"Researching specific tools: {', '.join(tool_names)}")
        
        companies = []
        for tool_name in tool_names:
            tool_search_results = self.firecrawl.search_companies(tool_name + " official site", num_results=1)
            
            if tool_search_results:
                result = tool_search_results.data[0]
                url = result.get("url", "")
                
                company = CompanyInfo(
                    name=tool_name,
                    description=result.get("markdown", ""),
                    webiste=url,
                    tech_stack=[],
                    competitors=[]
                )
                
                scraped = self.firecrawl.scrape_company_pages(url)
                if scraped:
                    content = scraped.markdown
                    analysis = self._analyze_company_content(company.name, content)
                    
                    company.pricing_model = analysis.pricing_model
                    company.is_open_source = analysis.is_open_source
                    company.tech_stack = analysis.tech_stack
                    company.description = analysis.description
                    company.api_available = analysis.api_available
                    company.language_support = analysis.language_support
                    company.integration_capabilities = analysis.integration_capabilities
                    
                companies.append(company)
        
        return {"companies": companies}
    
    
    def _analyze_step(self, state: ChatState) -> Dict[str, Any]:
        print("Generating recommendations")
        
        company_data = ", ".join([
            company.model_dump_json() for company in state.companies
        ])
        
        messages = [
            SystemMessage(content=self.prompts.RECOMMENDATIONS_SYSTEM),
            HumanMessage(content=self.prompts.recommendations_user(state.query, company_data))
        ]
        
        response = self.llm.invoke(messages)
        return {"analysis": response.content}
    
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
"""
Clean state definition for the pizzeria chatbot.
This defines what information flows through our conversation graph.
"""
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class ProductDetails(BaseModel):
    product_id: str
    product_name:str
    product_type: str
    borde: Dict[str, Any] = {}
    adiciones: List[Dict[str, Any]] = []
    base_price: float = 0.0
    total_price: float = 0.0
    


class Order(BaseModel):
    order_id: str
    order_date: str
    order_total: float
    order_items: List[ProductDetails]


class ChatState(TypedDict):
    """
    Main state that flows through our conversation graph.
    
    Each key represents a piece of information that persists throughout the conversation.
    """
    
    # Core conversation data
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]  # Conversation history
    user_id: str                                    # Unique identifier for the user
    
    # Contextual information
    divided_message: Optional[List[Dict[str, str]]]  # Current message sections being processed
    tool_results: Optional[Dict[str, Any]]          # Results from tool executions
    
    # Customer information
    customer: Optional[Dict[str, Any]]              # Customer data from database
    
    # Order management
    active_order: Optional[Dict[str, Any]]          # Current order being processed
    
    # Order process states (0=not started, 1=in progress, 2=completed)
    order_states: Optional[Dict[str, int]]          # Unified state tracking
    
    # Legacy individual state fields (kept for compatibility)
    saludo: Optional[int]
    registro_datos_personales: Optional[int] 
    registro_direccion: Optional[int]
    consulta_menu: Optional[int]
    seleccion_productos: Optional[int]
    confirmacion: Optional[int]
    finalizacion: Optional[int]
    general: Optional[int]

    



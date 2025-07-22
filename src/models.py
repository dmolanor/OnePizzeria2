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
    user_id: str                                    # Unique identifier for the user
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]  # Conversation history
    
    # Contextual information
    divided_message: Optional[List[Dict[str, str]]] = None
    tool_results: Optional[Dict[str, Any]]
    
    # Customer information
    customer: Optional[Dict[str, Any]]              # Customer data from database
    
    # Current conversation context
    current_step: str                               # What step we're in (greeting, menu, order, etc.)
    
    # Order management
    active_order: Optional[Dict[str, Any]]          # Current order being processed
    
    # System flags
    saludo: int = 0                        # True if we need to greet the user
    registro_datos_personales: int = 0                           # True if we need to collect customer info
    registro_direccion: int = 0
    consulta_menu: Optional[int] = None                           # True if customer is ready to place order
    seleccion_productos: int = 0                     # True if customer is selecting products
    confirmacion: int = 0                        # True if customer is confirming order
    finalizacion: int = 0                        # True if order is being finalized

    



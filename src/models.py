"""
Clean state definition for the pizzeria chatbot.
This defines what information flows through our conversation graph.
"""
from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class ProductDetails(BaseModel):
    product_id: str
    product_name: str
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
    Simplified state that flows through our conversation graph.
    
    Each key represents a piece of information that persists throughout the conversation.
    """
    
    # Core conversation data
    user_id: str                                    # Unique identifier for the user
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]  # Conversation history
    
    # Customer information
    customer: Optional[Dict[str, Any]]              # Customer data from database
    
    # Order management
    active_order: Optional[Dict[str, Any]]          # Current order being processed
    
    # Final response
    response: Optional[str]                         # Bot's response to send to user

    



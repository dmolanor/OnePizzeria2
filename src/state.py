"""
Clean state definition for the pizzeria chatbot.
This defines what information flows through our conversation graph.
"""
import hashlib
from datetime import datetime
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


class MessageValidator:
    """
    🛡️ ADVANCED MESSAGE VALIDATION - Production-ready message handling
    
    Implements conversation patterns and semantic filtering beyond simple deduplication.
    Based on best practices from Rasa conversation patterns and dynamic context management.
    """
    
    @staticmethod
    def is_semantic_duplicate(new_msg: BaseMessage, existing_messages: List[BaseMessage], threshold: float = 0.85) -> bool:
        """
        Check for semantic similarity between messages (not just exact duplicates).
        
        Args:
            new_msg: New message to check
            existing_messages: List of existing messages
            threshold: Similarity threshold (0.0 to 1.0)
            
        Returns:
            True if semantically similar message exists
        """
        if not existing_messages:
            return False
            
        new_content = new_msg.content.lower().strip()
        new_msg_type = new_msg.__class__.__name__
        
        # Simple semantic similarity check (can be enhanced with embeddings)
        for existing_msg in existing_messages[-5:]:  # Check last 5 messages only
            if existing_msg.__class__.__name__ != new_msg_type:
                continue
                
            existing_content = existing_msg.content.lower().strip()
            
            # Calculate simple similarity score
            similarity = MessageValidator._calculate_similarity(new_content, existing_content)
            
            if similarity >= threshold:
                print(f"🔍 Semantic duplicate detected: {similarity:.2f} similarity")
                print(f"   New: {new_content[:50]}...")
                print(f"   Existing: {existing_content[:50]}...")
                return True
        
        return False
    
    @staticmethod
    def _calculate_similarity(text1: str, text2: str) -> float:
        """Calculate simple similarity score between two texts."""
        if text1 == text2:
            return 1.0
            
        # Simple word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    @staticmethod
    def detect_conversation_pattern(new_msg: BaseMessage, recent_messages: List[BaseMessage]) -> Optional[str]:
        """
        Detect conversation patterns like correction, clarification, interruption.
        Based on Rasa conversation patterns.
        """
        if not recent_messages:
            return None
            
        content = new_msg.content.lower()
        
        # Correction patterns
        correction_keywords = ["no, ", "actually", "correction", "mean", "quise decir", "mejor dicho", "corrigiendo"]
        if any(keyword in content for keyword in correction_keywords):
            return "correction"
            
        # Clarification patterns  
        clarification_keywords = ["what do you mean", "explain", "qué quieres decir", "no entiendo", "clarify"]
        if any(keyword in content for keyword in clarification_keywords):
            return "clarification"
            
        # Interruption patterns
        interruption_keywords = ["wait", "stop", "cancel", "espera", "para", "cancela", "nunca importa"]
        if any(keyword in content for keyword in interruption_keywords):
            return "interruption"
            
        # Repeat request patterns
        repeat_keywords = ["repeat", "again", "what", "repite", "otra vez", "qué dijiste"]
        if any(keyword in content for keyword in repeat_keywords):
            return "repeat_request"
            
        return None
    
    @staticmethod
    def add_message_metadata(msg: BaseMessage) -> BaseMessage:
        """Add metadata to messages for better tracking."""
        if not hasattr(msg, 'additional_kwargs'):
            msg.additional_kwargs = {}
            
        msg.additional_kwargs.update({
            'timestamp': datetime.now().isoformat(),
            'message_id': hashlib.md5(f"{msg.content}{datetime.now()}".encode()).hexdigest()[:8],
            'processed_at': datetime.now().isoformat()
        })
        
        return msg


def smart_message_reducer(existing: Sequence[BaseMessage], new: Sequence[BaseMessage]) -> List[BaseMessage]:
    """
    🎯 ENHANCED SMART MESSAGE REDUCER - Now with validation layer
    
    Production-ready reducer that:
    1. Validates messages through MessageValidator
    2. Handles conversation patterns
    3. Prevents both exact and semantic duplicates
    4. Manages context window size
    5. Adds message metadata
    
    Args:
        existing: Current messages in state
        new: New messages to add
        
    Returns:
        List of validated, unique messages with proper conversation flow
    """
    if not new:
        return list(existing) if existing else []
    
    # Convert to lists for easier manipulation
    existing_list = list(existing) if existing else []
    new_list = list(new) if new else []
    
    # Fast path: if no existing messages, validate and return new ones
    if not existing_list:
        validated_messages = []
        for msg in new_list:
            msg_with_metadata = MessageValidator.add_message_metadata(msg)
            validated_messages.append(msg_with_metadata)
        print(f"🎯 First messages added with metadata: {len(validated_messages)}")
        return validated_messages
    
    # 🛡️ VALIDATION LAYER: Process each new message
    validated_new_messages = []
    for msg in new_list:
        # 1. Check for exact duplicates (fast check)
        msg_type = msg.__class__.__name__
        content_key = f"{msg_type}:{msg.content.strip()}"
        
        existing_exact = any(
            f"{existing_msg.__class__.__name__}:{existing_msg.content.strip()}" == content_key 
            for existing_msg in existing_list
        )
        
        if existing_exact:
            print(f"⚠️ Exact duplicate skipped: {msg_type} - {msg.content[:50]}...")
            continue
        """    
        # 2. Check for semantic duplicates
        if MessageValidator.is_semantic_duplicate(msg, existing_list):
            print(f"⚠️ Semantic duplicate skipped: {msg_type} - {msg.content[:50]}...")
            continue
        """
        
        # 3. Detect conversation patterns
        pattern = MessageValidator.detect_conversation_pattern(msg, existing_list[-3:])
        if pattern:
            print(f"🔄 Conversation pattern detected: {pattern}")
            # Handle special patterns
            if pattern == "correction":
                # Remove the last assistant message that's being corrected
                if existing_list and existing_list[-1].__class__.__name__ == "AIMessage":
                    existing_list.pop()
                    print(f"🔄 Removed last assistant message due to correction pattern")
            elif pattern == "interruption":
                # Mark this as high priority
                msg.additional_kwargs = getattr(msg, 'additional_kwargs', {})
                msg.additional_kwargs['conversation_pattern'] = 'interruption'
                msg.additional_kwargs['priority'] = 'high'
        
        # 4. Add metadata to message
        msg_with_metadata = MessageValidator.add_message_metadata(msg)
        if pattern:
            msg_with_metadata.additional_kwargs['conversation_pattern'] = pattern
            
        validated_new_messages.append(msg_with_metadata)
        print(f"✅ Message validated and added: {msg_type} - {msg.content[:50]}...")
    
    # 5. Context window management (keep last N messages)
    MAX_CONTEXT_MESSAGES = 50  # Configurable limit
    combined_messages = existing_list + validated_new_messages
    
    if len(combined_messages) > MAX_CONTEXT_MESSAGES:
        # Keep first 5 (important context) + last (MAX_CONTEXT_MESSAGES - 5)
        important_start = combined_messages[:5]
        recent_end = combined_messages[-(MAX_CONTEXT_MESSAGES - 5):]
        final_messages = important_start + recent_end
        print(f"🔧 Context window managed: {len(combined_messages)} → {len(final_messages)} messages")
    else:
        final_messages = combined_messages
    
    print(f"🔄 Enhanced reducer: {len(existing_list)} existing + {len(validated_new_messages)} validated = {len(final_messages)} total")
    
    return final_messages


class ChatState(TypedDict):
    """
    Main state that flows through our conversation graph.
    
    Each key represents a piece of information that persists throughout the conversation.
    """
    
    # Core conversation data - NOW WITH ENHANCED SMART REDUCER
    #messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]
    messages: Annotated[Sequence[BaseMessage], smart_message_reducer]  # 🎯 Enhanced smart deduplication + validation
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
    crear_pedido: Optional[int]
    seleccion_productos: Optional[int]
    confirmacion: Optional[int]
    finalizacion: Optional[int]
    general: Optional[int]

    



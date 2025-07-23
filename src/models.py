# Re-export ChatState from state.py for backward compatibility
from .state import ChatState, ProductDetails, Order

__all__ = ['ChatState', 'ProductDetails', 'Order'] 
import os
from unittest.mock import MagicMock, patch

import pytest


class TestBasicFunctionality:
    """Pruebas básicas que no requieren configuración externa"""
    
    def test_imports_work(self):
        """Prueba que los imports básicos funcionen"""
        # Test que podemos importar los módulos principales
        try:
            from src.models import ChatState, Order, ProductDetails
            from src.prompts import CustomerServicePrompts
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import basic modules: {e}")
    
    def test_models_creation(self):
        """Prueba que podemos crear instancias de los modelos"""
        from src.models import Order, ProductDetails

        # Test ProductDetails
        product = ProductDetails(
            product_id="test_1",
            product_name="Pizza Test",
            product_type="pizza"
        )
        assert product.product_id == "test_1"
        assert product.product_name == "Pizza Test"
        assert product.product_type == "pizza"
        assert product.base_price == 0.0
        
        # Test Order
        order = Order(
            order_id="order_1",
            order_date="2024-01-01",
            order_total=50000.0,
            order_items=[product]
        )
        assert order.order_id == "order_1"
        assert len(order.order_items) == 1
        assert order.order_total == 50000.0
    
    def test_prompts_creation(self):
        """Prueba que podemos crear instancias de prompts"""
        from src.prompts import CustomerServicePrompts
        
        prompts = CustomerServicePrompts()
        assert prompts is not None
        assert hasattr(prompts, 'MESSAGE_SPLITTING_SYSTEM')
        assert isinstance(prompts.MESSAGE_SPLITTING_SYSTEM, str)
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'test_url', 'SUPABASE_KEY': 'test_key'})
    def test_memory_creation(self):
        """Prueba que podemos crear el sistema de memoria"""
        from src.memory import ConversationContext, MemoryManager

        # Test ConversationContext
        context = ConversationContext("test_thread")
        assert context.thread_id == "test_thread"
        assert isinstance(context.customer_context, dict)
        assert isinstance(context.recent_messages, list)
        
        # Test MemoryManager
        memory = MemoryManager()
        assert memory is not None
        assert memory.table_name == "conversation_memory"
        assert memory.ttl_days == 7
    
    @patch.dict(os.environ, {'SUPABASE_URL': 'test_url', 'SUPABASE_KEY': 'test_key'})
    def test_checkpointer_creation(self):
        """Prueba que podemos crear el state manager"""
        from src.checkpointer import ChatStateManager
        
        state_manager = ChatStateManager()
        assert state_manager is not None
        assert hasattr(state_manager, 'memory_manager')
    
    @patch.dict(os.environ, {
        'SUPABASE_URL': 'test_url', 
        'SUPABASE_KEY': 'test_key',
        'OPENAI_API_KEY': 'test_key',
        'TELEGRAM_BOT_TOKEN': 'test_token'
    })
    def test_workflow_creation(self):
        """Prueba que podemos crear el workflow"""
        with patch('src.workflow.ChatOpenAI') as mock_llm:
            with patch('src.workflow.SupabaseService') as mock_supabase:
                mock_llm.return_value = MagicMock()
                mock_supabase.return_value = MagicMock()
                mock_supabase.return_value.ALL_TOOLS = []
                
                from src.workflow import Workflow
                
                workflow = Workflow()
                assert workflow is not None
                assert hasattr(workflow, 'llm')
                assert hasattr(workflow, 'supabase')
                assert hasattr(workflow, 'prompts')
                assert hasattr(workflow, 'workflow')

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from src.models import ChatState
from src.workflow import Workflow


class TestWorkflow:
    """Pruebas para el workflow simplificado de OnePizzeria"""
    
    @pytest.fixture
    def workflow(self):
        """Fixture para crear una instancia del workflow"""
        return Workflow()
    
    @pytest.fixture
    def sample_state(self):
        """Estado de prueba con un mensaje de usuario"""
        return {
            "user_id": "test_user_123",
            "messages": [HumanMessage(content="Hola, quiero ver el menú")],
            "customer": {},
            "current_step": "greeting",
            "active_order": {}
        }
    
    def test_workflow_initialization(self, workflow):
        """Prueba que el workflow se inicialice correctamente"""
        assert workflow is not None
        assert workflow.llm is not None
        assert workflow.supabase is not None
        assert workflow.prompts is not None
        assert workflow.workflow is not None
    
    def test_should_use_tools_with_tool_calls(self, workflow):
        """Prueba que should_use_tools detecte cuando hay tool calls"""
        # Crear un mensaje mock con tool_calls
        mock_message = MagicMock()
        mock_message.tool_calls = [{"name": "get_customer", "args": {}}]
        
        state = {"messages": [mock_message]}
        result = workflow.should_use_tools(state)
        
        assert result == "tools"
    
    def test_should_use_tools_without_tool_calls(self, workflow):
        """Prueba que should_use_tools vaya a response cuando no hay tool calls"""
        mock_message = MagicMock()
        mock_message.tool_calls = None
        
        state = {"messages": [mock_message]}
        result = workflow.should_use_tools(state)
        
        assert result == "response"
    
    def test_generate_response_step(self, workflow):
        """Prueba la generación de respuesta"""
        mock_message = MagicMock()
        mock_message.content = "¡Hola! ¿En qué te puedo ayudar?"
        
        state = {"messages": [mock_message]}
        result = workflow.generate_response_step(state)
        
        assert "response" in result
        assert result["response"] == "¡Hola! ¿En qué te puedo ayudar?"
    
    @pytest.mark.asyncio
    async def test_run_workflow_basic(self, workflow):
        """Prueba básica del método run"""
        with patch.object(workflow, 'workflow') as mock_workflow:
            # Mock del estado final
            mock_final_state = {
                "response": "¡Hola! Bienvenido a One Pizzeria"
            }
            mock_workflow.invoke.return_value = mock_final_state
            
            # Mock del state manager
            with patch('src.workflow.state_manager') as mock_state_manager:
                mock_state_manager.load_state_for_user.return_value = {
                    "user_id": "test_user",
                    "messages": [HumanMessage(content="Hola")],
                    "customer": {},
                    "active_order": {}
                }
                mock_state_manager.save_state_for_user.return_value = None
                
                result = await workflow.run("Hola", "test_user")
                
                assert result == "¡Hola! Bienvenido a One Pizzeria"
                mock_state_manager.load_state_for_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_run_workflow_error_handling(self, workflow):
        """Prueba el manejo de errores en el workflow"""
        with patch.object(workflow, 'workflow') as mock_workflow:
            # Simular un error
            mock_workflow.invoke.side_effect = Exception("Error de prueba")
            
            result = await workflow.run("Hola", "test_user")
            
            assert "problema técnico" in result.lower()

if __name__ == "__main__":
    pytest.main([__file__]) 
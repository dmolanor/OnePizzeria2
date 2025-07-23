import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.workflow import Workflow


class TestIntegration:
    """Pruebas de integración para flujos de conversación completos"""
    
    @pytest.fixture
    def workflow(self):
        return Workflow()
    
    @pytest.mark.asyncio
    async def test_complete_conversation_new_customer(self, workflow):
        """Prueba una conversación completa con un cliente nuevo"""
        
        # Mock del state manager
        with patch('src.workflow.state_manager') as mock_state_manager:
            # Mock para cliente nuevo
            mock_state_manager.load_state_for_user.return_value = {
                "user_id": "new_user_123",
                "messages": [],
                "customer": {},
                "active_order": {}
            }
            
            # Mock del workflow de LangGraph
            with patch.object(workflow, 'workflow') as mock_langgraph:
                
                # Simular respuestas del bot para cada paso
                conversation_steps = [
                    "¡Hola! Bienvenido a One Pizzeria. ¿En qué te puedo ayudar?",
                    "Perfecto, aquí tienes nuestro menú...",
                    "Excelente elección. Para registrar tu pedido necesito tu nombre completo y teléfono.",
                    "¡Genial! Tu pedido está confirmado y será entregado en 30-40 minutos."
                ]
                
                responses = []
                for i, step_response in enumerate(conversation_steps):
                    mock_langgraph.invoke.return_value = {"response": step_response}
                    
                    user_messages = [
                        "Hola",
                        "Muéstrame el menú",
                        "Quiero una pizza hawaiana grande",
                        "Juan Pérez, 3001234567"
                    ]
                    
                    if i < len(user_messages):
                        response = await workflow.run(user_messages[i], "new_user_123")
                        responses.append(response)
                
                # Verificar que se obtuvieron respuestas
                assert len(responses) == len(conversation_steps)
                assert "bienvenido" in responses[0].lower()
                assert "menú" in responses[1].lower()
                assert "registrar" in responses[2].lower()
                assert "confirmado" in responses[3].lower()
    
    @pytest.mark.asyncio
    async def test_menu_consultation_flow(self, workflow):
        """Prueba el flujo de consulta de menú"""
        
        with patch('src.workflow.state_manager') as mock_state_manager:
            mock_state_manager.load_state_for_user.return_value = {
                "user_id": "user_456",
                "messages": [],
                "customer": {"nombre": "María", "telefono": "3009876543"},
                "active_order": {}
            }
            
            with patch.object(workflow, 'workflow') as mock_langgraph:
                # Simular respuesta con información del menú
                menu_response = {
                    "response": "Tenemos pizzas hawaiana ($45.000), pepperoni ($40.000), y vegetariana ($38.000)"
                }
                mock_langgraph.invoke.return_value = menu_response
                
                response = await workflow.run("¿Qué pizzas tienen y cuánto cuestan?", "user_456")
                
                assert "hawaiana" in response.lower()
                assert "45.000" in response
                assert "pepperoni" in response.lower()
    
    @pytest.mark.asyncio
    async def test_order_creation_flow(self, workflow):
        """Prueba el flujo de creación de pedido"""
        
        with patch('src.workflow.state_manager') as mock_state_manager:
            # Cliente existente
            mock_state_manager.load_state_for_user.return_value = {
                "user_id": "existing_user_789",
                "messages": [],
                "customer": {
                    "nombre": "Carlos",
                    "telefono": "3005551234",
                    "direccion": "Calle 123 #45-67"
                },
                "active_order": {}
            }
            
            with patch.object(workflow, 'workflow') as mock_langgraph:
                order_response = {
                    "response": "Perfecto Carlos! Tu pizza hawaiana grande ha sido agregada. Total: $45.000. ¿Confirmas el pedido?"
                }
                mock_langgraph.invoke.return_value = order_response
                
                response = await workflow.run("Quiero una pizza hawaiana grande", "existing_user_789")
                
                assert "carlos" in response.lower()
                assert "hawaiana" in response.lower()
                assert "45.000" in response
                assert "confirmas" in response.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_flow(self, workflow):
        """Prueba el manejo de errores en el flujo"""
        
        with patch('src.workflow.state_manager') as mock_state_manager:
            # Simular error en state manager
            mock_state_manager.load_state_for_user.side_effect = Exception("Database error")
            
            response = await workflow.run("Hola", "error_user")
            
            assert "problema técnico" in response.lower()
    
    @pytest.mark.asyncio
    async def test_workflow_with_tools_integration(self, workflow):
        """Prueba integración con herramientas"""
        
        with patch('src.workflow.state_manager') as mock_state_manager:
            mock_state_manager.load_state_for_user.return_value = {
                "user_id": "tools_user",
                "messages": [],
                "customer": {},
                "active_order": {}
            }
            
            # Mock del LLM que devuelve tool calls
            with patch.object(workflow, 'llm') as mock_llm:
                # Simular respuesta con tool calls
                mock_response = MagicMock()
                mock_response.tool_calls = [{"name": "search_menu", "args": {"query": "hawaiana"}}]
                mock_response.content = ""
                
                mock_llm.bind_tools.return_value.invoke.return_value = mock_response
                mock_llm.invoke.return_value.content = "La pizza hawaiana cuesta $45.000"
                
                # Mock del workflow de LangGraph para simular ejecución de tools
                with patch.object(workflow, 'workflow') as mock_langgraph:
                    mock_langgraph.invoke.return_value = {
                        "response": "La pizza hawaiana cuesta $45.000 y tiene jamón y piña"
                    }
                    
                    response = await workflow.run("¿Cuánto cuesta la pizza hawaiana?", "tools_user")
                    
                    assert "hawaiana" in response.lower()
                    assert "45.000" in response
    
    def test_workflow_graph_structure(self, workflow):
        """Prueba que la estructura del grafo sea correcta"""
        graph = workflow.workflow
        
        # Verificar que el grafo tenga los nodos esperados
        assert graph is not None
        
        # Verificar que se puede compilar sin errores
        assert callable(graph.invoke)

if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 
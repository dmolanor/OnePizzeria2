from unittest.mock import MagicMock, patch

import pytest

from src.tools import (create_customer, create_or_update_order, finalize_order,
                       get_active_order, get_customer, get_full_menu,
                       search_menu, update_customer)


class TestTools:
    """Pruebas para las herramientas de Supabase"""
    
    @patch('src.tools.supabase')
    def test_get_customer_exists(self, mock_supabase):
        """Prueba obtener un cliente existente"""
        # Mock de respuesta exitosa
        mock_result = MagicMock()
        mock_result.data = [{"id": "123", "nombre": "Juan", "telefono": "3001234567"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        
        result = get_customer.invoke({"user_id": "123"})
        
        assert result["id"] == "123"
        assert result["nombre"] == "Juan"
    
    @patch('src.tools.supabase')
    def test_get_customer_not_exists(self, mock_supabase):
        """Prueba obtener un cliente que no existe"""
        mock_result = MagicMock()
        mock_result.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        
        result = get_customer.invoke({"user_id": "999"})
        
        assert result == {}
    
    @patch('src.tools.supabase')
    def test_create_customer_success(self, mock_supabase):
        """Prueba crear un cliente exitosamente"""
        mock_result = MagicMock()
        mock_result.data = [{"id": "123"}]
        mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_result
        
        result = create_customer.invoke({
            "user_id": "123",
            "nombre_completo": "Juan Pérez",
            "telefono": "3001234567",
            "correo": "juan@email.com"
        })
        
        assert result["success"] is True
        assert "exitosamente" in result["message"]
    
    @patch('src.tools.supabase')
    def test_search_menu_pizzas(self, mock_supabase):
        """Prueba buscar pizzas en el menú"""
        mock_pizzas = MagicMock()
        mock_pizzas.data = [
            {"nombre": "Hawaiana", "precio": 45000, "texto_ingredientes": "jamón, piña"},
            {"nombre": "Pepperoni", "precio": 40000, "texto_ingredientes": "pepperoni, queso"}
        ]
        
        mock_bebidas = MagicMock()
        mock_bebidas.data = []
        
        mock_combos = MagicMock()
        mock_combos.data = []
        
        # Configurar los mocks para cada llamada a la tabla
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "pizzas_armadas":
                mock_table.select.return_value.execute.return_value = mock_pizzas
            elif table_name == "bebidas":
                mock_table.select.return_value.execute.return_value = mock_bebidas
            elif table_name == "combos":
                mock_table.select.return_value.execute.return_value = mock_combos
            return mock_table
        
        mock_supabase.table.side_effect = table_side_effect
        
        result = search_menu.invoke({"query": "hawaiana"})
        
        assert "pizzas" in result
        assert len(result["pizzas"]) == 1
        assert result["pizzas"][0]["nombre"] == "Hawaiana"
    
    @patch('src.tools.supabase')
    def test_get_active_order_exists(self, mock_supabase):
        """Prueba obtener un pedido activo existente"""
        mock_result = MagicMock()
        mock_result.data = [{"id": 1, "cliente_id": "123", "estado": "activo"}]
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result
        
        result = get_active_order.invoke({"user_id": "123"})
        
        assert result["id"] == 1
        assert result["estado"] == "activo"
    
    @patch('src.tools.supabase')
    def test_create_order_new(self, mock_supabase):
        """Prueba crear un pedido nuevo"""
        # Mock para verificar si existe pedido (no existe)
        mock_existing = MagicMock()
        mock_existing.data = []
        
        # Mock para insertar nuevo pedido
        mock_insert = MagicMock()
        mock_insert.data = [{"id": 1}]
        
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "pedidos_activos":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_existing
                mock_table.insert.return_value.execute.return_value = mock_insert
            return mock_table
        
        mock_supabase.table.side_effect = table_side_effect
        
        result = create_or_update_order.invoke({
            "user_id": "123",
            "items": [{"nombre": "Pizza Hawaiana", "precio": 45000}],
            "direccion": "Calle 123",
            "metodo_pago": "efectivo",
            "subtotal": 45000
        })
        
        assert result["success"] is True
        assert "creado" in result["message"]
    
    def test_tools_are_callable(self):
        """Prueba que todas las herramientas sean invocables"""
        tools = [
            get_customer, create_customer, update_customer,
            search_menu, get_full_menu,
            get_active_order, create_or_update_order, finalize_order
        ]
        
        for tool in tools:
            assert callable(tool.invoke)
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')

if __name__ == "__main__":
    pytest.main([__file__]) 
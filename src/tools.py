import os

from langchain_core.tools import tool

from config import supabase

# PEDIDOS

@tool
def get_order_by_id(id: int) -> dict:
    """
    Obtiene un pedido activo por su ID.
    
    Args:
        id: ID numérico del pedido
        
    Returns:
        dict: Datos del pedido si existe
    """
    try:
        result = supabase.table("pedidos_activos").select("*").eq("id", id).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": f"Pedido con ID {id} no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar pedido: {str(e)}"}

#@tool
#def get_order_by_client_id( client_id: int) -> list[dict]:
#    return supabase.table("pedidos_activos").select("*").eq("cliente_id", client_id).execute().data
@tool
def create_order(cliente_id: str, items: list, total: float) -> dict:
    """
    Crea un nuevo pedido activo.
    
    Args:
        cliente_id: ID del cliente (string)
        items: Lista de productos del pedido 
        total: Total del pedido (float)
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        create_order("7315133184", [{"pizza": "pepperoni", "tamaño": "large", "precio": 25000}], 25000)
    """
    try:
        order_data = {
            "cliente_id": cliente_id,
            "items": items,
            "total": total
        }
        result = supabase.table("pedidos_activos").insert(order_data).execute()
        return {"success": "Pedido creado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al crear pedido: {str(e)}"}
@tool
def update_order(id: int, cliente_id: str = None, items: list = None, total: float = None) -> dict:
    """
    Actualiza un pedido activo existente.
    
    Args:
        id: ID del pedido a actualizar (int) - requerido
        cliente_id: ID del cliente (string, opcional)
        items: Lista de productos del pedido (opcional)
        total: Total del pedido (float, opcional)
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        update_data = {}
        
        if cliente_id:
            update_data["cliente_id"] = cliente_id
        if items:
            update_data["items"] = items
        if total:
            update_data["total"] = total
            
        if not update_data:
            return {"error": "No se proporcionaron datos para actualizar"}
        
        result = supabase.table("pedidos_activos").update(update_data).eq("id", id).execute()
        return {"success": "Pedido actualizado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al actualizar pedido: {str(e)}"}
@tool
def delete_order(id: int) -> dict:
    """Elimina un pedido activo"""
    try:
        result = supabase.table("pedidos_activos").delete().eq("id", id).execute()
        return {"success": "Pedido eliminado exitosamente"}
    except Exception as e:
        return {"error": f"Error al eliminar pedido: {str(e)}"}
@tool    
def finish_order(id: int) -> dict:
    """Finaliza un pedido activo y lo guarda en la tabla de pedidos finalizados"""
    try:
        # Primero obtener el pedido completo
        current_order = supabase.table("pedidos_activos").select("*").eq("id", id).execute()
        if not current_order.data:
            return {"error": "Pedido no encontrado"}
        
        order_data = current_order.data[0]
        
        # Eliminar de activos y agregar a finalizados
        supabase.table("pedidos_activos").delete().eq("id", id).execute()
        supabase.table("pedidos_finalizados").insert(order_data).execute()
        return {"success": "Pedido finalizado exitosamente"}
    except Exception as e:
        return {"error": f"Error al finalizar pedido: {str(e)}"}


# CLIENTES
@tool
def get_client_by_id(user_id: str) -> dict:
    """
    Obtiene un cliente por su ID de Telegram.
    
    Args:
        user_id: El ID del usuario de Telegram (como string)
        
    Returns:
        dict: Los datos del cliente si existe
        
    Example:
        get_client_by_id("7315133184")
    """
    try:
        result = supabase.table("clientes").select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": f"Cliente con ID {user_id} no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar cliente: {str(e)}"}

#@tool
#def get_client_by_full_name( full_name: str) -> dict:
#    return supabase.table("clientes").select("*").eq("nombre_completo", full_name).execute().data[0]
@tool
def create_client(id: str, nombre_completo: str, telefono: str, direccion: str = None) -> dict:
    """
    Crea un nuevo cliente en la base de datos.
    
    Args:
        id: ID del usuario de Telegram (string)
        nombre_completo: Nombre completo del cliente (string)
        telefono: Número de teléfono (string)  
        direccion: Dirección del cliente (string, opcional)
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        create_client("7315133184", "Diego Molano", "3203782744", "Calle 127A #11B-76 Apto 401")
    """
    try:
        # Split nombre_completo into nombre and apellido (required by DB schema)
        parts = nombre_completo.split(" ", 1)
        nombre = parts[0] if parts else ""
        apellido = parts[1] if len(parts) > 1 else ""
        
        client_data = {
            "id": id,
            "nombre_completo": nombre_completo,
            "nombre": nombre,
            "apellido": apellido,
            "telefono": telefono
        }
        
        if direccion:
            client_data["direccion"] = direccion
        
        result = supabase.table("clientes").insert(client_data).execute()
        return {"success": "Cliente creado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al crear cliente: {str(e)}"}

@tool  
def update_client(id: str, nombre_completo: str = None, telefono: str = None, direccion: str = None) -> dict:
    """
    Actualiza un cliente existente en la base de datos.
    
    Args:
        id: ID del usuario de Telegram (string) - requerido para identificar el cliente
        nombre_completo: Nombre completo del cliente (string, opcional)
        telefono: Número de teléfono (string, opcional)
        direccion: Dirección del cliente (string, opcional)
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        update_client("7315133184", nombre_completo="Diego Molano", telefono="3203782744", direccion="Calle 127A #11B-76 Apto 401")
    """
    try:
        update_data = {}
        
        if nombre_completo:
            # Split nombre_completo into nombre and apellido
            parts = nombre_completo.split(" ", 1)
            nombre = parts[0] if parts else ""
            apellido = parts[1] if len(parts) > 1 else ""
            
            update_data["nombre_completo"] = nombre_completo
            update_data["nombre"] = nombre  
            update_data["apellido"] = apellido
            
        if telefono:
            update_data["telefono"] = telefono  
        if direccion:
            update_data["direccion"] = direccion
            
        if not update_data:
            return {"error": "No se proporcionaron datos para actualizar"}
        
        result = supabase.table("clientes").update(update_data).eq("id", id).execute()
        return {"success": "Cliente actualizado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al actualizar cliente: {str(e)}"}


# PIZZAS
@tool
def get_pizza_by_name(name: str) -> dict:
    """
    Obtiene una pizza por su nombre desde la base de datos.
    
    Args:
        name: Nombre de la pizza a buscar (ej: "pepperoni", "hawaiana", "margherita")
        
    Returns:
        dict: Datos de la pizza si existe
        
    Example:
        get_pizza_by_name("pepperoni")
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("pizzas_armadas").select("*").eq("nombre", name).execute()
        
        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("pizzas_armadas").select("*").ilike("nombre", f"%{name}%").execute()
        
        if result.data:
            return result.data[0]
        else:
            return {"error": f"Pizza '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar pizza: {str(e)}"}

#@tool
#def get_pizzas_by_type( type: str) -> list[dict]:
#    return supabase.table("pizzas_armadas").select("*").eq("tipo", type).execute().data

# COMBOS

#@tool
#def get_combos(self) -> list[dict]:
#    return supabase.table("combos").select("*").execute().data

#@tool
#def get_combo_by_name( name: str) -> dict:
#    return supabase.table("combos").select("*").eq("nombre", name).execute().data[0]

# BEBIDAS

#@tool
#def get_beverages(self) -> list[dict]:
#    return supabase.table("bebidas").select("*").execute().data

@tool
def get_beverage_by_name(name: str) -> dict:
    """
    Obtiene una bebida por su nombre desde la base de datos.
    
    Args:
        name: Nombre de la bebida a buscar (ej: "coca cola", "agua", "jugo")
        
    Returns:
        dict: Datos de la bebida si existe
        
    Example:
        get_beverage_by_name("coca cola")
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("bebidas").select("*").eq("nombre_producto", name).execute()
        
        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("bebidas").select("*").ilike("nombre_producto", f"%{name}%").execute()
        
        if result.data:
            return result.data[0]
        else:
            return {"error": f"Bebida '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar bebida: {str(e)}"}

#@tool
#def get_beverages_by_sugar( sugar: bool) -> list[dict]:
#    return supabase.table("bebidas").select("*").eq("azucar", sugar).execute().data

#@tool
#def get_beverages_by_alcohol( alcohol: bool) -> list[dict]:
#    return supabase.table("bebidas").select("*").eq("alcohol", alcohol).execute().data

# ADICIONES

#@tool
#def get_aditions(self) -> list[dict]:
#    return supabase.table("adiciones").select("*").execute().data

#@tool
#def get_adition_by_name( name: str) -> dict:
#    return supabase.table("adiciones").select("*").eq("nombre", name).execute().data[0]

# BORDES

#@tool
#def get_borders(self) -> list[dict]:
#    return supabase.table("bordes").select("*").execute().data

#@tool
#def get_border_by_name( name: str) -> dict:
#    return supabase.table("bordes").select("*").eq("nombre", name).execute().data[0]


#CUSTOMER_TOOLS = [get_client_by_phone_number, get_client_by_full_name, create_client, update_client]
CUSTOMER_TOOLS = [get_client_by_id, create_client, update_client]
#ORDER_TOOLS = [get_orders, get_order_by_id, get_order_by_client_id, create_order, update_order, delete_order, finish_order]  # Removed get_menu - only use search_menu and send_full_menu
ORDER_TOOLS = [get_order_by_id, create_order, update_order, delete_order, finish_order]  # Removed get_menu - only use search_menu and send_full_menu
MENU_TOOLS = [get_pizza_by_name, get_beverage_by_name]

# Complete tool list for the agent
ALL_TOOLS = CUSTOMER_TOOLS + MENU_TOOLS + ORDER_TOOLS
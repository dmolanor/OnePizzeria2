from contextlib import nullcontext
import os

from langchain_core.tools import tool
from pydantic.v1.errors import NoneIsAllowedError

from config import supabase

#=========================================================#
#---------------------- ORDER TOOLS ----------------------#
#=========================================================#

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
            return {"success": "Pedido encontrado", "data": result.data[0]}
        else:
            return {"error": f"Pedido con ID {id} no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar pedido: {str(e)}"}


@tool
def get_active_order_by_client(cliente_id: str) -> dict:
    """
    Obtiene el pedido activo de un cliente específico.
    
    Args:
        cliente_id: ID del cliente (string)
        
    Returns:
        dict: Datos del pedido activo si existe, o error si no hay pedido activo
        
    Example:
        get_active_order_by_client("7315133184")
    """
    try:
        result = supabase.table("pedidos_activos").select("*").eq("cliente_id", cliente_id).execute()
        if result.data:
            return {"success": "Se ha encontrado un pedido activo", "data": result.data[0]}  # Retorna el primer pedido activo encontrado
        else:
            return {"fail": f"No hay pedido activo para el cliente {cliente_id}","data": {}}
    except Exception as e:
        return {"error": f"Error al buscar pedido activo: {str(e)}"}
@tool
def create_order(cliente_id: str, items: list = None, total: float = 0.0, direccion_entrega: str = None, estado: str = "PREPARANDO") -> dict:
    """
    Crea un nuevo pedido activo.
    
    Args:
        cliente_id: ID del cliente (string)
        items: Lista de productos del pedido (opcional)
        total: Total del pedido (float, opcional)
        direccion_entrega: Dirección de entrega (string, opcional)
        estado: Estado del pedido (string, por defecto "PREPARANDO")
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        create_order("7315133184", [{"pizza": "pepperoni", "tamaño": "large", "precio": 25000}], 25000, "Calle 123")
    """
    try:
        # Preparar datos del pedido en formato JSONB
        pedido_data = {
            "items": items or [],
            "total": total,
            "fecha_creacion": "now()"
        }
        
        order_data = {
            "cliente_id": cliente_id,
            "estado": estado,
            "direccion_entrega": direccion_entrega,
            "pedido": pedido_data
        }
        
        result = supabase.table("pedidos_activos").insert(order_data).execute()
        return {"success": "Pedido creado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al crear pedido: {str(e)}"}
@tool
def update_order(id: int, items: list = None, total: float = None, direccion_entrega: str = None, metodo_pago: str = None, estado: str = None) -> dict:
    """
    Actualiza un pedido activo existente.
    
    Args:
        id: ID del pedido a actualizar (int) - requerido
        items: Lista de productos del pedido (opcional)
        total: Total del pedido (float, opcional)
        direccion_entrega: Dirección de entrega (string, opcional)
        metodo_pago: Método de pago (string, opcional)
        estado: Estado del pedido (string, opcional)
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Primero obtener el pedido actual para preservar los datos existentes
        current_order = supabase.table("pedidos_activos").select("*").eq("id", id).execute()
        if not current_order.data:
            return {"error": "Pedido no encontrado"}
        
        current_data = current_order.data[0]
        current_pedido = current_data.get("pedido", {})
        
        update_data = {}
        
        # Actualizar campos directos
        if direccion_entrega is not None:
            update_data["direccion_entrega"] = direccion_entrega
        if metodo_pago is not None:
            update_data["metodo_pago"] = metodo_pago
        if estado is not None:
            update_data["estado"] = estado
            
        # Actualizar datos del pedido (JSONB)
        if items is not None or total is not None:
            updated_pedido = current_pedido.copy()
            if items is not None:
                updated_pedido["items"] = items
            if total is not None:
                updated_pedido["total"] = total
            update_data["pedido"] = updated_pedido
            
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
def finish_order(cliente_id: str) -> dict:
    """
    Finaliza el pedido activo de un cliente y lo mueve a pedidos finalizados.
    
    Args:
        cliente_id: ID del cliente (string)
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Primero obtener el pedido activo del cliente
        current_order = supabase.table("pedidos_activos").select("*").eq("cliente_id", cliente_id).execute()
        if not current_order.data:
            return {"error": "No hay pedido activo para este cliente"}
        
        order_data = current_order.data[0]
        order_id = order_data["id"]
        
        # Preparar datos para pedidos_finalizados (sin el ID auto-increment)
        finalized_data = {
            "cliente_id": order_data["cliente_id"],
            "estado": "ENTREGADO",  # Estado final
            "direccion_entrega": order_data["direccion_entrega"],
            "pedido": order_data["pedido"],
            "hora_ultimo_mensaje": order_data["hora_ultimo_mensaje"],
            "metodo_pago": order_data.get("metodo_pago")
        }
        
        # Mover a pedidos finalizados y eliminar de activos
        supabase.table("pedidos_finalizados").insert(finalized_data).execute()
        supabase.table("pedidos_activos").delete().eq("id", order_id).execute()
        
        return {"success": "Pedido finalizado exitosamente"}
    except Exception as e:
        return {"error": f"Error al finalizar pedido: {str(e)}"}

#==========================================================#
#---------------------- CLIENT TOOLS ----------------------#
#==========================================================#


@tool
def get_client_by_id(cliente_id: str) -> dict:
    """
    Retorna la información de un cliente a partir de su ID de Telegram.
    
    Args:
        cliente_id: El ID del usuario de Telegram (como string)
        
    Returns:
        dict: Los datos del cliente si existe
        
    Example:
        get_client_by_id("7315133184")
    """
    try:
        result = supabase.table("clientes").select("*").eq("id", cliente_id).execute()
        if result.data:
            return result.data[0]
        else:
            return {"error": f"Cliente con ID {cliente_id} no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar cliente: {str(e)}"}


@tool  
def update_client(id: str, nombre:str = None, apellido: str = None, telefono: str = None, correo:str = None, direccion: str = None) -> dict:
    """
    Actualiza la información de un cliente existente en la base de datos.
    
    Args:
        id: ID del usuario de Telegram (string) - requerido para identificar el cliente
        nombre: Nombre del cliente (string, opcional)
        apellido: Apellido del cliente (string, opcional)
        telefono: Número de teléfono (string, opcional)
        correo: Correo electrónico del cliente (string, opcional)
        direccion: Dirección del cliente (string, opcional)
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        update_client("7315133184", nombre="Diego",  apellido="Molano", telefono="3203782744", correo="diegomolano@gmail.com", direccion="Calle 127A #11B-76 Apto 401")
    """
    try:
        update_data = {}
            
        if telefono:
            update_data["telefono"] = telefono  
        if correo:
            update_data["correo"] = correo
        if direccion:
            update_data["direccion"] = direccion
            
        if not update_data:
            return {"error": "No se proporcionaron datos para actualizar"}
        
        result = supabase.table("clientes").update(update_data).eq("id", id).execute()
        return {"success": "Cliente actualizado exitosamente", "data": result.data}
    except Exception as e:
        return {"error": f"Error al actualizar cliente: {str(e)}"}


#========================================================#
#---------------------- MENU TOOLS ----------------------#
#========================================================#

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
            return {"success": "Pizza encontrada", "data": result.data}
        else:
            return {"error": f"Pizza '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar pizza: {str(e)}"}
    

@tool
def get_pizza_by_name_and_size(name: str, size: str) -> dict:
    """
    Obtiene una pizza por su nombre desde la base de datos.
    
    Args:
        name: Nombre de la pizza a buscar (ej: "pepperoni", "hawaiana", "margherita")
        size: Tamaño de la pizza a buscar (ej: "Small", "Medium", "Large")
    Returns:
        dict: Datos de la pizza si existe
        
    Example:
        get_pizza_by_name_and_size("pepperoni", "Small")
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("pizzas_armadas").select("*").eq("nombre", name).eq("tamano", size).execute()
        
        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("pizzas_armadas").select("*").ilike("nombre", f"%{name}%").eq("tamano", size).execute()
        
        if result.data:
            return {"success": "Pizza encontrada", "data": result.data}
        else:
            return {"error": f"Pizza '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar pizza: {str(e)}"}


@tool
def get_combos(self) -> list[dict]:
    """
    Obtiene todos los combos disponibles en la base de datos.
    
    Returns:
        dict: Datos de los combos disponibles
        
    Example:
        get_combos()
    """
    try:
        result = supabase.table("combos").select("*").execute().data
        if result:
            return {"success": "Combos encontrados", "data": result.data}
        else:
            return {"error": "No se encontraron combos"}
    except Exception as e:
        return {"error": f"Error al buscar combos: {str(e)}"}

@tool
def get_combo_by_name(name: str) -> dict:
    """
    Obtiene información de un combo por su nombre desde la base de datos.
    
    Args:
        name: Nombre del combo a buscar (ej: "combo 1", "combo 2", "combo 3")
    Returns:
        dict: Datos del combo si existe
        
    Example:    
        get_combo_by_name("combo 1")
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("combos").select("*").eq("nombre", name).execute()

        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("combos").select("*").ilike("nombre", f"%{name}%").execute()
        
        if result.data:
            return {"success": "Combo encontrado", "data": result.data}
        else:
            return {"error": f"Combo '{name}' no encontrado"}
        
    except Exception as e:
        return {"error": f"Error al buscar combo: {str(e)}"}


@tool
def get_beverages(self) -> list[dict]:
    """
    Obtiene todas las bebidas disponibles en la base de datos.
    
    Returns:
        dict: Datos de las bebidas disponibles
        
    Example:
        get_beverages()
    """
    try:
        result = supabase.table("bebidas").select("*").execute().data
        if result:
            return {"success": "Bebidas encontradas", "data": result.data}
        else:
            return {"error": "No se encontraron bebidas"}
    except Exception as e:
        return {"error": f"Error al buscar bebidas: {str(e)}"}

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

@tool
def get_aditions(self) -> list[dict]:
    """
    Obtiene todas las adiciones disponibles en la base de datos.
    
    Returns:
        dict: Datos de las adiciones disponibles
        
    Example:
        get_aditions()
    """
    try:
        result = supabase.table("adiciones").select("*").execute().data
        if result:
            return {"success": "Adiciones encontradas", "data": result.data}
        else:
            return {"error": "No se encontraron adiciones"}
    except Exception as e:
        return {"error": f"Error al buscar adiciones: {str(e)}"}
    
@tool
def get_adition_by_name( name: str) -> dict:
    """
    Obtiene una adición por su nombre desde la base de datos.
    
    Args:
        name: Nombre de la adición a buscar (ej: "cebolla", "queso", "huevo")
        
    Returns:
        dict: Datos de la adición si existe
        
    Example:
        get_adition_by_name("cebolla")
    """
    try:
        result = supabase.table("adiciones").select("*").eq("nombre", name).execute().data[0]
        if not result:
            result = supabase.table("adiciones").select("*").ilike("nombre", f"%{name}%").execute().data[0]
        
        if result:
            return {"success": "Adición encontrada", "data": result}
        else:
            return {"error": f"Adición '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar adición: {str(e)}"}


@tool
def get_borders(self) -> list[dict]:
    """
    Obtiene todos los bordes disponibles en la base de datos.
    
    Returns:
        dict: Datos de los bordes disponibles
        
    Example:
        get_borders()
    """
    try:
        result = supabase.table("bordes").select("*").execute().data
        if result:
            return {"success": "Bordes encontrados", "data": result.data}
        else:
            return {"error": "No se encontraron bordes"}
    except Exception as e:
        return {"error": f"Error al buscar bordes: {str(e)}"}

@tool
def get_border_by_name( name: str) -> dict:
    """
    Obtiene un borde por su nombre desde la base de datos.
    
    Args:
        name: Nombre del borde a buscar (ej: "cebolla", "queso", "huevo")
        
    Returns:
        dict: Datos del borde si existe
        
    Example:
        get_border_by_name("cebolla")
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("bordes").select("*").eq("nombre", name).execute().data[0]
        if not result:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("bordes").select("*").ilike("nombre", f"%{name}%").execute().data[0]
        
        # Retornar el resultado si existe
        if result:
            return {"success": "Borde encontrado", "data": result}
        else:
            return {"error": f"Borde '{name}' no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar borde: {str(e)}"}


#=========================================================#
#-------------------- TELEGRAM TOOLS --------------------#
#=========================================================#

#@tool
def send_text_message(message: str, parse_mode: str = "HTML") -> dict:
    """
    Envía un mensaje de texto al usuario con formato opcional.
    
    Args:
        message: Texto del mensaje a enviar
        parse_mode: Modo de parseo del mensaje ("HTML" o "Markdown")
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_text_message("¡Hola! Tu <b>pizza</b> está lista", parse_mode="HTML")
    """
    try:
        return {
            "type": "text_message",
            "content": message,
            "parse_mode": parse_mode
        }
    except Exception as e:
        return {"error": f"Error al enviar mensaje: {str(e)}"}

@tool
def send_image_message(image_url: str, caption: str = None) -> dict:
    """
    Envía una imagen al usuario con un pie de foto opcional.
    
    Args:
        image_url: URL o path de la imagen a enviar
        caption: Texto opcional para el pie de foto
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_image_message("https://example.com/pizza.jpg", "¡Tu pizza está lista!")
    """
    try:
        return {
            "type": "image_message",
            "image_url": image_url,
            "caption": caption
        }
    except Exception as e:
        return {"error": f"Error al enviar imagen: {str(e)}"}

@tool
def send_inline_keyboard(message: str, buttons: list) -> dict:
    """
    Envía un mensaje con botones inline.
    
    Args:
        message: Texto del mensaje
        buttons: Lista de diccionarios con los botones. Formato:
                [{"text": "Texto botón", "callback_data": "data"}]
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_inline_keyboard(
            "Elige un tamaño:",
            [
                {"text": "Pequeña", "callback_data": "size_small"},
                {"text": "Mediana", "callback_data": "size_medium"},
                {"text": "Grande", "callback_data": "size_large"}
            ]
        )
    """
    try:
        return {
            "type": "inline_keyboard",
            "message": message,
            "buttons": buttons
        }
    except Exception as e:
        return {"error": f"Error al enviar teclado: {str(e)}"}

@tool
def send_menu_message(title: str, items: list[dict], show_prices: bool = True) -> dict:
    """
    Envía un mensaje formateado como menú.
    
    Args:
        title: Título del menú
        items: Lista de items del menú. Formato:
               [{"name": "Nombre", "description": "Desc", "price": 1000}]
        show_prices: Si se deben mostrar los precios
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_menu_message(
            "🍕 Nuestras Pizzas",
            [
                {
                    "name": "Pepperoni",
                    "description": "Pepperoni y queso",
                    "price": 25000
                }
            ]
        )
    """
    try:
        formatted_menu = f"<b>{title}</b>\n\n"
        for item in items:
            formatted_menu += f"• <b>{item['name']}</b>\n"
            if item.get('description'):
                formatted_menu += f"  {item['description']}\n"
            if show_prices and item.get('price'):
                formatted_menu += f"  💰 ${item['price']:,}\n"
            formatted_menu += "\n"
            
        return {
            "type": "text_message",
            "content": formatted_menu,
            "parse_mode": "HTML"
        }
    except Exception as e:
        return {"error": f"Error al enviar menú: {str(e)}"}

@tool
def send_order_summary(order_data: dict) -> dict:
    """
    Envía un resumen formateado del pedido.
    
    Args:
        order_data: Diccionario con los datos del pedido. Debe contener:
                   - items: Lista de productos
                   - total: Total del pedido
                   - cliente_id: ID del cliente
                   
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_order_summary({
            "items": [{"pizza": "Pepperoni", "tamaño": "M", "precio": 25000}],
            "total": 25000,
            "cliente_id": "123456789"
        })
    """
    try:
        summary = "<b>🛍️ Resumen de tu pedido</b>\n\n"
        
        # Agregar items
        for item in order_data.get("items", []):
            if "pizza" in item:
                summary += f"🍕 Pizza {item['pizza']} ({item.get('tamaño', 'N/A')})\n"
            elif "bebida" in item:
                summary += f"🥤 {item['bebida']}\n"
            summary += f"   💰 ${item.get('precio', 0):,}\n\n"
            
        # Agregar total
        summary += f"\n<b>Total: ${order_data.get('total', 0):,}</b>"
        
        # Agregar botones de confirmación
        buttons = [
            {"text": "✅ Confirmar Pedido", "callback_data": f"confirm_order_{order_data['cliente_id']}"},
            {"text": "❌ Cancelar", "callback_data": f"cancel_order_{order_data['cliente_id']}"}
        ]
        
        return {
            "type": "inline_keyboard",
            "message": summary,
            "buttons": buttons,
            "parse_mode": "HTML"
        }
    except Exception as e:
        return {"error": f"Error al enviar resumen: {str(e)}"}

@tool
def send_pdf_document(file_path: str = None, caption: str = None) -> dict:
    """
    Envía un documento PDF al usuario.
    
    Args:
        file_path: Ruta al archivo PDF. Si es None, se enviará el menú por defecto
        caption: Texto opcional para acompañar el documento
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        send_pdf_document(caption="Aquí tienes nuestro menú completo 📄")
    """
    try:
        # Si no se proporciona un archivo, usar el menú por defecto
        if file_path is None:
            file_path = "menu one pizzeria.pdf"
            
        return {
            "type": "document",
            "file_path": file_path,
            "caption": caption or "Aquí tienes nuestro menú 📄",
            "parse_mode": "HTML"
        }
    except Exception as e:
        return {"error": f"Error al enviar documento: {str(e)}"}

# Actualizar las listas de herramientas
CUSTOMER_TOOLS = [get_client_by_id, update_client]
ORDER_TOOLS = [get_order_by_id, get_active_order_by_client, create_order, update_order, delete_order, finish_order]  # Removed get_menu - only use search_menu and send_full_menu
MENU_TOOLS = [get_pizza_by_name, get_beverage_by_name, get_adition_by_name, get_border_by_name, get_combo_by_name, get_combos, get_borders, get_beverages]
TELEGRAM_TOOLS = [send_image_message, send_inline_keyboard, send_menu_message, send_order_summary, send_pdf_document]

# Complete tool list for the agent
ALL_TOOLS = CUSTOMER_TOOLS + MENU_TOOLS + ORDER_TOOLS + TELEGRAM_TOOLS
import os

from langchain_core.tools import tool
from pydantic.v1.errors import NoneIsAllowedError

from config.settings import supabase

#=========================================================#
#---------------------- ORDER TOOLS ----------------------#
#=========================================================#

@tool
def get_order_by_id(cliente_id: str) -> dict:
    """
    Obtiene un pedido activo por su ID.
    
    Args:
        cliente_id: ID numérico del pedido
        
    Returns:
        dict: Datos del pedido si existe
    """
    try:
        result = supabase.table("pedidos_activos").select("*").eq("cliente_id", cliente_id).execute()
        if result.data:
            return {"success": "Pedido encontrado", "data": result.data[0]}
        else:
            return {"fail": f"Pedido con ID {cliente_id} no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar pedido: {str(e)}"}
    
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
def update_order_info(id: int, direccion_entrega: str = None, metodo_pago: str = None, estado: str = None) -> dict:
    """
    Actualiza un pedido activo existente.
    
    Args:
        id: ID del pedido a actualizar (int) - requerido
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
def get_order_total(id: int, items: list = None) -> dict:
    """
    Obtiene el total de un pedido activo.
    
    Args:
        id: ID del pedido activo
        items: Lista de items (no se usa, mantenido por compatibilidad)
        
    Returns:
        dict: Resultado con el total del pedido
    """
    try:
        result = supabase.table("pedidos_activos").select("*").eq("id", id).execute()
        if not result.data:
            return {"error": f"Pedido con ID {id} no encontrado"}
            
        order_data = result.data[0]
        order_items = order_data.get("pedido", {}).get("items", [])
        
        total = 0
        for item in order_items:
            # Use total_price if available, otherwise use precio or base_price
            item_price = item.get("total_price", item.get("precio", item.get("base_price", 0)))
            total += float(item_price)
            
        return {"success": "Total del pedido obtenido exitosamente", "data": total}
    except Exception as e:
        return {"error": f"Error al obtener total del pedido: {str(e)}"}


@tool
def add_products_to_order(cliente_id: str, product_data: dict) -> dict:
    """
    Agrega un producto estructurado al pedido activo de un cliente.
    
    Args:
        cliente_id: ID del cliente (string)
        product_data: Lista de diccionarios con datos del producto (debe incluir: tipo_producto, nombre, tamaño (opcional))
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        add_product_to_order(
            "7315133184",
            [{"tipo_producto": "pizza", "nombre": "pepperoni", "tamaño": "large", "borde": "pesto", "adiciones": []},
             {"tipo_producto": "bebida", "nombre": "coca cola"}]
        )
    """
    try:
        from src.core.state import ProductDetails

        # Get or create active order
        active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
        
        if "fail" in active_order or "error" in active_order:
            # Create new order if none exists
            create_result = create_order.invoke({"cliente_id": cliente_id, "items": [], "total": 0.0})
            if "error" in create_result:
                return create_result
            active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
            if "error" in active_order:
                return {"error": "Failed to create or retrieve order"}
        
        order_id = active_order["data"]["id"]
        current_pedido = active_order.data[0]["data"].get("products", {})
        current_items = current_pedido.get("items", [])
        
        # Create structured product using ProductDetails
        base_price = float(product_data.get("precio", product_data.get("price", 0)))
        total_price = base_price
        
        # Calculate borde price
        borde_data = {}
        if borde and product_data.get("tipo", "").lower() == "pizza":
            borde_data = {
                "nombre": borde.get("nombre", ""),
                "precio_adicional": float(borde.get("precio_adicional", 0))
            }
            total_price += borde_data["precio_adicional"]
        
        # Calculate adiciones price
        adiciones_data = []
        if adiciones and product_data.get("tipo", "").lower() == "pizza":
            for adicion in adiciones:
                adicion_data = {
                    "nombre": adicion.get("nombre", ""),
                    "precio_adicional": float(adicion.get("precio_adicional", 0))
                }
                adiciones_data.append(adicion_data)
                total_price += adicion_data["precio_adicional"]
        
        # Create structured product dict following ProductDetails schema
        structured_product = {
            "product_id": str(product_data.get("id", "")),
            "product_name": product_data.get("nombre", product_data.get("nombre_producto", "")),
            "product_type": product_data.get("tipo", "pizza" if "categoria" in product_data else "bebida"),
            "base_price": base_price,
            "total_price": total_price,
            "borde": borde_data,
            "adiciones": adiciones_data,
            # Additional fields for compatibility
            "id": str(product_data.get("id", "")),
            "nombre": product_data.get("nombre", product_data.get("nombre_producto", "")),
            "tipo": product_data.get("tipo", "pizza" if "categoria" in product_data else "bebida"),
            "precio": total_price,
            "tamano": product_data.get("tamano", ""),
            "categoria": product_data.get("categoria", ""),
            "descripcion": product_data.get("descripcion", product_data.get("texto_ingredientes", "")),
            "activo": product_data.get("activo", True)
        }
        
        # Add to current items
        current_items.append(structured_product)
        
        # Calculate new total
        new_total = sum(item.get("total_price", item.get("precio", 0)) for item in current_items)
        
        # Update the order
        update_result = update_order.invoke({
            "id": order_id,
            "items": current_items,
            "total": new_total
        })
        
        if "success" in update_result:
            return {
                "success": f"Producto '{structured_product['product_name']}' agregado exitosamente al pedido",
                "data": {
                    "product": structured_product,
                    "order_total": new_total,
                    "order_id": order_id
                }
            }
        else:
            return update_result
            
    except Exception as e:
        return {"error": f"Error al agregar producto al pedido: {str(e)}"}


@tool
def remove_product_from_order(cliente_id: str, product_id: str) -> dict:
    """
    Remueve un producto del pedido activo de un cliente.
    
    Args:
        cliente_id: ID del cliente (string)
        product_id: ID del producto a remover (string)
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Get active order
        active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
        
        if "error" in active_order:
            return {"error": "No hay pedido activo para este cliente"}
        
        order_id = active_order["id"]
        current_pedido = active_order.get("pedido", {})
        current_items = current_pedido.get("items", [])
        
        # Find and remove the product
        updated_items = []
        removed_product = None
        
        for item in current_items:
            if str(item.get("product_id", item.get("id", ""))) == str(product_id):
                removed_product = item
            else:
                updated_items.append(item)
        
        if not removed_product:
            return {"error": f"Producto con ID {product_id} no encontrado en el pedido"}
        
        # Calculate new total
        new_total = sum(item.get("total_price", item.get("precio", 0)) for item in updated_items)
        
        # Update the order
        update_result = update_order.invoke({
            "id": order_id,
            "items": updated_items,
            "total": new_total
        })
        
        if "success" in update_result:
            return {
                "success": f"Producto '{removed_product.get('product_name', removed_product.get('nombre', 'Unknown'))}' removido exitosamente del pedido",
                "data": {
                    "removed_product": removed_product,
                    "order_total": new_total,
                    "remaining_items": len(updated_items)
                }
            }
        else:
            return update_result
            
    except Exception as e:
        return {"error": f"Error al remover producto del pedido: {str(e)}"}


@tool
def update_product_in_order(cliente_id: str, product_id: str, new_borde: dict = None, new_adiciones: list = None) -> dict:
    """
    Actualiza las personalizaciones de un producto en el pedido activo.
    
    Args:
        cliente_id: ID del cliente (string)
        product_id: ID del producto a actualizar (string)
        new_borde: Nuevo borde (opcional) - dict con nombre y precio_adicional
        new_adiciones: Nuevas adiciones (opcional) - list de dicts con nombre y precio_adicional
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        # Get active order
        active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
        
        if "error" in active_order:
            return {"error": "No hay pedido activo para este cliente"}
        
        order_id = active_order["id"]
        current_pedido = active_order.get("pedido", {})
        current_items = current_pedido.get("items", [])
        
        # Find and update the product
        updated_items = []
        updated_product = None
        
        for item in current_items:
            if str(item.get("product_id", item.get("id", ""))) == str(product_id):
                # This is the product to update
                updated_item = item.copy()
                
                # Recalculate price starting from base price
                base_price = float(updated_item.get("base_price", updated_item.get("precio", 0)))
                new_total_price = base_price
                
                # Update borde if provided and product is pizza
                if new_borde is not None and updated_item.get("product_type", updated_item.get("tipo", "")).lower() == "pizza":
                    updated_item["borde"] = {
                        "nombre": new_borde.get("nombre", ""),
                        "precio_adicional": float(new_borde.get("precio_adicional", 0))
                    }
                    new_total_price += updated_item["borde"]["precio_adicional"]
                else:
                    # Keep existing borde if not updating
                    existing_borde = updated_item.get("borde", {})
                    if existing_borde and existing_borde.get("precio_adicional"):
                        new_total_price += float(existing_borde["precio_adicional"])
                
                # Update adiciones if provided and product is pizza
                if new_adiciones is not None and updated_item.get("product_type", updated_item.get("tipo", "")).lower() == "pizza":
                    updated_item["adiciones"] = []
                    for adicion in new_adiciones:
                        adicion_data = {
                            "nombre": adicion.get("nombre", ""),
                            "precio_adicional": float(adicion.get("precio_adicional", 0))
                        }
                        updated_item["adiciones"].append(adicion_data)
                        new_total_price += adicion_data["precio_adicional"]
                else:
                    # Keep existing adiciones if not updating
                    existing_adiciones = updated_item.get("adiciones", [])
                    for adicion in existing_adiciones:
                        if adicion.get("precio_adicional"):
                            new_total_price += float(adicion["precio_adicional"])
                
                # Update prices
                updated_item["total_price"] = new_total_price
                updated_item["precio"] = new_total_price  # For compatibility
                
                updated_items.append(updated_item)
                updated_product = updated_item
            else:
                updated_items.append(item)
        
        if not updated_product:
            return {"error": f"Producto con ID {product_id} no encontrado en el pedido"}
        
        # Calculate new order total
        new_total = sum(item.get("total_price", item.get("precio", 0)) for item in updated_items)
        
        # Update the order
        update_result = update_order.invoke({
            "id": order_id,
            "items": updated_items,
            "total": new_total
        })
        
        if "success" in update_result:
            return {
                "success": f"Producto '{updated_product.get('product_name', updated_product.get('nombre', 'Unknown'))}' actualizado exitosamente",
                "data": {
                    "updated_product": updated_product,
                    "order_total": new_total
                }
            }
        else:
            return update_result
            
    except Exception as e:
        return {"error": f"Error al actualizar producto en el pedido: {str(e)}"}


@tool 
def calculate_order_total(cliente_id: str) -> dict:
    """
    Calcula el total correcto del pedido activo de un cliente.
    
    Args:
        cliente_id: ID del cliente (string)
        
    Returns:
        dict: Resultado con el total calculado y desglose de items
    """
    try:
        # Get active order
        active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
        
        if "error" in active_order:
            return {"error": "No hay pedido activo para este cliente"}
        
        current_pedido = active_order.get("pedido", {})
        current_items = current_pedido.get("items", [])
        
        total = 0
        items_breakdown = []
        
        for item in current_items:
            item_total = float(item.get("total_price", item.get("precio", item.get("base_price", 0))))
            total += item_total
            
            # Create breakdown for this item
            breakdown = {
                "product_name": item.get("product_name", item.get("nombre", "Unknown")),
                "base_price": float(item.get("base_price", item.get("precio", 0))),
                "total_price": item_total,
                "borde": item.get("borde", {}),
                "adiciones": item.get("adiciones", [])
            }
            items_breakdown.append(breakdown)
        
        return {
            "success": "Total del pedido calculado exitosamente",
            "data": {
                "total": total,
                "items_count": len(current_items),
                "items_breakdown": items_breakdown,
                "order_id": active_order["id"]
            }
        }
        
    except Exception as e:
        return {"error": f"Error al calcular total del pedido: {str(e)}"}


@tool
def get_order_details(cliente_id: str) -> dict:
    """
    Obtiene los detalles completos del pedido activo de un cliente.
    
    Args:
        cliente_id: ID del cliente (string)
        
    Returns:
        dict: Detalles completos del pedido con productos estructurados
    """
    try:
        # Get active order
        active_order = get_order_by_id.invoke({"cliente_id": cliente_id})
        
        if "error" in active_order:
            return {"error": "No hay pedido activo para este cliente"}
        
        current_pedido = active_order.get("pedido", {})
        current_items = current_pedido.get("items", [])
        
        # Calculate total
        total = sum(float(item.get("total_price", item.get("precio", 0))) for item in current_items)
        
        # Format products for display
        formatted_products = []
        for item in current_items:
            product_info = {
                "id": item.get("product_id", item.get("id", "")),
                "name": item.get("product_name", item.get("nombre", "")),
                "type": item.get("product_type", item.get("tipo", "")),
                "base_price": float(item.get("base_price", 0)),
                "total_price": float(item.get("total_price", item.get("precio", 0))),
                "customizations": {
                    "borde": item.get("borde", {}),
                    "adiciones": item.get("adiciones", [])
                },
                "details": {
                    "tamano": item.get("tamano", ""),
                    "categoria": item.get("categoria", ""),
                    "descripcion": item.get("descripcion", "")
                }
            }
            formatted_products.append(product_info)
        
        return {
            "success": "Detalles del pedido obtenidos exitosamente",
            "data": {
                "order_id": active_order["id"],
                "cliente_id": cliente_id,
                "estado": active_order.get("estado", ""),
                "direccion_entrega": active_order.get("direccion_entrega", ""),
                "metodo_pago": active_order.get("metodo_pago", ""),
                "total": total,
                "items_count": len(current_items),
                "products": formatted_products,
                "created_at": active_order.get("hora_ultimo_mensaje", "")
            }
        }
        
    except Exception as e:
        return {"error": f"Error al obtener detalles del pedido: {str(e)}"}
    
    
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


@tool
def get_border_price_by_name(name: str) -> dict:
    """
    Obtiene el precio de un borde por su nombre desde la base de datos.
    
    Args:
        name: Nombre del borde a buscar
        
    Returns:
        dict: Precio del borde si existe
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("bordes").select("*").eq("nombre", name).execute()
        
        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("bordes").select("*").ilike("nombre", f"%{name}%").execute()
        
        if result.data:
            borde_data = result.data[0]
            return {
                "success": "Borde encontrado",
                "data": {
                    "nombre": borde_data.get("nombre", ""),
                    "precio_adicional": float(borde_data.get("precio", 0))
                }
            }
        else:
            return {"error": f"Borde '{name}' no encontrado"}
    except Exception as e:
        return {"error": f"Error al buscar precio del borde: {str(e)}"}


@tool
def get_adition_price_by_name(name: str) -> dict:
    """
    Obtiene el precio de una adición por su nombre desde la base de datos.
    
    Args:
        name: Nombre de la adición a buscar
        
    Returns:
        dict: Precio de la adición si existe
    """
    try:
        # Buscar con nombre exacto primero
        result = supabase.table("adiciones").select("*").eq("nombre", name).execute()
        
        if not result.data:
            # Buscar con ilike para mayor flexibilidad
            result = supabase.table("adiciones").select("*").ilike("nombre", f"%{name}%").execute()
        
        if result.data:
            adicion_data = result.data[0]
            return {
                "success": "Adición encontrada",
                "data": {
                    "nombre": adicion_data.get("nombre", ""),
                    "precio_adicional": float(adicion_data.get("precio", 0))
                }
            }
        else:
            return {"error": f"Adición '{name}' no encontrada"}
    except Exception as e:
        return {"error": f"Error al buscar precio de la adición: {str(e)}"}


@tool
def add_product_to_order_smart(cliente_id: str, product_data: dict, borde_name: str = None, adiciones_names: list = None) -> dict:
    """
    Agrega un producto al pedido obteniendo automáticamente los precios de bordes y adiciones desde la BD.
    
    Args:
        cliente_id: ID del cliente (string)
        product_data: Datos del producto (debe incluir: id, nombre, tipo, precio)
        borde_name: Nombre del borde (opcional) - se buscarán los precios automáticamente
        adiciones_names: Lista de nombres de adiciones (opcional) - se buscarán los precios automáticamente
        
    Returns:
        dict: Resultado de la operación
        
    Example:
        add_product_to_order_smart(
            "7315133184",
            {"id": "1", "nombre": "Pepperoni", "tipo": "pizza", "precio": 25000},
            "pimentón",
            ["queso extra", "champiñones"]
        )
    """
    try:
        borde_data = None
        adiciones_data = []
        
        # Get borde price from database if specified
        if borde_name and product_data.get("tipo", "").lower() == "pizza":
            borde_result = get_border_price_by_name.invoke({"name": borde_name})
            if "success" in borde_result:
                borde_data = borde_result["data"]
            else:
                # Use default price if not found
                borde_data = {
                    "nombre": borde_name,
                    "precio_adicional": 2000  # Default fallback
                }
                print(f"⚠️ Borde '{borde_name}' not found in DB, using default price")
        
        # Get adiciones prices from database if specified
        if adiciones_names and product_data.get("tipo", "").lower() == "pizza":
            for adicion_name in adiciones_names:
                adicion_result = get_adition_price_by_name.invoke({"name": adicion_name})
                if "success" in adicion_result:
                    adiciones_data.append(adicion_result["data"])
                else:
                    # Use default price if not found
                    adiciones_data.append({
                        "nombre": adicion_name,
                        "precio_adicional": 5000  # Default fallback
                    })
                    print(f"⚠️ Adición '{adicion_name}' not found in DB, using default price")
        
        # Call the base add_product_to_order function with the fetched data
        return add_product_to_order.invoke({
            "cliente_id": cliente_id,
            "product_data": product_data,
            "borde": borde_data,
            "adiciones": adiciones_data
        })
        
    except Exception as e:
        return {"error": f"Error al agregar producto inteligente al pedido: {str(e)}"}


@tool
def update_product_in_order_smart(cliente_id: str, product_id: str, new_borde_name: str = None, new_adiciones_names: list = None) -> dict:
    """
    Actualiza un producto en el pedido obteniendo automáticamente los precios de bordes y adiciones desde la BD.
    
    Args:
        cliente_id: ID del cliente (string)
        product_id: ID del producto a actualizar (string)
        new_borde_name: Nuevo nombre del borde (opcional) - se buscarán los precios automáticamente
        new_adiciones_names: Nuevos nombres de adiciones (opcional) - se buscarán los precios automáticamente
        
    Returns:
        dict: Resultado de la operación
    """
    try:
        new_borde_data = None
        new_adiciones_data = []
        
        # Get borde price from database if specified
        if new_borde_name:
            borde_result = get_border_price_by_name.invoke({"name": new_borde_name})
            if "success" in borde_result:
                new_borde_data = borde_result["data"]
            else:
                # Use default price if not found
                new_borde_data = {
                    "nombre": new_borde_name,
                    "precio_adicional": 2000  # Default fallback
                }
                print(f"⚠️ Borde '{new_borde_name}' not found in DB, using default price")
        
        # Get adiciones prices from database if specified
        if new_adiciones_names:
            for adicion_name in new_adiciones_names:
                adicion_result = get_adition_price_by_name.invoke({"name": adicion_name})
                if "success" in adicion_result:
                    new_adiciones_data.append(adicion_result["data"])
                else:
                    # Use default price if not found
                    new_adiciones_data.append({
                        "nombre": adicion_name,
                        "precio_adicional": 5000  # Default fallback
                    })
                    print(f"⚠️ Adición '{adicion_name}' not found in DB, using default price")
        
        # Call the base update_product_in_order function with the fetched data
        return update_product_in_order.invoke({
            "cliente_id": cliente_id,
            "product_id": product_id,
            "new_borde": new_borde_data,
            "new_adiciones": new_adiciones_data
        })
        
    except Exception as e:
        return {"error": f"Error al actualizar producto inteligente en el pedido: {str(e)}"}


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
ORDER_TOOLS = [create_order, update_order, delete_order, get_order_total, finish_order]
PRODUCT_ORDER_TOOLS = [add_product_to_order, remove_product_from_order, update_product_in_order, calculate_order_total, get_order_details]
SMART_PRODUCT_TOOLS = [add_product_to_order_smart, update_product_in_order_smart, get_border_price_by_name, get_adition_price_by_name]
MENU_TOOLS = [get_pizza_by_name, get_beverage_by_name, get_adition_by_name, get_border_by_name, get_combo_by_name, get_combos, get_borders, get_beverages]
TELEGRAM_TOOLS = [send_image_message, send_inline_keyboard, send_menu_message, send_order_summary, send_pdf_document]

# Complete tool list for the agent
ALL_TOOLS = CUSTOMER_TOOLS + MENU_TOOLS + ORDER_TOOLS + PRODUCT_ORDER_TOOLS + SMART_PRODUCT_TOOLS + TELEGRAM_TOOLS
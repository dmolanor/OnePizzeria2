import os
# Importar el cliente de Supabase desde config centralizado
import sys
from typing import List, Optional

from langchain_core.tools import tool

sys.path.append('..')
from config import supabase

# HERRAMIENTAS PARA CLIENTES

@tool
def get_customer(user_id: str) -> dict:
    """Busca un cliente por su ID/teléfono en la base de datos."""
    try:
        result = supabase.table("clientes").select("*").eq("id", user_id).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception as e:
        print(f"Error getting customer: {e}")
        return {}

@tool
def create_customer(user_id: str, nombre_completo: str, telefono: str, correo: str = "", direccion: str = "") -> dict:
    """Crea un nuevo cliente en la base de datos."""
    try:
        # Separar nombre y apellido
        names = nombre_completo.strip().split()
        if len(names) >= 2:
            nombre = names[0]
            apellido = " ".join(names[1:])
        else:
            nombre = nombre_completo
            apellido = ""
        
        customer_data = {
            "id": user_id,
            "nombre_completo": nombre_completo,
            "nombre": nombre,
            "apellido": apellido,
            "telefono": telefono,
            "correo": correo,
            "direccion": direccion,
            "numero_pedidos": 0,
            "gasto_total": 0,
            "gasto_promedio": 0
        }
        
        result = supabase.table("clientes").insert(customer_data).execute()
        return {"success": True, "message": "Cliente creado exitosamente"}
    except Exception as e:
        print(f"Error creating customer: {e}")
        return {"success": False, "message": f"Error al crear cliente: {e}"}

@tool
def update_customer(user_id: str, nombre_completo: str = None, telefono: str = None, correo: str = None, direccion: str = None) -> dict:
    """Actualiza la información de un cliente existente."""
    try:
        update_data = {}
        if nombre_completo:
            update_data["nombre_completo"] = nombre_completo
            names = nombre_completo.strip().split()
            if len(names) >= 2:
                update_data["nombre"] = names[0]
                update_data["apellido"] = " ".join(names[1:])
            else:
                update_data["nombre"] = nombre_completo
                
        if telefono:
            update_data["telefono"] = telefono
        if correo:
            update_data["correo"] = correo
        if direccion:
            update_data["direccion"] = direccion
            
        if update_data:
            result = supabase.table("clientes").update(update_data).eq("id", user_id).execute()
            return {"success": True, "message": "Cliente actualizado exitosamente"}
        return {"success": False, "message": "No hay datos para actualizar"}
    except Exception as e:
        print(f"Error updating customer: {e}")
        return {"success": False, "message": f"Error al actualizar cliente: {e}"}

# HERRAMIENTAS PARA MENÚ

@tool
def search_menu(query: str) -> dict:
    """Busca productos en el menú por nombre, ingredientes o tipo. Ideal para consultas específicas."""
    try:
        results = {}
        query_lower = query.lower()
        
        # Buscar pizzas
        pizzas = supabase.table("pizzas_armadas").select("*").execute().data
        matching_pizzas = [pizza for pizza in pizzas if 
                          query_lower in pizza.get("nombre", "").lower() or 
                          query_lower in pizza.get("texto_ingredientes", "").lower() or
                          query_lower in pizza.get("categoria", "").lower()]
        
        # Buscar bebidas
        bebidas = supabase.table("bebidas").select("*").execute().data
        matching_bebidas = [bebida for bebida in bebidas if 
                           query_lower in bebida.get("nombre_producto", "").lower()]
        
        # Buscar combos
        combos = supabase.table("combos").select("*").execute().data
        matching_combos = [combo for combo in combos if 
                          query_lower in combo.get("nombre", "").lower() or
                          query_lower in combo.get("incluye", "").lower()]
        
        results = {
            "pizzas": matching_pizzas[:5],  # Limitar resultados
            "bebidas": matching_bebidas[:5],
            "combos": matching_combos[:5]
        }
        
        return results
    except Exception as e:
        print(f"Error searching menu: {e}")
        return {"error": f"Error buscando en el menú: {e}"}

@tool
def get_pizzas_by_ingredients(ingredientes: list) -> dict:
    """Busca pizzas que contengan todos los ingredientes especificados, considerando variaciones en nombres."""
    try:
        if not ingredientes:
            return {"pizzas": [], "message": "No se especificaron ingredientes"}
        
        # Normalizar los ingredientes de búsqueda
        ingredientes_lower = [ing.lower().strip() for ing in ingredientes]
        
        # Obtener todas las pizzas con sus ingredientes
        pizzas = supabase.table("pizzas_armadas").select("*").execute().data
        
        pizzas_encontradas = []
        
        for pizza in pizzas:
            texto_ingredientes = pizza.get("texto_ingredientes", "").lower()
            nombre_pizza = pizza.get("nombre", "").lower()
            
            # Verificar si todos los ingredientes están presentes
            todos_presentes = True
            ingredientes_encontrados = []
            
            for ingrediente in ingredientes_lower:
                # Buscar el ingrediente en el texto de ingredientes de la pizza
                if ingrediente in texto_ingredientes or ingrediente in nombre_pizza:
                    ingredientes_encontrados.append(ingrediente)
                else:
                    # Buscar variaciones del ingrediente en la tabla ingredientes
                    ingrediente_result = supabase.table("ingredientes").select("*").or_(
                        f"nombre_ingrediente.ilike.%{ingrediente}%,"
                        f"variacion_nombre_1.ilike.%{ingrediente}%,"
                        f"variacion_nombre_2.ilike.%{ingrediente}%,"
                        f"variacion_nombre_3.ilike.%{ingrediente}%"
                    ).execute()
                    
                    if ingrediente_result.data:
                        # Verificar si alguna de las variaciones está en la pizza
                        encontrado_variacion = False
                        for ing_data in ingrediente_result.data:
                            ing_id = ing_data.get("id")
                            # Verificar en la tabla ingredientes_pizzas
                            pizza_ing_result = supabase.table("ingredientes_pizzas").select("*").eq("pizza_id", pizza.get("id")).eq("ingrediente_id", ing_id).execute()
                            if pizza_ing_result.data:
                                ingredientes_encontrados.append(ingrediente)
                                encontrado_variacion = True
                                break
                        
                        if not encontrado_variacion:
                            todos_presentes = False
                            break
                    else:
                        todos_presentes = False
                        break
            
            if todos_presentes:
                pizzas_encontradas.append({
                    "id": pizza.get("id"),
                    "nombre": pizza.get("nombre"),
                    "categoria": pizza.get("categoria"),
                    "tamano": pizza.get("tamano"),
                    "precio": pizza.get("precio"),
                    "ingredientes": pizza.get("texto_ingredientes"),
                    "ingredientes_buscados": ingredientes_encontrados
                })
        
        return {
            "pizzas": pizzas_encontradas,
            "total_encontradas": len(pizzas_encontradas),
            "ingredientes_buscados": ingredientes
        }
        
    except Exception as e:
        print(f"Error searching pizzas by ingredients: {e}")
        return {"error": f"Error buscando pizzas por ingredientes: {e}"}

@tool 
def get_full_menu() -> dict:
    """Obtiene el menú completo organizado por categorías."""
    try:
        # Obtener pizzas por categoría
        pizzas = supabase.table("pizzas_armadas").select("*").order("categoria", desc=False).execute().data
        
        # Organizar pizzas por categoría
        pizzas_por_categoria = {}
        for pizza in pizzas:
            categoria = pizza.get("categoria", "Otras")
            if categoria not in pizzas_por_categoria:
                pizzas_por_categoria[categoria] = []
            pizzas_por_categoria[categoria].append({
                "nombre": pizza.get("nombre"),
                "precio": pizza.get("precio"),
                "ingredientes": pizza.get("texto_ingredientes"),
                "tamano": pizza.get("tamano")
            })
        
        # Obtener bebidas
        bebidas = supabase.table("bebidas").select("*").execute().data
        bebidas_simples = [{
            "nombre": b.get("nombre_producto"),
            "precio": b.get("precio"),
            "tamano": b.get("tamano")
        } for b in bebidas]
        
        # Obtener combos
        combos = supabase.table("combos").select("*").execute().data
        combos_simples = [{
            "nombre": c.get("nombre"),
            "precio": c.get("precio"),
            "incluye": c.get("incluye")
        } for c in combos]
        
        return {
            "pizzas": pizzas_por_categoria,
            "bebidas": bebidas_simples,
            "combos": combos_simples
        }
    except Exception as e:
        print(f"Error getting full menu: {e}")
        return {"error": f"Error obteniendo menú completo: {e}"}

# HERRAMIENTAS PARA ADICIONES Y BORDES

@tool
def get_pizza_additions() -> dict:
    """Obtiene las adiciones disponibles para pizzas con precios por tamaño."""
    try:
        adiciones = supabase.table("adiciones").select("*").execute().data
        bordes = supabase.table("bordes").select("*").execute().data
        
        return {
            "adiciones": adiciones,
            "bordes": bordes
        }
    except Exception as e:
        print(f"Error getting additions: {e}")
        return {"error": f"Error obteniendo adiciones: {e}"}

@tool
def calculate_pizza_price(pizza_name: str, size: str, additions: list = None, border: str = None) -> dict:
    """Calcula el precio total de una pizza con sus adiciones y borde."""
    try:
        # Obtener precio base de la pizza
        pizza_result = supabase.table("pizzas_armadas").select("*").eq("nombre", pizza_name).eq("tamano", size).execute()
        if not pizza_result.data:
            return {"error": f"Pizza {pizza_name} tamaño {size} no encontrada"}
        
        base_price = float(pizza_result.data[0]["precio"])
        total_price = base_price
        price_breakdown = [{"item": f"Pizza {pizza_name} {size}", "price": base_price}]
        
        # Agregar precio de adiciones
        if additions:
            for addition in additions:
                addition_result = supabase.table("adiciones").select("*").eq("nombre", addition).eq("tamano_pizza", size).execute()
                if addition_result.data:
                    addition_price = float(addition_result.data[0]["precio_adicional"])
                    total_price += addition_price
                    price_breakdown.append({"item": f"Adición {addition}", "price": addition_price})
        
        # Agregar precio de borde
        if border:
            border_result = supabase.table("bordes").select("*").eq("nombre", border).execute()
            if border_result.data:
                border_price = float(border_result.data[0]["precio_adicional"])
                total_price += border_price
                price_breakdown.append({"item": f"Borde {border}", "price": border_price})
        
        return {
            "total_price": total_price,
            "breakdown": price_breakdown
        }
    except Exception as e:
        print(f"Error calculating price: {e}")
        return {"error": f"Error calculando precio: {e}"}

# HERRAMIENTAS PARA PEDIDOS

@tool
def get_active_order(user_id: str) -> dict:
    """Obtiene el pedido activo de un cliente."""
    try:
        result = supabase.table("pedidos_activos").select("*").eq("cliente_id", user_id).execute()
        if result.data:
            return result.data[0]
        return {}
    except Exception as e:
        print(f"Error getting active order: {e}")
        return {}

@tool
def create_or_update_order(user_id: str, items: list, direccion: str = "", metodo_pago: str = "", subtotal: float = 0) -> dict:
    """Crea o actualiza un pedido activo para un cliente."""
    try:
        # Buscar si ya existe un pedido activo
        existing = supabase.table("pedidos_activos").select("*").eq("cliente_id", user_id).execute()
        
        order_data = {
            "cliente_id": user_id,
            "estado": "activo",
            "direccion_entrega": direccion,
            "pedido": {
                "items": items,
                "metodo_pago": metodo_pago,
                "subtotal": subtotal
            }
        }
        
        if existing.data:
            # Actualizar pedido existente
            result = supabase.table("pedidos_activos").update(order_data).eq("cliente_id", user_id).execute()
            return {"success": True, "message": "Pedido actualizado"}
        else:
            # Crear nuevo pedido
            result = supabase.table("pedidos_activos").insert(order_data).execute()
            return {"success": True, "message": "Pedido creado"}
            
    except Exception as e:
        print(f"Error creating/updating order: {e}")
        return {"success": False, "message": f"Error al crear pedido: {e}"}

@tool
def finalize_order(user_id: str) -> dict:
    """Finaliza un pedido activo y lo mueve a pedidos completados."""
    try:
        # Obtener pedido activo
        active_order = supabase.table("pedidos_activos").select("*").eq("cliente_id", user_id).execute()
        
        if not active_order.data:
            return {"success": False, "message": "No hay pedido activo para finalizar"}
        
        order = active_order.data[0]
        
        # Mover a pedidos finalizados
        finalized_order = {
            "cliente_id": order["cliente_id"],
            "estado": "preparacion",
            "direccion_entrega": order["direccion_entrega"],
            "pedido": order["pedido"],
            "hora_ultimo_mensaje": order["hora_ultimo_mensaje"]
        }
        
        # Insertar en finalizados y eliminar de activos
        supabase.table("pedidos_finalizados").insert(finalized_order).execute()
        supabase.table("pedidos_activos").delete().eq("cliente_id", user_id).execute()
        
        return {"success": True, "message": "Pedido finalizado y enviado a cocina"}
        
    except Exception as e:
        print(f"Error finalizing order: {e}")
        return {"success": False, "message": f"Error al finalizar pedido: {e}"}

# Lista de todas las herramientas críticas para el MVP
CRITICAL_TOOLS = [
    get_customer,
    create_customer,
    update_customer,
    search_menu,
    get_pizzas_by_ingredients,
    get_full_menu,
    get_pizza_additions,
    calculate_pizza_price,
    get_active_order,
    create_or_update_order,
    finalize_order
]

class SupabaseService:
    """Clase mantenida para compatibilidad, pero las herramientas reales son las funciones @tool"""
    def __init__(self):
        self.ALL_TOOLS = CRITICAL_TOOLS
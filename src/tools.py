import os
from ..config import supabase
from langchain_core.tools import tool

# PEDIDOS

@tool
def get_order_by_id( id: int) -> dict:
    return supabase.table("pedidos_activos").select("*").eq("id", id).execute().data[0]

#@tool
#def get_order_by_client_id( client_id: int) -> list[dict]:
#    return supabase.table("pedidos_activos").select("*").eq("cliente_id", client_id).execute().data
@tool
def create_order( order: dict) -> None:
    supabase.table("pedidos_activos").insert(order).execute()
@tool
def update_order( order: dict) -> None:
    supabase.table("pedidos_activos").update(order).eq("id", order["id"]).execute()
@tool
def delete_order( order: dict) -> None:
    supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
@tool    
def finish_order( order: dict) -> None:
    supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
    supabase.table("pedidos_finalizados").insert(order).execute()


# CLIENTES
@tool
def get_client_by_id( user_id: str) -> dict:
    return supabase.table("clientes").select("*").eq("id", user_id).execute().data[0]

#@tool
#def get_client_by_full_name( full_name: str) -> dict:
#    return supabase.table("clientes").select("*").eq("nombre_completo", full_name).execute().data[0]
@tool
def create_client( client: dict) -> None:
    supabase.table("clientes").insert(client).execute()
@tool
def update_client( client: dict) -> None:
    supabase.table("clientes").update(client).eq("id", client["id"]).execute()

#@tool
#def delete_client(client: dict) -> None:
#    supabase.table("clientes").delete().eq("id", client["id"]).execute()

# PIZZAS

#@tool
#def get_pizzas(self) -> list[dict]:
#    return supabase.table("pizzas_armadas").select("*").execute().data


#@tool
#def get_pizzas_by_all_ingredients( ingredients: list[str]) -> list[dict]:
#    ingredient_ids = supabase.table("ingredientes") \
#    # First get the ingredient IDs that match any of the input ingredient names
#        .select("id") \
#        .or_(f"name.ilike.%{ingredient}%" for ingredient in ingredients) \
#        .execute().data
#    
#    # Extract just the IDs
#    ids = [ing["id"] for ing in ingredient_ids]
#    
#    # Get pizzas that contain ALL the specified ingredients
#    # We use a subquery to count matches and ensure all ingredients are present
#    pizzas = supabase.table("pizzas_armadas") \
#        .select("*") \
#        .in_("id", 
#            supabase.table("ingredientes_pizzas") \
#            .select("pizza_id") \
#            .in_("ingrediente_id", ids) \
#            .group("pizza_id") \
#            .gte("count", len(ids)) \
#            .execute().data
#        ) \
#        .execute().data
#    
#    return pizzas
@tool
def get_pizza_by_name( name: str) -> dict:
    return supabase.table("pizzas_armadas").select("*").eq("nombre", name).execute().data[0]

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
def get_beverage_by_name( name: str) -> dict:
    return supabase.table("bebidas").select("*").eq("nombre_producto", name).execute().data[0]

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
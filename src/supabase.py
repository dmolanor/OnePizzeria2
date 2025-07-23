import os

from supabase import Client, create_client

# PEDIDOS

class SupabaseService:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        api_key: str = os.environ.get("SUPABASE_KEY")
        if not api_key:
            raise ValueError("SUPABASE_KEY environment variable is not set.")
        if not url:
            raise ValueError("SUPABASE_URL environment variable is not set.")
        self.supabase: Client = create_client(url, api_key)

    # PEDIDOS

    def get_order_by_id(self, id: int) -> dict:
        return self.supabase.table("pedidos_activos").select("*").eq("id", id).execute().data[0]

    #def get_order_by_client_id(self, client_id: int) -> list[dict]:
    #    return self.supabase.table("pedidos_activos").select("*").eq("cliente_id", client_id).execute().data

    def create_order(self, order: dict) -> None:
        self.supabase.table("pedidos_activos").insert(order).execute()

    def update_order(self, order: dict) -> None:
        self.supabase.table("pedidos_activos").update(order).eq("id", order["id"]).execute()

    def delete_order(self, order: dict) -> None:
        self.supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
        
    def finish_order(self, order: dict) -> None:
        self.supabase.table("pedidos_activos").delete().eq("id", order["id"]).execute()
        self.supabase.table("pedidos_finalizados").insert(order).execute()


    # CLIENTES

    def get_client_by_phone_number(self, phone_number: str) -> dict:
        return self.supabase.table("clientes").select("*").eq("id", phone_number).execute().data[0]

    #def get_client_by_full_name(self, full_name: str) -> dict:
    #    return self.supabase.table("clientes").select("*").eq("nombre_completo", full_name).execute().data[0]

    def create_client(self, client: dict) -> None:
        self.supabase.table("clientes").insert(client).execute()

    def update_client(self, client: dict) -> None:
        self.supabase.table("clientes").update(client).eq("id", client["id"]).execute()

    #def delete_client(client: dict) -> None:
    #    supabase.table("clientes").delete().eq("id", client["id"]).execute()

    # PIZZAS

    def get_pizzas(self) -> list[dict]:
        return self.supabase.table("pizzas_armadas").select("*").execute().data

    def get_pizzas_by_all_ingredients(self, ingredients: list[str]) -> list[dict]:
        # First get the ingredient IDs that match any of the input ingredient names
        ingredient_ids = self.supabase.table("ingredientes") \
            .select("id") \
            .or_(f"name.ilike.%{ingredient}%" for ingredient in ingredients) \
            .execute().data
        
        # Extract just the IDs
        ids = [ing["id"] for ing in ingredient_ids]
        
        # Get pizzas that contain ALL the specified ingredients
        # We use a subquery to count matches and ensure all ingredients are present
        pizzas = self.supabase.table("pizzas_armadas") \
            .select("*") \
            .in_("id", 
                self.supabase.table("ingredientes_pizzas") \
                .select("pizza_id") \
                .in_("ingrediente_id", ids) \
                .group("pizza_id") \
                .gte("count", len(ids)) \
                .execute().data
            ) \
            .execute().data
        
        return pizzas

    def get_pizza_by_name(self, name: str) -> dict:
        return self.supabase.table("pizzas_armadas").select("*").eq("nombre", name).execute().data[0]

    def get_pizzas_by_type(self, type: str) -> list[dict]:
        return self.supabase.table("pizzas_armadas").select("*").eq("tipo", type).execute().data

    # COMBOS

    def get_combos(self) -> list[dict]:
        return self.supabase.table("combos").select("*").execute().data

    def get_combo_by_name(self, name: str) -> dict:
        return self.supabase.table("combos").select("*").eq("nombre", name).execute().data[0]

    # BEBIDAS

    def get_beverages(self) -> list[dict]:
        return self.supabase.table("bebidas").select("*").execute().data

    def get_beverage_by_name(self, name: str) -> dict:
        return self.supabase.table("bebidas").select("*").eq("nombre_producto", name).execute().data[0]

    def get_beverages_by_sugar(self, sugar: bool) -> list[dict]:
        return self.supabase.table("bebidas").select("*").eq("azucar", sugar).execute().data

    def get_beverages_by_alcohol(self, alcohol: bool) -> list[dict]:
        return self.supabase.table("bebidas").select("*").eq("alcohol", alcohol).execute().data

    # ADICIONES

    def get_aditions(self) -> list[dict]:
        return self.supabase.table("adiciones").select("*").execute().data

    def get_adition_by_name(self, name: str) -> dict:
        return self.supabase.table("adiciones").select("*").eq("nombre", name).execute().data[0]

    # BORDES

    def get_borders(self) -> list[dict]:
        return self.supabase.table("bordes").select("*").execute().data

    def get_border_by_name(self, name: str) -> dict:
        return self.supabase.table("bordes").select("*").eq("nombre", name).execute().data[0]
    
    
    #CUSTOMER_TOOLS = [get_client_by_phone_number, get_client_by_full_name, create_client, update_client]
    CUSTOMER_TOOLS = [get_client_by_phone_number, create_client, update_client]
    #ORDER_TOOLS = [get_orders, get_order_by_id, get_order_by_client_id, create_order, update_order, delete_order, finish_order]  # Removed get_menu - only use search_menu and send_full_menu
    ORDER_TOOLS = [get_order_by_id, create_order, update_order, delete_order, finish_order]  # Removed get_menu - only use search_menu and send_full_menu
    MENU_TOOLS = [get_pizzas, get_pizzas_by_all_ingredients, get_pizza_by_name, get_pizzas_by_type, get_combos, get_combo_by_name, get_beverages, get_beverage_by_name, get_beverages_by_sugar, get_beverages_by_alcohol, get_aditions, get_adition_by_name, get_borders, get_border_by_name]

    # Complete tool list for the agent
    ALL_TOOLS = CUSTOMER_TOOLS + MENU_TOOLS + ORDER_TOOLS
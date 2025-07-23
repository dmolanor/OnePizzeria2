import logging
import os

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# AI Configuration - Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct") 
GOOGLE_MODEL = os.getenv("GOOGLE_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")

logging.info(f"GOOGLE_API_KEY loaded: {bool(GOOGLE_API_KEY)}")
logging.info(f"Using LLM_MODEL: {GOOGLE_MODEL}")

supabase: Client = create_client(
    supabase_url=SUPABASE_URL,
    supabase_key=SUPABASE_KEY
)


# =============================================================================
# Legacy configuration (to be removed)
# =============================================================================
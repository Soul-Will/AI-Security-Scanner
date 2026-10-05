import os 
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "llama-3.1-70b-versatile")
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY

def get_supabase_client() -> Client:
    # Instantiate the Supabase client using env configs
    # The schema mandates that the backend uses the service_role key to bypass RLS for inserts
    key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    if not SUPABASE_URL or not key:
        raise ValueError("Supabase configuration is missing.")
    return create_client(SUPABASE_URL, key)

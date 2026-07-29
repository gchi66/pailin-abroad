from supabase import Client, create_client
from app.config import Config


# This client is intentionally shared for ordinary database and storage calls.
# Never perform session-mutating auth operations on it.
supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
service_key = Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY
supabase_admin = create_client(Config.SUPABASE_URL, service_key)


def create_auth_client() -> Client:
    """Return an isolated client for one authentication operation/request."""
    return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)

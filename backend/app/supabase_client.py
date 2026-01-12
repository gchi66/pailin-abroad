from supabase import create_client
from app.config import Config


supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
service_key = Config.SUPABASE_SERVICE_ROLE_KEY or Config.SUPABASE_KEY
supabase_admin = create_client(Config.SUPABASE_URL, service_key)

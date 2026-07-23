import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Config:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    REVENUECAT_WEBHOOK_AUTH_SECRET = os.getenv("REVENUECAT_WEBHOOK_AUTH_SECRET")
    REVENUECAT_SECRET_API_KEY = os.getenv("REVENUECAT_SECRET_API_KEY")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    AUTH_CALLBACK_URL = os.getenv(
        "AUTH_CALLBACK_URL",
        "https://www.pailinabroad.com/auth/callback",
    )
    EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
    RECIPIENT_EMAIL = "pailinabroad@gmail.com"
    POSTMARK_SERVER_TOKEN = os.getenv("POSTMARK_SERVER_TOKEN")
    POSTMARK_FROM = os.getenv("POSTMARK_FROM")
    POSTMARK_TO = os.getenv("POSTMARK_TO") or POSTMARK_FROM

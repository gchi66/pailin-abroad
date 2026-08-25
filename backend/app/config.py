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
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    AZURE_API_KEY = os.getenv("AZURE_API_KEY")
    AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION")
    SPEAKING_COACH_MODEL = os.getenv(
        "SPEAKING_COACH_MODEL", "gemini-3.5-flash-lite"
    )
    SPEAKING_COACH_EVALUATION_TIMEOUT_SECONDS = int(
        os.getenv("SPEAKING_COACH_EVALUATION_TIMEOUT_SECONDS", "60")
    )
    SPEAKING_COACH_THINKING_LEVEL = os.getenv(
        "SPEAKING_COACH_THINKING_LEVEL", "minimal"
    )
    SPEAKING_COACH_CLEANUP_SECRET = os.getenv("SPEAKING_COACH_CLEANUP_SECRET")
    SPEAKING_COACH_AUDIO_RETENTION_HOURS = int(
        os.getenv("SPEAKING_COACH_AUDIO_RETENTION_HOURS", "24")
    )
    SPEAKING_COACH_DIAGNOSTIC_RETENTION_DAYS = int(
        os.getenv("SPEAKING_COACH_DIAGNOSTIC_RETENTION_DAYS", "90")
    )
    SPEAKING_COACH_CLEANUP_BATCH_SIZE = int(
        os.getenv("SPEAKING_COACH_CLEANUP_BATCH_SIZE", "100")
    )

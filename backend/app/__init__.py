from flask import Flask, request
from flask_cors import CORS
from app.routes import routes
from app.stripe_routes import stripe_routes
from app.stripe_webhook import stripe_webhook
from app.ai_evaluate import bp as ai_evaluate_bp
from app.config import Config

def create_app():
    app = Flask(__name__)
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://172.28.154.148:3000",
        "https://pailin-abroad.vercel.app",
        "https://pailinabroad.vercel.app",
        "https://www.pailinabroad.com",
        "https://pailinabroad.com"
    ]
    app.config["CORS_SUPPORTS_CREDENTIALS"] = True
    CORS(
        app,
        resources={
            r"/*": {
                "origins": allowed_origins,
                "allow_headers": ["Content-Type", "Authorization"],
                "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            }
        },
        supports_credentials=True,
    )
    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin in allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response
    # , resources={r"/api/*": {"origins": "*"}} # Define resources later in production
    app.config.from_object(Config)
    app.register_blueprint(routes)  # Register Blueprint
    app.register_blueprint(stripe_routes)  # Register Stripe payment routes
    app.register_blueprint(stripe_webhook)  # Register Stripe webhook
    app.register_blueprint(ai_evaluate_bp)  # Register AI evaluation routes
    return app

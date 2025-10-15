from flask import Flask
from flask_cors import CORS
from app.routes import routes
from app.stripe_routes import stripe_routes
from app.stripe_webhook import stripe_webhook
from app.ai_evaluate import bp as ai_evaluate_bp
from app.config import Config

def create_app():
    app = Flask(__name__)
    cors = CORS(app, resources={r"/*": {"origins": [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://172.28.154.148:3000"
    ]}})
    # , resources={r"/api/*": {"origins": "*"}} # Define resources later in production
    app.config.from_object(Config)
    app.register_blueprint(routes)  # Register Blueprint
    app.register_blueprint(stripe_routes)  # Register Stripe payment routes
    app.register_blueprint(stripe_webhook)  # Register Stripe webhook
    app.register_blueprint(ai_evaluate_bp)  # Register AI evaluation routes
    return app

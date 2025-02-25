from flask import Flask
from flask_cors import CORS
from app.routes import routes
from app.config import Config

def create_app():
    app = Flask(__name__)
    cors = CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
    # , resources={r"/api/*": {"origins": "*"}} # Define resources later in production
    app.config.from_object(Config)
    app.register_blueprint(routes)  # Register Blueprint
    return app

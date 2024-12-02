from flask import Flask
from flask_cors import CORS
from app.routes import routes

def create_app():
    app = Flask(__name__)
    cors = CORS(app)
    # , resources={r"/api/*": {"origins": "*"}} # Define resources later in production
    app.register_blueprint(routes)  # Register Blueprint
    return app

from flask import Blueprint, request, jsonify
from app.supabase_client import supabase

routes = Blueprint("routes", __name__)

@routes.route("/", methods=["GET"])
def home():
    return {"message": "Welcome to Pailin Abroad!"}, 200

@routes.route('/api/signup', methods=['POST'])

def signup():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    response = supabase.auth.sign_up({
        "email": email,
        "password": password
    })

    if response.get("error"):
        return jsonify({"error": response["error"]["message"]}), 400

    return jsonify({"message": "Sign-up successful! Please verify your email."}), 200

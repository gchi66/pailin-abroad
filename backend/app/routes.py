from flask import Blueprint, request, jsonify
from app.supabase_client import supabase

routes = Blueprint("routes", __name__)

@routes.route("/", methods=["GET"])
def home():
    return {"message": "Welcome to Pailin Abroad!"}, 200

@routes.route('/api/signup', methods=['GET', 'POST'])
def signup():
    print("Endpoint hit!")
    data = request.json
    print("Received data:", data)  # Debug incoming data

    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        print("Missing email or password")  # Debug missing fields
        return jsonify({"error": "Email and password are required"}), 400

    response = supabase.auth.sign_up({
        "email": email,
        "password": password
    })
    print("Supabase response:", response)  # Debug Supabase response

    # Check for errors in the response
    if hasattr(response, "error") and response.error:
        print("Error from Supabase:", response.error)  # Debug Supabase error
        return jsonify({"error": str(response.error)}), 400

    if not response.user:
        print("Sign-up failed: No user object returned")
        return jsonify({"error": "Sign-up failed. Please try again."}), 400

    return jsonify({"message": "Sign-up successful! Please verify your email."}), 200

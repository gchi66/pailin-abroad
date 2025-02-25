from flask import Blueprint, request, jsonify
from app.supabase_client import supabase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from app.config import Config

routes = Blueprint("routes", __name__)

@routes.route("/", methods=["GET"])
def home():
    return jsonify({}), 204

@routes.route('/api/login', methods=['GET', 'POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if hasattr(response, "error") and response.error:
            return jsonify({"error": str(response.error)}), 400

        session_data = {
            "access_token": response.session.access_token,
            "refresh_token": response.session.refresh_token,
            "user": {
                "id": response.user.id,
                "email": response.user.email,
            }
        }

        return jsonify({"message": "Login successful!", "session": session_data}), 200

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500


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

@routes.route('/api/delete_account', methods=['DELETE'])
def delete_account():
    try:
        data = request.json
        access_token = data.get('access_token')

        if not access_token:
            return jsonify({"error": "Access token is required"}), 400

        # Fetch the user's details using the access token
        user_response = supabase.auth.get_user(access_token)

        if user_response.user is None:
            return jsonify({"error": "Unable to retrieve user details. User may not exist."}), 401

        user_id = user_response.user.id

        # Delete the user using the service role client
        supabase.auth.admin.delete_user(user_id)

        # # Check if the delete action was successful
        # if delete_response is None or delete_response.error:
        #     return jsonify({"error": "Failed to delete the user."}), 400

        print("User deleted successfully:", user_id)
        # Return a success message immediately
        return jsonify({"message": "Account deleted successfully."}), 200


    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@routes.route("/contact", methods=["POST"])
def contact():
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    message = data.get("message")

    if not (name and email and message):
        return jsonify({"message": "Missing required fields"}), 400

    # Build the message
    msg = MIMEMultipart()
    msg["From"] = Config.EMAIL_ADDRESS
    msg["To"] = Config.RECIPIENT_EMAIL
    msg["Subject"] = "New Contact Form Submission"

    body = f"""
    You have a new message from your contact form:

    Name: {name}
    Email: {email}

    Message:
    {message}
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(Config.EMAIL_ADDRESS, Config.EMAIL_PASSWORD)
            server.send_message(msg)
        return jsonify({"message": "Email sent successfully!"}), 200
    except Exception as e:
        print("Error sending email:", e)
        return jsonify({"message": "Failed to send email."}), 500

# server.py
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

load_dotenv()  # Load variables from .env

app = Flask(__name__)

# Grab your email credentials from environment variables
EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
# The recipient could be your own email or a distribution list
RECIPIENT_EMAIL = "pailinabroad@gmail.com"

@app.route("/contact", methods=["POST"])
def contact():
    # Get the JSON data from the request
    data = request.get_json()
    name = data.get("name")
    email = data.get("email")
    message = data.get("message")

    if not (name and email and message):
        return jsonify({"message": "Missing required fields"}), 400

    # Create the email
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = RECIPIENT_EMAIL
    msg["Subject"] = "New Contact Form Submission"

    # Format the body of the email
    body = f"""
    You have a new message from your contact form:

    Name: {name}
    Email: {email}

    Message:
    {message}
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        # Connect to Gmail's SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        return jsonify({"message": "Email sent successfully!"}), 200
    except Exception as e:
        print("Error sending email:", e)
        return jsonify({"message": "Failed to send email."}), 500

if __name__ == "__main__":
    # Run Flask in debug mode for development
    app.run(debug=True, port=5000)

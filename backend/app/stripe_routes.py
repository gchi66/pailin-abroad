import os
import stripe
from flask import Blueprint, request, jsonify

# Initialize Stripe with API key from environment variable
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Create Blueprint for Stripe payment routes
stripe_routes = Blueprint('stripe_routes', __name__)


@stripe_routes.route('/api/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """
    Create a Stripe PaymentIntent for processing payments.

    Expects JSON body with:
    - amount: The payment amount in baht (will be converted to satang)
    - currency: Optional currency code (defaults to 'thb')

    Returns:
    - clientSecret: The PaymentIntent client secret for frontend confirmation
    """
    try:
        # Parse request data
        data = request.get_json()

        # Extract amount and currency from request
        # Amount is expected in baht, convert to satang (multiply by 100)
        amount = data.get('amount')
        currency = data.get('currency', 'thb')  # Default to Thai Baht

        # Validate amount is provided
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400

        # Convert amount to satang (smallest currency unit for THB)
        amount_in_satang = int(amount * 100)

        # Create PaymentIntent with Stripe
        payment_intent = stripe.PaymentIntent.create(
            amount=amount_in_satang,
            currency=currency,
            # Enable automatic payment methods
            automatic_payment_methods={
                'enabled': True,
            },
        )

        # Return the client secret to the frontend
        return jsonify({
            'clientSecret': payment_intent['client_secret']
        }), 200

    except Exception as e:
        # Return error message if something goes wrong
        return jsonify({'error': str(e)}), 400

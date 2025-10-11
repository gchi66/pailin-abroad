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
    - email: Customer email address (optional, for webhook processing)

    Returns:
    - clientSecret: The PaymentIntent client secret for frontend confirmation
    """
    try:
        # Parse request data
        data = request.get_json()

        # Extract amount, currency, and email from request
        # Amount is expected in baht, convert to satang (multiply by 100)
        amount = data.get('amount')
        currency = data.get('currency', 'thb')  # Default to Thai Baht
        email = data.get('email')  # Customer email for webhook

        # Validate amount is provided
        if not amount:
            return jsonify({'error': 'Amount is required'}), 400

        # Convert amount to satang (smallest currency unit for THB)
        amount_in_satang = int(amount * 100)

        # Prepare PaymentIntent parameters
        payment_intent_params = {
            'amount': amount_in_satang,
            'currency': currency,
            # Enable automatic payment methods
            'automatic_payment_methods': {
                'enabled': True,
            },
        }

        # Add email as metadata if provided (for webhook processing)
        if email:
            payment_intent_params['receipt_email'] = email
            payment_intent_params['metadata'] = {
                'customer_email': email
            }

        # Create PaymentIntent with Stripe
        payment_intent = stripe.PaymentIntent.create(**payment_intent_params)

        # Return the client secret to the frontend
        return jsonify({
            'clientSecret': payment_intent['client_secret']
        }), 200

    except Exception as e:
        # Return error message if something goes wrong
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/update-payment-intent', methods=['POST'])
def update_payment_intent():
    """
    Update a PaymentIntent with customer email metadata.

    Expects JSON body with:
    - payment_intent_id: The PaymentIntent ID to update
    - email: Customer email address

    Returns:
    - success: Boolean indicating if update was successful
    """
    try:
        data = request.get_json()
        payment_intent_id = data.get('payment_intent_id')
        email = data.get('email')

        if not payment_intent_id or not email:
            return jsonify({'error': 'payment_intent_id and email are required'}), 400

        # Update PaymentIntent with email metadata
        stripe.PaymentIntent.modify(
            payment_intent_id,
            receipt_email=email,
            metadata={'customer_email': email}
        )

        return jsonify({'success': True}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400

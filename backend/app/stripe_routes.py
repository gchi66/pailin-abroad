import os
import stripe
from flask import Blueprint, request, jsonify, send_file
from app.supabase_client import supabase
import io

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

stripe_routes = Blueprint('stripe_routes', __name__)


@stripe_routes.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """
    Create a Stripe Checkout Session for subscription payments.
    """
    try:
        data = request.get_json()
        price_id = data.get('price_id')  # Pass the Stripe Price ID from frontend
        customer_email = data.get('email')
        success_url = data.get('success_url', 'http://localhost:3000/payment-success')
        cancel_url = data.get('cancel_url', 'http://localhost:3000/checkout')

        if not price_id:
            return jsonify({'error': 'price_id is required'}), 400

        # Create Checkout Session
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='subscription',  # This makes it recurring!
            customer_email=customer_email,
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'customer_email': customer_email
            }
        )

        return jsonify({'sessionId': session.id, 'url': session.url}), 200

    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/create-portal-session', methods=['POST'])
def create_portal_session():
    """
    Create a Stripe Customer Portal session for subscription management.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)
        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get user's Stripe customer ID from database
        result = supabase.table('users').select('stripe_customer_id').eq('id', user_id).single().execute()

        if not result.data or not result.data.get('stripe_customer_id'):
            return jsonify({"error": "No Stripe customer found"}), 404

        stripe_customer_id = result.data['stripe_customer_id']

        # Get return URL from request
        data = request.get_json() or {}
        return_url = data.get('return_url', 'http://localhost:3000/account-settings')

        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )

        return jsonify({'url': portal_session.url}), 200

    except Exception as e:
        print(f"Error creating portal session: {e}")
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/get-payment-method', methods=['GET'])
def get_payment_method():
    """
    Get the customer's default payment method details.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)
        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get user's Stripe customer ID
        result = supabase.table('users').select('stripe_customer_id').eq('id', user_id).single().execute()

        if not result.data or not result.data.get('stripe_customer_id'):
            return jsonify({"error": "No Stripe customer found"}), 404

        stripe_customer_id = result.data['stripe_customer_id']

        # Retrieve customer from Stripe
        customer = stripe.Customer.retrieve(stripe_customer_id)

        if not customer.invoice_settings.default_payment_method:
            return jsonify({"payment_method": None}), 200

        # Get payment method details
        payment_method = stripe.PaymentMethod.retrieve(
            customer.invoice_settings.default_payment_method
        )

        # Return card details
        return jsonify({
            "payment_method": {
                "id": payment_method.id,
                "brand": payment_method.card.brand,
                "last4": payment_method.card.last4,
                "exp_month": payment_method.card.exp_month,
                "exp_year": payment_method.card.exp_year
            }
        }), 200

    except Exception as e:
        print(f"Error getting payment method: {e}")
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/get-invoices', methods=['GET'])
def get_invoices():
    """
    Get the customer's recent invoices.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)
        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get user's Stripe customer ID
        result = supabase.table('users').select('stripe_customer_id').eq('id', user_id).single().execute()

        if not result.data or not result.data.get('stripe_customer_id'):
            return jsonify({"error": "No Stripe customer found"}), 404

        stripe_customer_id = result.data['stripe_customer_id']

        # Retrieve invoices from Stripe
        invoices = stripe.Invoice.list(
            customer=stripe_customer_id,
            limit=10
        )

        # Format invoice data
        invoice_list = []
        for invoice in invoices.data:
            invoice_list.append({
                "id": invoice.id,
                "number": invoice.number,
                "amount": invoice.amount_paid,
                "currency": invoice.currency,
                "created": invoice.created,
                "status": invoice.status,
                "description": invoice.description or f"Subscription payment",
                "pdf_url": invoice.invoice_pdf
            })

        return jsonify({"invoices": invoice_list}), 200

    except Exception as e:
        print(f"Error getting invoices: {e}")
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/download-invoice/<invoice_id>', methods=['GET'])
def download_invoice(invoice_id):
    """
    Download a specific invoice PDF.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)
        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get user's Stripe customer ID
        result = supabase.table('users').select('stripe_customer_id').eq('id', user_id).single().execute()

        if not result.data or not result.data.get('stripe_customer_id'):
            return jsonify({"error": "No Stripe customer found"}), 404

        stripe_customer_id = result.data['stripe_customer_id']

        # Retrieve invoice
        invoice = stripe.Invoice.retrieve(invoice_id)

        # Verify this invoice belongs to this customer
        if invoice.customer != stripe_customer_id:
            return jsonify({"error": "Unauthorized"}), 403

        # Get PDF URL and redirect
        if invoice.invoice_pdf:
            # For simplicity, redirect to PDF URL
            # In production, you might want to proxy the PDF
            return jsonify({"pdf_url": invoice.invoice_pdf}), 200
        else:
            return jsonify({"error": "PDF not available"}), 404

    except Exception as e:
        print(f"Error downloading invoice: {e}")
        return jsonify({'error': str(e)}), 400


@stripe_routes.route('/api/cancel-subscription', methods=['POST'])
def cancel_subscription():
    """
    Cancel the customer's active subscription.
    """
    try:
        # Get authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authorization token required"}), 401

        access_token = auth_header.split(' ')[1]

        # Get the authenticated user
        user_response = supabase.auth.get_user(access_token)
        if not user_response.user:
            return jsonify({"error": "Invalid token"}), 401

        user_id = user_response.user.id

        # Get user's Stripe subscription ID
        result = supabase.table('users').select('stripe_subscription_id, stripe_customer_id').eq('id', user_id).single().execute()

        if not result.data or not result.data.get('stripe_subscription_id'):
            return jsonify({"error": "No active subscription found"}), 404

        stripe_subscription_id = result.data['stripe_subscription_id']

        # Cancel subscription at period end (not immediately)
        subscription = stripe.Subscription.modify(
            stripe_subscription_id,
            cancel_at_period_end=True
        )

        # Update database
        supabase.table('users').update({
            'subscription_status': 'canceled'
        }).eq('id', user_id).execute()

        print(f"Subscription {stripe_subscription_id} scheduled for cancellation for user {user_id}")

        return jsonify({
            "message": "Subscription cancelled. You'll retain access until the end of your billing period.",
            "cancel_at": subscription.cancel_at,
            "current_period_end": subscription.current_period_end
        }), 200

    except Exception as e:
        print(f"Error cancelling subscription: {e}")
        return jsonify({'error': str(e)}), 400

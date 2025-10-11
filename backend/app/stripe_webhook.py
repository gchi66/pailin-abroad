import os
import stripe
from flask import Blueprint, request, jsonify
from app.supabase_client import supabase

stripe_webhook = Blueprint('stripe_webhook', __name__)

# Get Stripe webhook secret from environment
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Debug: Print webhook secret status on startup
if STRIPE_WEBHOOK_SECRET:
    print(f"✅ Stripe webhook secret loaded: {STRIPE_WEBHOOK_SECRET[:10]}...{STRIPE_WEBHOOK_SECRET[-10:]}")
else:
    print("❌ WARNING: STRIPE_WEBHOOK_SECRET not found in environment!")

@stripe_webhook.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook_handler():
    """
    Handle Stripe webhook events
    Verifies webhook signature and processes checkout.session.completed events
    """
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    print(f"🔔 Webhook received! Signature: {sig_header[:50]}..." if sig_header else "🔔 Webhook received! No signature")

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        print(f"✅ Webhook signature verified! Event type: {event['type']}")
    except ValueError as e:
        # Invalid payload
        print(f"❌ Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.SignatureVerificationError as e:
        # Invalid signature
        print(f"❌ Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        # Get customer email from the session
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')

        if not customer_email:
            print("No customer email found in session")
            return jsonify({'error': 'No customer email'}), 400

        try:
            # Update user's is_paid status
            result = supabase.table('users').update({
                'is_paid': True,
                'stripe_customer_id': session.get('customer'),
                'stripe_subscription_id': session.get('subscription'),
                'subscription_status': 'active'
            }).eq('email', customer_email).execute()

            if result.data:
                print(f"Successfully updated is_paid for user: {customer_email}")
            else:
                print(f"No user found with email: {customer_email}")

        except Exception as e:
            print(f"Error updating user: {e}")
            return jsonify({'error': str(e)}), 500

    # Handle PaymentIntent succeeded (for direct payment intents, not checkout sessions)
    elif event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']

        print("=" * 60)
        print(f"💰 PaymentIntent succeeded! ID: {payment_intent.get('id')}")
        print(f"📋 Full PaymentIntent object: {payment_intent}")
        print("=" * 60)

        # Get customer email from receipt_email or metadata
        customer_email = payment_intent.get('receipt_email') or payment_intent.get('metadata', {}).get('customer_email')

        print(f"📧 Customer email found: {customer_email}")

        if not customer_email:
            print("⚠️ No customer email found in payment intent")
            print(f"🔍 receipt_email: {payment_intent.get('receipt_email')}")
            print(f"🔍 metadata: {payment_intent.get('metadata')}")
            return jsonify({'error': 'No customer email'}), 400

        try:
            # Update user's is_paid status
            result = supabase.table('users').update({
                'is_paid': True,
                'stripe_customer_id': payment_intent.get('customer')
            }).eq('email', customer_email).execute()

            if result.data:
                print(f"✅ Successfully updated is_paid for user: {customer_email}")
                print(f"📊 Updated data: {result.data}")
            else:
                print(f"⚠️ No user found with email: {customer_email}")

        except Exception as e:
            print(f"❌ Error updating user from PaymentIntent: {e}")
            return jsonify({'error': str(e)}), 500

    # Handle subscription updates (optional - for recurring subscriptions)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        status = subscription.get('status')

        try:
            # Update subscription status
            supabase.table('users').update({
                'subscription_status': status,
                'current_period_end': subscription.get('current_period_end')
            }).eq('stripe_customer_id', customer_id).execute()

            print(f"Updated subscription status for customer: {customer_id}")

        except Exception as e:
            print(f"Error updating subscription: {e}")

    # Handle subscription cancellation
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')

        try:
            # Update user status when subscription is cancelled
            supabase.table('users').update({
                'is_paid': False,
                'subscription_status': 'cancelled'
            }).eq('stripe_customer_id', customer_id).execute()

            print(f"Cancelled subscription for customer: {customer_id}")

        except Exception as e:
            print(f"Error cancelling subscription: {e}")

    return jsonify({'status': 'success'}), 200

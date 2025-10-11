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
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    print(f"🔔 Webhook received!")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        print(f"✅ Webhook signature verified! Event type: {event['type']}")
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 400

    # Handle subscription creation (first payment)
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']

        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email')
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')

        print(f"💳 Checkout completed for: {customer_email}")

        if not customer_email:
            print("⚠️ No customer email found")
            return jsonify({'error': 'No customer email'}), 400

        try:
            # Get subscription details
            subscription = stripe.Subscription.retrieve(subscription_id)

            result = supabase.table('users').update({
                'is_paid': True,
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription_id,
                'subscription_status': subscription.status,
                'current_period_end': subscription.current_period_end
            }).eq('email', customer_email).execute()

            if result.data:
                print(f"✅ Successfully updated subscription for: {customer_email}")
            else:
                print(f"⚠️ No user found with email: {customer_email}")

        except Exception as e:
            print(f"❌ Error updating user: {e}")
            return jsonify({'error': str(e)}), 500

    # Handle successful subscription renewals
    elif event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        subscription_id = invoice.get('subscription')

        print(f"💰 Invoice paid for customer: {customer_id}")

        if subscription_id:
            try:
                subscription = stripe.Subscription.retrieve(subscription_id)

                supabase.table('users').update({
                    'is_paid': True,
                    'subscription_status': subscription.status,
                    'current_period_end': subscription.current_period_end
                }).eq('stripe_customer_id', customer_id).execute()

                print(f"✅ Renewed subscription for customer: {customer_id}")

            except Exception as e:
                print(f"❌ Error updating renewal: {e}")

    # Handle subscription updates (e.g., status changes)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        status = subscription.get('status')

        print(f"🔄 Subscription updated for customer: {customer_id}, status: {status}")

        try:
            supabase.table('users').update({
                'subscription_status': status,
                'current_period_end': subscription.get('current_period_end'),
                'is_paid': status in ['active', 'trialing']  # Only paid if active or trialing
            }).eq('stripe_customer_id', customer_id).execute()

        except Exception as e:
            print(f"❌ Error updating subscription: {e}")

    # Handle subscription cancellation
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')

        print(f"❌ Subscription cancelled for customer: {customer_id}")

        try:
            supabase.table('users').update({
                'is_paid': False,
                'subscription_status': 'cancelled'
            }).eq('stripe_customer_id', customer_id).execute()

        except Exception as e:
            print(f"❌ Error cancelling subscription: {e}")

    return jsonify({'status': 'success'}), 200

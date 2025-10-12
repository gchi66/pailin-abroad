import os
import stripe
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from app.supabase_client import supabase

stripe_webhook = Blueprint('stripe_webhook', __name__)


def get_current_period_end(subscription):
    """
    Universal-safe extractor for current_period_end.
    In Flexible Billing mode, current_period_end is nested in items.data[0].
    """
    try:
        # Try direct attribute first (standard subscriptions)
        if hasattr(subscription, 'current_period_end') and subscription.current_period_end:
            return subscription.current_period_end

        # Fall back to items.data[0] for Flexible Billing
        if hasattr(subscription, 'items'):
            items = subscription.items
            if hasattr(items, 'data') and items.data and len(items.data) > 0:
                first_item = items.data[0]
                if hasattr(first_item, 'current_period_end'):
                    print(f"📅 Found current_period_end in items.data[0]: {first_item.current_period_end}")
                    return first_item.current_period_end

        # If subscription is a dict (from webhook event object)
        if isinstance(subscription, dict):
            if 'current_period_end' in subscription:
                return subscription['current_period_end']

            items = subscription.get('items', {})
            data = items.get('data', [])
            if data and len(data) > 0:
                first_item = data[0]
                if 'current_period_end' in first_item:
                    print(f"📅 Found current_period_end in items.data[0]: {first_item['current_period_end']}")
                    return first_item['current_period_end']

        print(f"⚠️ Could not find current_period_end anywhere in subscription")
        return None

    except Exception as e:
        print(f"❌ Error extracting current_period_end: {e}")
        return None


def to_iso_date(unix_ts):
    """Convert a Unix timestamp (in seconds) to ISO 8601 string"""
    if not unix_ts:
        return None
    try:
        dt = datetime.fromtimestamp(int(unix_ts), tz=timezone.utc)
        iso_string = dt.isoformat()
        print(f"🕒 Converted {unix_ts} → {iso_string}")
        return iso_string
    except Exception as e:
        print(f"⚠️ Error converting timestamp {unix_ts}: {e}")
        return None

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

            print(f"📊 Subscription object type: {type(subscription)}")
            print(f"📊 Has current_period_end: {hasattr(subscription, 'current_period_end')}")
            print(f"📊 current_period_end value: {getattr(subscription, 'current_period_end', 'NOT FOUND')}")

            current_period_end_value = get_current_period_end(subscription)
            print(f"📊 Extracted current_period_end: {current_period_end_value} (type: {type(current_period_end_value)})")

            # Get the payment method from the subscription and set as customer default
            payment_method_id = getattr(subscription, 'default_payment_method', None)
            print(f"💳 Payment method from subscription: {payment_method_id}")

            # Set this as the customer's default payment method for invoices
            if payment_method_id:
                try:
                    stripe.Customer.modify(
                        customer_id,
                        invoice_settings={
                            'default_payment_method': payment_method_id
                        }
                    )
                    print(f"✅ Set default payment method: {payment_method_id} for customer: {customer_id}")
                except Exception as pm_error:
                    print(f"⚠️ Error setting default payment method: {pm_error}")

            result = supabase.table('users').update({
                'is_paid': True,
                'stripe_customer_id': customer_id,
                'stripe_subscription_id': subscription_id,
                'subscription_status': subscription.status,
                'current_period_end': to_iso_date(current_period_end_value)
            }).eq('email', customer_email).execute()

            if result.data:
                print(f"✅ Successfully updated subscription for: {customer_email}")
            else:
                print(f"⚠️ No user found with email: {customer_email}")

        except Exception as e:
            print(f"❌ Error updating user: {e}")
            import traceback
            traceback.print_exc()
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

                print(f"📊 Invoice renewal - subscription type: {type(subscription)}")
                current_period_end_value = get_current_period_end(subscription)
                print(f"📊 Invoice renewal - current_period_end: {current_period_end_value}")

                # Get the payment method from the subscription and set as default
                payment_method_id = subscription.default_payment_method

                print(f"💳 Payment method from subscription: {payment_method_id}")

                # Set this as the customer's default payment method
                if payment_method_id:
                    try:
                        stripe.Customer.modify(
                            customer_id,
                            invoice_settings={
                                'default_payment_method': payment_method_id
                            }
                        )
                        print(f"✅ Set default payment method: {payment_method_id} for customer: {customer_id}")
                    except Exception as pm_error:
                        print(f"⚠️ Error setting default payment method: {pm_error}")

                supabase.table('users').update({
                    'is_paid': True,
                    'subscription_status': subscription.status,
                    'current_period_end': to_iso_date(current_period_end_value)
                }).eq('stripe_customer_id', customer_id).execute()

                print(f"✅ Renewed subscription for customer: {customer_id}")

            except Exception as e:
                print(f"❌ Error updating renewal: {e}")
                import traceback
                traceback.print_exc()

    # Handle subscription updates (e.g., status changes)
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        status = subscription.get('status')

        print(f"🔄 Subscription updated for customer: {customer_id}, status: {status}")

        try:
            current_period_end_value = get_current_period_end(subscription)

            supabase.table('users').update({
                'subscription_status': status,
                'current_period_end': to_iso_date(current_period_end_value),
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

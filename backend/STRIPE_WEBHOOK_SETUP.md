# Stripe Webhook Setup Guide

## 🎯 Purpose
This webhook automatically updates `is_paid=true` in your database when a user completes payment.

## 📝 Setup Instructions

### 1. **For Testing (Stripe CLI - Sandbox Mode)**

Install Stripe CLI:
```bash
# macOS
brew install stripe/stripe-cli/stripe

# Linux
wget https://github.com/stripe/stripe-cli/releases/download/v1.19.4/stripe_1.19.4_linux_x86_64.tar.gz
tar -xvf stripe_1.19.4_linux_x86_64.tar.gz
sudo mv stripe /usr/local/bin/
```

Login to Stripe CLI:
```bash
stripe login
```

Forward webhook events to your local server:
```bash
stripe listen --forward-to http://127.0.0.1:5000/api/stripe/webhook
```

**Important**: The Stripe CLI will output a webhook signing secret like:
```
> Ready! Your webhook signing secret is whsec_abc123... (^C to quit)
```

Add this to your `backend/.env`:
```
STRIPE_WEBHOOK_SECRET=whsec_abc123...
```

### 2. **For Production**

1. Go to Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. Enter your production URL: `https://yourdomain.com/api/stripe/webhook`
4. Select events to listen for:
   - `checkout.session.completed` (required)
   - `customer.subscription.updated` (optional)
   - `customer.subscription.deleted` (optional)
5. Copy the "Signing secret" (starts with `whsec_`)
6. Add to your production `.env`:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_production_secret_here
   ```

## 🧪 Testing the Webhook

### Test with Stripe CLI:
1. Start your Flask server: `python app.py`
2. In another terminal, run: `stripe listen --forward-to http://127.0.0.1:5000/api/stripe/webhook`
3. In a third terminal, trigger a test event:
   ```bash
   stripe trigger checkout.session.completed
   ```

### Test with real checkout:
1. Make sure Stripe CLI is running (`stripe listen --forward-to...`)
2. Complete a test checkout on your frontend
3. Check your terminal for webhook events
4. Check your database - `is_paid` should be `true`

## 📊 What the Webhook Does

When a payment is completed, the webhook:
1. ✅ Verifies the webhook signature (security)
2. ✅ Extracts customer email from the Stripe session
3. ✅ Updates user in database:
   - `is_paid = true`
   - `stripe_customer_id = <customer_id>`
   - `stripe_subscription_id = <subscription_id>` (if subscription)
   - `subscription_status = 'active'`

## 🔒 Security

The webhook verifies the signature using `STRIPE_WEBHOOK_SECRET` to ensure:
- Events actually come from Stripe
- Events haven't been tampered with
- Protection against replay attacks

## 🐛 Troubleshooting

**Webhook not receiving events:**
- Make sure Stripe CLI is running
- Check that your Flask server is running on port 5000
- Verify `STRIPE_WEBHOOK_SECRET` is set in `.env`

**User not updating:**
- Check that the customer email in Stripe matches the email in your database
- Check Flask console for error messages
- Verify Supabase credentials are correct

**Signature verification failing:**
- Make sure you're using the correct webhook secret
- In test mode, use the secret from `stripe listen`
- In production, use the secret from Stripe Dashboard

## 📝 Environment Variables

Required in `backend/.env`:
```bash
STRIPE_SECRET_KEY=sk_test_...              # Your Stripe secret key
STRIPE_WEBHOOK_SECRET=whsec_...            # From Stripe CLI or Dashboard
SUPABASE_URL=https://...                   # Your Supabase project URL
SUPABASE_KEY=...                           # Supabase service role key
```

## 🚀 Deployment Notes

For production deployment:
1. Set environment variables in your hosting platform (Heroku, Railway, etc.)
2. Configure webhook endpoint in Stripe Dashboard
3. Use production webhook secret
4. Monitor webhook logs in Stripe Dashboard

## 📖 Additional Resources

- [Stripe Webhooks Documentation](https://stripe.com/docs/webhooks)
- [Stripe CLI Documentation](https://stripe.com/docs/stripe-cli)
- [Testing Webhooks](https://stripe.com/docs/webhooks/test)

import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { loadStripe } from "@stripe/stripe-js";
import { Elements, CardElement, useStripe, useElements } from "@stripe/react-stripe-js";
import "../Styles/Checkout.css";

// Load Stripe with your publishable key - fallback to the key from .env
const STRIPE_KEY = process.env.REACT_APP_STRIPE_PUBLIC_KEY || "pk_test_51SFbieC0PRtSkVT4B5tU24PXfgMbqXTiRBnoGAjaqsMJX4CG2VGJW3eBUCm14pwAf7IJAe1GNwVnpgvDpMRCwITw00njEs0tSh";

// Validate Stripe key exists
if (!STRIPE_KEY) {
  console.error("Stripe publishable key is missing!");
}

const stripePromise = loadStripe(STRIPE_KEY);

// Card element styling
const cardElementOptions = {
  style: {
    base: {
      fontSize: '16px',
      color: '#1E1E1E',
      fontFamily: '"Poppins", sans-serif',
      '::placeholder': {
        color: '#999',
      },
    },
    invalid: {
      color: '#ff4545',
    },
  },
};

const CheckoutForm = () => {
  const stripe = useStripe();
  const elements = useElements();
  const location = useLocation();
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    fullName: "",
    email: "",
    zip: ""
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [clientSecret, setClientSecret] = useState("");

  // Get plan data from navigation state
  const selectedPlan = location.state?.selectedPlan;

  // Redirect if no plan selected
  useEffect(() => {
    if (!selectedPlan) {
      navigate('/membership');
      return;
    }

    // Create payment intent when component mounts
    const createPaymentIntent = async () => {
      try {
        const response = await fetch('http://127.0.0.1:5000/api/create-payment-intent', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            amount: selectedPlan.totalPrice,
            currency: 'thb',
            // Don't pass email yet - will add it when submitting
          }),
        });

        const data = await response.json();

        if (data.error) {
          setError(data.error);
        } else {
          setClientSecret(data.clientSecret);
        }
      } catch (err) {
        setError('Failed to initialize payment. Please try again.');
        console.error('Payment intent error:', err);
      }
    };

    createPaymentIntent();
  }, [selectedPlan, navigate]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!stripe || !elements || !clientSecret) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Extract payment_intent_id from client secret
      const paymentIntentId = clientSecret.split('_secret_')[0];

      // Update PaymentIntent with email before confirming
      const updateResponse = await fetch('http://127.0.0.1:5000/api/update-payment-intent', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          payment_intent_id: paymentIntentId,
          email: formData.email,
        }),
      });

      const updateData = await updateResponse.json();

      if (updateData.error) {
        setError('Failed to update payment. Please try again.');
        setLoading(false);
        return;
      }

      // Now confirm the payment
      const cardElement = elements.getElement(CardElement);

      const { error: stripeError, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
        payment_method: {
          card: cardElement,
          billing_details: {
            name: formData.fullName,
            email: formData.email,
            address: {
              postal_code: formData.zip,
            },
          },
        },
      });

      if (stripeError) {
        setError(stripeError.message);
        setLoading(false);
      } else if (paymentIntent.status === 'succeeded') {
        // Payment successful - redirect to success page
        console.log('✅ Payment succeeded!', paymentIntent);
        console.log('Payment Intent ID:', paymentIntent.id);
        navigate('/payment-success');
      }
    } catch (err) {
      setError('An unexpected error occurred. Please try again.');
      console.error('Payment error:', err);
      setLoading(false);
    }
  };

  if (!selectedPlan) {
    return null;
  }

  return (
    <div className="checkout-page-container">
      <header className="checkout-page-header">
        <h1 className="page-header-text">CHECKOUT</h1>
        <p className="checkout-page-header-subtitle">Complete your payment to activate your membership.</p>
      </header>

      <div className="checkout-content">
        <div className="checkout-card">
          {/* Plan Summary */}
          <div className="checkout-plan-summary">
            <h3 className="plan-summary-title">Selected Plan</h3>
            <div className="plan-summary-details">
              <span className="plan-summary-duration">{selectedPlan.duration}</span>
              <span className="plan-summary-price">{selectedPlan.totalPrice}฿</span>
            </div>
            {selectedPlan.savings && (
              <span className="plan-summary-savings">{selectedPlan.savings}</span>
            )}
          </div>

          <form onSubmit={handleSubmit} className="checkout-form">
            <div className="form-group">
              <label htmlFor="fullName" className="form-label">Full Name</label>
              <input
                type="text"
                id="fullName"
                name="fullName"
                value={formData.fullName}
                onChange={handleChange}
                className="form-input"
                placeholder="John Doe"
                required
              />
            </div>

            <div className="form-group">
              <label htmlFor="email" className="form-label">Email</label>
              <input
                type="email"
                id="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                className="form-input"
                placeholder="john@example.com"
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Card Information</label>
              <div className="card-element-wrapper">
                <CardElement options={cardElementOptions} />
              </div>
            </div>

            <div className="form-group">
              <label htmlFor="zip" className="form-label">ZIP Code (Optional)</label>
              <input
                type="text"
                id="zip"
                name="zip"
                value={formData.zip}
                onChange={handleChange}
                className="form-input"
                placeholder="12345"
              />
            </div>

            {error && (
              <div className="checkout-error" role="alert">
                {error}
              </div>
            )}

            <button
              type="submit"
              className="signup-cta-button checkout-submit-button"
              disabled={!stripe || loading}
            >
              {loading ? 'Processing...' : `Pay ${selectedPlan.totalPrice}฿`}
            </button>

            <p className="checkout-security-note">
              🔒 Your payment is secure and encrypted via Stripe.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
};

const Checkout = () => {
  const [stripeReady, setStripeReady] = useState(false);

  useEffect(() => {
    // Ensure Stripe is loaded before rendering Elements
    stripePromise.then(() => {
      setStripeReady(true);
    }).catch((error) => {
      console.error("Failed to load Stripe:", error);
    });
  }, []);

  if (!stripeReady) {
    return (
      <div className="checkout-page-container">
        <div className="checkout-content">
          <div className="checkout-card">
            <p style={{ textAlign: 'center', padding: '2rem' }}>Loading payment system...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Elements stripe={stripePromise}>
      <CheckoutForm />
    </Elements>
  );
};

export default Checkout;

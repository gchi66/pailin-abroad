import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "../Styles/Checkout.css";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";

// ✅ Load Stripe publishable key from .env
const STRIPE_KEY =
  process.env.REACT_APP_STRIPE_PUBLIC_KEY ||
  "pk_test_51SFbiU2FEde6izNxgllAtD0Mjc7FWGfMjTmeeuO6OeiGEmSzgAnQdGPnn5lRkx6Pe3NqeEfrOy0FEecwGCMQwe4r00oG3xBfRM";

const Checkout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [userEmail, setUserEmail] = useState("");

  const selectedPlan = location.state?.selectedPlan;

  // ✅ Fetch user email on mount
  useEffect(() => {
    const getUserEmail = async () => {
      const {
        data: { user },
      } = await supabaseClient.auth.getUser();
      if (user) {
        setUserEmail(user.email);
      }
    };
    getUserEmail();
  }, []);

  // ✅ Redirect if no plan selected
  useEffect(() => {
    if (!selectedPlan) {
      navigate("/membership");
    }
  }, [selectedPlan, navigate]);

  const handleCheckout = async () => {
    setLoading(true);
    setError(null);

    try {
      // ✅ Match keys exactly to your Membership plans
      const priceIdMap = {
        "1 MONTH": "price_1SH6OH2FEde6izNxD1YRbtqx",
        "3 MONTHS": "price_1SH6OH2FEde6izNxWvgdYvLW",
        "6 MONTHS": "price_1SH6OH2FEde6izNxcyqYFrou",
      };

      const priceId = priceIdMap[selectedPlan.duration];
      console.log("Selected plan duration:", selectedPlan.duration);

      if (!priceId) {
        setError("Invalid plan selected");
        setLoading(false);
        return;
      }

      // ✅ Create checkout session
      const response = await fetch(`${API_BASE_URL}/api/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          price_id: priceId,
          email: userEmail,
          success_url: "http://localhost:3000/payment-success",
          cancel_url: "http://localhost:3000/checkout",
        }),
      });

      const data = await response.json();

      if (data.error) {
        setError(data.error);
        setLoading(false);
        return;
      }

      // ✅ Redirect to Stripe Checkout (Clover-compliant)
      window.location.href = data.url;

    } catch (err) {
      setError("An unexpected error occurred. Please try again.");
      console.error("Checkout error:", err);
      setLoading(false);
    }
  };

  if (!selectedPlan) return null;

  return (
    <div className="checkout-page-container">
      <header className="checkout-page-header">
        <h1 className="page-header-text">CHECKOUT</h1>
        <p className="checkout-page-header-subtitle">
          Complete your payment to activate your membership.
        </p>
      </header>

      <div className="checkout-content">
        <div className="checkout-card">
          <div className="checkout-plan-summary">
            <h3 className="plan-summary-title">Selected Plan</h3>
            <div className="plan-summary-details">
              <span className="plan-summary-duration">
                {selectedPlan.duration}
              </span>
              <span className="plan-summary-price">
                {selectedPlan.totalPrice}฿
              </span>
            </div>
            {selectedPlan.savings && (
              <span className="plan-summary-savings">
                {selectedPlan.savings}
              </span>
            )}
            <p
              style={{ marginTop: "1rem", fontSize: "0.9rem", color: "#666" }}
            >
              Auto-renews every {selectedPlan.duration.toLowerCase()}. Cancel
              anytime.
            </p>
          </div>

          {error && (
            <div className="checkout-error" role="alert">
              {error}
            </div>
          )}

          <button
            onClick={handleCheckout}
            className="signup-cta-button checkout-submit-button"
            disabled={loading}
          >
            {loading
              ? "Redirecting to checkout..."
              : `Subscribe for ${selectedPlan.totalPrice}฿`}
          </button>

          <p className="checkout-security-note">
            🔒 Your payment is secure and encrypted via Stripe.
          </p>
        </div>
      </div>
    </div>
  );
};

export default Checkout;

import React, { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "../Styles/Checkout.css";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";


const Checkout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const [emailInput, setEmailInput] = useState("");

  const [selectedPlan, setSelectedPlan] = useState(() => {
    if (location.state?.selectedPlan) return location.state.selectedPlan;
    const storedPlan = sessionStorage.getItem("checkout_selected_plan");
    if (!storedPlan) return null;
    try {
      return JSON.parse(storedPlan);
    } catch (err) {
      console.warn("Failed to parse stored checkout plan:", err);
      return null;
    }
  });
  const searchParams = new URLSearchParams(location.search || "");
  const emailFromUrl = searchParams.get("email") || "";
  const currencySymbol = selectedPlan?.currency === "USD" ? "$" : "฿";
  const formatAmount = (value) => {
    const amount = Number(value);
    if (!Number.isFinite(amount)) return value;
    return amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  };

  // ✅ Fetch user email on mount
  useEffect(() => {
    const getUserEmail = async () => {
      const {
        data: { user },
      } = await supabaseClient.auth.getUser();
      if (user) {
        setUserEmail(user.email);
        setEmailInput(user.email);
        return;
      }
      if (emailFromUrl) {
        setUserEmail(emailFromUrl);
        setEmailInput(emailFromUrl);
      }
    };
    getUserEmail();
  }, [emailFromUrl]);

  useEffect(() => {
    if (location.state?.selectedPlan) {
      setSelectedPlan(location.state.selectedPlan);
    }
  }, [location.state?.selectedPlan]);

  // ✅ Redirect if no plan selected
  useEffect(() => {
    if (!selectedPlan) {
      navigate("/membership");
      return;
    }
    sessionStorage.removeItem("checkout_selected_plan");
  }, [selectedPlan, navigate]);

  const handleCheckout = async () => {
    setLoading(true);
    setError(null);

    try {
      const finalEmail = (userEmail || emailInput || "").trim();
      if (!finalEmail) {
        setError("Please enter a valid email address.");
        setLoading(false);
        return;
      }

      // ✅ Create checkout session
      const response = await fetch(`${API_BASE_URL}/api/create-checkout-session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          billing_period: selectedPlan.billingPeriod,
          email: finalEmail,
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
  const isLifetime = selectedPlan.billingPeriod === "lifetime";

  return (
    <div className="checkout-page-container">
      <header className="checkout-page-header">
        <h1 className="page-header-text">Checkout</h1>
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
                {currencySymbol}{formatAmount(selectedPlan.totalPrice)}
              </span>
            </div>
            {selectedPlan.savings && (
              <span className="plan-summary-savings">
                {selectedPlan.savings}
              </span>
            )}
            {!isLifetime && (
              <p
                style={{ marginTop: "1rem", fontSize: "0.9rem", color: "#666" }}
              >
                Auto-renews every {selectedPlan.duration.toLowerCase()}. Cancel
                anytime.
              </p>
            )}
          </div>

          {error && (
            <div className="checkout-error" role="alert">
              {error}
            </div>
          )}

          {!userEmail && (
            <div className="checkout-email-entry">
              <label htmlFor="checkout-email" className="form-label">Email address</label>
              <input
                id="checkout-email"
                type="email"
                className="form-input"
                value={emailInput}
                onChange={(event) => {
                  setEmailInput(event.target.value);
                  setError(null);
                }}
                placeholder="you@example.com"
                required
              />
            </div>
          )}

          <button
            onClick={handleCheckout}
            className="signup-cta-button checkout-submit-button"
            disabled={loading}
          >
            {loading
              ? "Redirecting to checkout..."
              : isLifetime
                ? `Pay ${currencySymbol}${formatAmount(selectedPlan.totalPrice)}`
                : `Subscribe for ${currencySymbol}${formatAmount(selectedPlan.totalPrice)}`}
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

import React, { useState } from "react";
import supabaseClient from "../supabaseClient";
import "../Styles/QuickSignupModal.css";

const QuickSignupModal = ({ isOpen, onClose, onSuccess }) => {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: ""
  });
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    // Clear error when user types
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    // Basic validation
    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      setLoading(false);
      return;
    }

    if (formData.password.length < 6) {
      setError("Password must be at least 6 characters");
      setLoading(false);
      return;
    }

    try {
      // Supabase signup with email confirmation
      const { error: signupError } = await supabaseClient.auth.signUp({
        email: formData.email,
        password: formData.password,
        options: {
          emailRedirectTo: `${window.location.origin}/`,
          data: {
            is_verified: false // Set custom metadata
          }
        }
      });

      if (signupError) {
        setError(signupError.message);
        setLoading(false);
        return;
      }

      // User is now logged in (but not verified)
      // Show success message and allow them to continue
      setSuccess(true);
      setLoading(false);

    } catch (err) {
      setError("An error occurred during signup. Please try again.");
      setLoading(false);
      console.error("Signup error:", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="quick-signup-overlay" onClick={onClose}>
      <div
        className="quick-signup-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <button className="close-btn" onClick={onClose}>×</button>

        {!success ? (
          <>
            <h2 className="modal-title">Create an Account</h2>
            <p className="modal-subtitle">Sign up to continue to checkout</p>

            <form onSubmit={handleSubmit} className="signup-form">
              <div className="form-group">
                <label htmlFor="email" className="form-label">Email</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  className="form-input"
                  placeholder="your@email.com"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="password" className="form-label">Password</label>
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  className="form-input"
                  placeholder="Enter password"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="confirmPassword" className="form-label">Confirm Password</label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className="form-input"
                  placeholder="Confirm password"
                  required
                />
              </div>

              {error && (
                <div className="error-message" role="alert">
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="signup-cta-button modal-signup-btn"
                disabled={loading}
              >
                {loading ? "Signing up..." : "Sign Up"}
              </button>

              <p className="secondary-text">
                Already have an account?{" "}
                <button type="button" className="login-link" onClick={() => {
                  // TODO: Toggle to login modal
                  console.log("Switch to login");
                }}>
                  Log in
                </button>
              </p>
            </form>
          </>
        ) : (
          <div className="success-state">
            <div className="success-icon">✉️</div>
            <h3 className="success-title">Account Created!</h3>
            <p className="success-message">
              We've sent you a verification email. You can proceed to checkout now and verify your email later.
            </p>
            <button
              className="signup-cta-button modal-signup-btn"
              onClick={() => {
                if (onSuccess) {
                  onSuccess(); // Trigger callback to proceed to checkout
                } else {
                  onClose();
                }
              }}
            >
              Continue to Checkout
            </button>
            <p className="success-message" style={{ fontSize: '0.85rem', marginTop: '1rem', color: '#666' }}>
              Please verify your email to unlock all features
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default QuickSignupModal;

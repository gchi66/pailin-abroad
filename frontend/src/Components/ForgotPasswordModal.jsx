import React, { useState } from "react";
import axios from "axios";
import "../Styles/ForgotPasswordModal.css";

const ForgotPasswordModal = ({ isOpen, onClose, onBackToLogin }) => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [magicLinkLoading, setMagicLinkLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Clear form when modal opens/closes
  React.useEffect(() => {
    if (isOpen) {
      setEmail("");
      setError("");
      setSuccess("");
      setLoading(false);
      setMagicLinkLoading(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleMagicLink = async () => {
    if (!email) {
      setError("Please enter your email address first");
      return;
    }

    setMagicLinkLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await axios.post(
        "http://127.0.0.1:5000/api/forgot-password/magic-link",
        { email },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      setSuccess(response.data.message);
    } catch (error) {
      console.error("Magic Link Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || "Failed to send magic link. Please try again.");
    } finally {
      setMagicLinkLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();

    if (!email) {
      setError("Please enter your email address");
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await axios.post(
        "http://127.0.0.1:5000/api/forgot-password/reset",
        { email },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      setSuccess(response.data.message);
    } catch (error) {
      console.error("Reset Password Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || "Failed to send reset email. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleBackToLogin = () => {
    // Clear all states when going back to login
    setEmail("");
    setError("");
    setSuccess("");
    setLoading(false);
    setMagicLinkLoading(false);

    console.log("Back to login clicked");
    if (onBackToLogin) {
      onBackToLogin();
    }
  };

  return (
    <div className="forgot-password-modal">
      <div className="forgot-password-modal-content">
        <button className="forgot-password-modal-close" onClick={onClose}>
          &times;
        </button>
        <h2>Forgot password?</h2>

        {/* Error/Success Messages */}
        {error && <div className="forgot-password-error-message">{error}</div>}
        {success && <div className="forgot-password-success-message">{success}</div>}

        {/* Email Input - Shared for both options */}
        <div className="forgot-password-section">
          <div className="forgot-password-form-group">
            <input
              type="email"
              className="forgot-password-input"
              placeholder="Email Address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Magic Link Section */}
        <div className="forgot-password-section">
          <button
            className="submit-btn forgot-password-magic-btn"
            onClick={handleMagicLink}
            disabled={magicLinkLoading || loading}
          >
            {magicLinkLoading ? "SENDING..." : "Get a sign-in link"}
          </button>
        </div>

        {/* Divider */}
        <div className="forgot-password-divider">OR</div>

        {/* Reset Password Section */}
        <div className="forgot-password-section">
          <h3>Reset password</h3>
          <p className="forgot-password-description">
            Click below to receive password reset instructions
          </p>

          <form onSubmit={handleResetPassword}>
            <button
              type="submit"
              className="submit-btn"
              disabled={loading || magicLinkLoading}
            >
              {loading ? "SENDING..." : "RESET PASSWORD"}
            </button>
          </form>
        </div>

        {/* Back to Login Link */}
        <div className="forgot-password-back">
          <span className="forgot-password-back-link" onClick={handleBackToLogin}>
            &larr; Back to log in
          </span>
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordModal;

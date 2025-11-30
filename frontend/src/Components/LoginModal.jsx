import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import ForgotPasswordModal from "./ForgotPasswordModal";
import "../Styles/LoginModal.css";

const LoginModal = ({ isOpen, onClose, toggleSignupModal }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [socialLoading, setSocialLoading] = useState("");
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();

    // Basic validation
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/login`,
        { email, password },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const { access_token, refresh_token } = response.data.session;
      const { error: sessionError } = await supabaseClient.auth.setSession({
        access_token,
        refresh_token,
      });

      if (sessionError) {
        throw new Error("Failed to establish session");
      } else {
        console.log("Login successful!");
        onClose(); // Close modal on success
        navigate("/pathway"); // Navigate to pathway instead of profile
      }
    } catch (error) {
      console.error("Login Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || error.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSocialSignIn = async (provider) => {
    setError("");
    setSocialLoading(provider);

    try {
      const { error: oauthError } = await supabaseClient.auth.signInWithOAuth({
        provider,
        options: {
          redirectTo: `${window.location.origin}/onboarding`
        }
      });

      if (oauthError) {
        throw oauthError;
      }
    } catch (oauthErr) {
      console.error(`Social login failed (${provider}):`, oauthErr);
      setError(oauthErr.message || "Failed to sign in with social login.");
      setSocialLoading("");
    }
  };

  return (
    <div className="login-modal">
      <div className="login-modal-content">
        <button className="login-modal-close" onClick={onClose}>
          &times;
        </button>
        <h2>Sign In</h2>
        <form onSubmit={handleLogin}>
          {error && <div className="login-error-message">{error}</div>}

          <div className="login-form-group">
            <label className="login-form-label">
              Email
            </label>
            <input
              type="email"
              className="login-form-input"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="login-form-group">
            <label className="login-form-label">
              Password
            </label>
            <input
              type="password"
              className="login-form-input"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="login-form-footer">
            <label className="login-remember-label">
              <input type="checkbox" className="login-remember-checkbox" /> Remember me
            </label>
            <span
              className="login-forgot-link"
              onClick={(e) => {
                e.preventDefault();
                setShowForgotPassword(true);
              }}
              style={{ cursor: 'pointer' }}
            >
              Forgot username/password?
            </span>
          </div>
          <button
            type="submit"
            className={`login-submit-btn ${loading ? 'loading' : ''}`}
            disabled={loading}
          >
            {loading ? "SIGNING IN..." : "SIGN IN"}
          </button>
        </form>
        <div className="login-divider">OR</div>
        <button
          className="login-social-button google"
          onClick={() => handleSocialSignIn("google")}
          disabled={socialLoading === "google"}
          style={{ opacity: socialLoading === "google" ? 0.6 : 1 }}
        >
          {socialLoading === "google" ? "Connecting to Google..." : "Sign in with Google"}
        </button>
        <button
          className="login-social-button facebook"
          onClick={() => handleSocialSignIn("facebook")}
          disabled={socialLoading === "facebook"}
          style={{ opacity: socialLoading === "facebook" ? 0.6 : 1 }}
        >
          {socialLoading === "facebook" ? "Connecting to Facebook..." : "Sign in with Facebook"}
        </button>

        {toggleSignupModal && (
          <p className="login-switch-text">
            Don't have an account?
            <span className="login-switch-link" onClick={() => {
              onClose(); // Close login modal
              toggleSignupModal(); // Open signup modal
            }}>
              Sign up
            </span>
          </p>
        )}
      </div>

      {/* Forgot Password Modal */}
      <ForgotPasswordModal
        isOpen={showForgotPassword}
        onClose={() => setShowForgotPassword(false)}
        onBackToLogin={() => setShowForgotPassword(false)}
      />
    </div>
  );
};

export default LoginModal;

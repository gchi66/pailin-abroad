import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import ForgotPasswordModal from "./ForgotPasswordModal";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/LoginModal.css";

const LoginModal = ({ isOpen, onClose, toggleSignupModal }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showForgotPassword, setShowForgotPassword] = useState(false);
  const [socialLoading, setSocialLoading] = useState("");
  const navigate = useNavigate();
  const { ui } = useUiLang();

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();

    // Basic validation
    if (!email || !password) {
      setError(t("authModals.signIn.errors.missingFields", ui));
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
        onClose(); // Close modal on success
        navigate("/pathway"); // Navigate to pathway instead of profile
      }
    } catch (error) {
      const backendError = error.response?.data;
      console.error("Login Error:", backendError || error.message);

      if (!error.response) {
        setError(t("authModals.signIn.errors.network", ui));
        return;
      }

      switch (backendError?.error) {
        case "INVALID_CREDENTIALS":
          setError(t("authModals.signIn.errors.invalidCredentials", ui));
          return;
        case "MISSING_FIELDS":
          setError(t("authModals.signIn.errors.missingFields", ui));
          return;
        case "AUTH_ERROR":
        case "SERVER_ERROR":
          setError(t("authModals.signIn.errors.authError", ui));
          return;
        default: {
          const message = backendError?.message || error.message || "Login failed.";
          setError(`${message} ${t("authModals.signIn.errors.fallbackHelp", ui)}`.trim());
        }
      }
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
      setError(oauthErr.message || "Failed to log in with social login.");
      setSocialLoading("");
    }
  };

  return (
    <div className="login-modal">
      <div className="login-modal-content">
        <button className="login-modal-close" onClick={onClose}>
          &times;
        </button>
        <h2>{t("authModals.signIn.title", ui)}</h2>
        <form onSubmit={handleLogin}>
          {error && <div className="login-error-message">{error}</div>}

          <div className="login-form-group">
            <label className="login-form-label">{t("authModals.signIn.emailLabel", ui)}</label>
            <input
              type="email"
              className="login-form-input"
              placeholder={t("authModals.signIn.emailPlaceholder", ui)}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="login-form-group">
            <label className="login-form-label">{t("authModals.signIn.passwordLabel", ui)}</label>
            <input
              type="password"
              className="login-form-input"
              placeholder={t("authModals.signIn.passwordPlaceholder", ui)}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="login-form-footer">
            <label className="login-remember-label">
              <input type="checkbox" className="login-remember-checkbox" />{" "}
              {t("authModals.signIn.rememberMe", ui)}
            </label>
            <span
              className="login-forgot-link"
              onClick={(e) => {
                e.preventDefault();
                setShowForgotPassword(true);
              }}
              style={{ cursor: 'pointer' }}
            >
              {t("authModals.signIn.forgotLink", ui)}
            </span>
          </div>
          <button
            type="submit"
            className={`login-submit-btn ${loading ? 'loading' : ''}`}
            disabled={loading}
          >
            {loading ? t("authModals.signIn.submitting", ui) : t("authModals.signIn.submit", ui)}
          </button>
        </form>
        <div className="login-divider">{t("authModals.signIn.divider", ui)}</div>
        <button
          className="login-social-button google"
          onClick={() => handleSocialSignIn("google")}
          disabled={socialLoading === "google"}
          style={{ opacity: socialLoading === "google" ? 0.6 : 1 }}
        >
          {socialLoading === "google"
            ? t("authModals.signIn.googleConnecting", ui)
            : t("authModals.signIn.google", ui)}
        </button>

        {toggleSignupModal && (
          <p className="login-switch-text">
            {t("authModals.signIn.noAccount", ui)}
            <span className="login-switch-link" onClick={() => {
              onClose(); // Close login modal
              toggleSignupModal(); // Open signup modal
            }}>
              {t("authModals.signIn.signUpLink", ui)}
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

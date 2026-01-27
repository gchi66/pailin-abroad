import React, { useState } from "react";
import supabaseClient from "../supabaseClient";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
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
  const { ui } = useUiLang();

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
      setError(t("quickSignup.passwordMismatch", ui));
      setLoading(false);
      return;
    }

    if (formData.password.length < 6) {
      setError(t("quickSignup.passwordTooShort", ui));
      setLoading(false);
      return;
    }

    try {
      // Supabase signup with email confirmation
      const { error: signupError } = await supabaseClient.auth.signUp({
        email: formData.email,
        password: formData.password,
        options: {
          emailRedirectTo: `${window.location.origin}/onboarding`,
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
      setError(t("quickSignup.signupError", ui));
      setLoading(false);
      console.error("Signup error:", err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="quick-signup-overlay">
      <div
        className="quick-signup-modal"
      >
        <button className="close-btn" onClick={onClose}>×</button>

        {!success ? (
          <>
            <h2 className="modal-title">{t("quickSignup.title", ui)}</h2>
            <p className="modal-subtitle">{t("quickSignup.subtitle", ui)}</p>

            <form onSubmit={handleSubmit} className="signup-form">
              <div className="form-group">
                <label htmlFor="email" className="form-label">{t("quickSignup.emailLabel", ui)}</label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  value={formData.email}
                  onChange={handleChange}
                  className="form-input"
                  placeholder={t("quickSignup.emailPlaceholder", ui)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="password" className="form-label">{t("quickSignup.passwordLabel", ui)}</label>
                <input
                  type="password"
                  id="password"
                  name="password"
                  value={formData.password}
                  onChange={handleChange}
                  className="form-input"
                  placeholder={t("quickSignup.passwordPlaceholder", ui)}
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="confirmPassword" className="form-label">{t("quickSignup.confirmPasswordLabel", ui)}</label>
                <input
                  type="password"
                  id="confirmPassword"
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className="form-input"
                  placeholder={t("quickSignup.confirmPasswordPlaceholder", ui)}
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
                {loading ? t("quickSignup.submitting", ui) : t("quickSignup.submit", ui)}
              </button>

              <p className="secondary-text">
                {t("quickSignup.alreadyHaveAccount", ui)}{" "}
                <button type="button" className="login-link" onClick={() => {
                  // TODO: Toggle to login modal
                  console.log("Switch to login");
                }}>
                  {t("quickSignup.loginLink", ui)}
                </button>
              </p>
            </form>
          </>
        ) : (
          <div className="success-state">
            <div className="success-icon">✉️</div>
            <h3 className="success-title">{t("quickSignup.successTitle", ui)}</h3>
            <p className="success-message">
              {t("quickSignup.successMessage", ui)}
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
              {t("quickSignup.continueCheckout", ui)}
            </button>
            <p className="success-message" style={{ fontSize: '0.85rem', marginTop: '1rem', color: '#666' }}>
              {t("quickSignup.verifyNote", ui)}
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default QuickSignupModal;

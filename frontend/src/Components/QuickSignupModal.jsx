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
  const passwordValue = formData.password;
  const confirmPasswordValue = formData.confirmPassword;
  const meetsLength = passwordValue.length >= 8;
  const meetsNumberOrSymbol = /[\d!@#$%^&*(),.?":{}|<>]/.test(passwordValue);
  const meetsUppercase = /[A-Z]/.test(passwordValue);
  const shouldShowMismatch =
    confirmPasswordValue.length > 0 &&
    passwordValue.length > 0 &&
    passwordValue !== confirmPasswordValue;

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
    if (!meetsLength) {
      setError(t("quickSignup.passwordTooShort", ui));
      setLoading(false);
      return;
    }

    if (!meetsNumberOrSymbol || !meetsUppercase) {
      setError(t("quickSignup.passwordRequirements", ui));
      setLoading(false);
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError(t("quickSignup.passwordMismatch", ui));
      setLoading(false);
      return;
    }

    try {
      console.debug("[QuickSignup] submit", {
        emailProvided: Boolean(formData.email),
        emailValue: formData.email,
        passwordLength: formData.password.length,
        confirmPasswordLength: formData.confirmPassword.length
      });

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
        console.warn("[QuickSignup] supabase signup error", {
          message: signupError.message,
          status: signupError.status,
          name: signupError.name
        });
        setError(signupError.message);
        setLoading(false);
        return;
      }

      console.info("[QuickSignup] signup success", { email: formData.email });

      // User is now logged in (but not verified)
      // Show success message and allow them to continue
      setSuccess(true);
      setLoading(false);

    } catch (err) {
      console.error("[QuickSignup] signup exception", err);
      setError(t("quickSignup.signupError", ui));
      setLoading(false);
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
                {shouldShowMismatch && (
                  <div className="onboarding-password-mismatch" role="alert">
                    {t("quickSignup.passwordMismatch", ui)}
                  </div>
                )}
              </div>

              <div className="onboarding-password-rules">
                <div className="onboarding-password-rule">
                  <img
                    src={meetsLength ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsLength ? "✓ Length requirement met" : "Length requirement not met"}
                    className={`onboarding-rule-icon ${meetsLength ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsLength ? "met" : ""}`}>
                    {t("quickSignup.passwordRule1", ui)}
                  </span>
                </div>
                <div className="onboarding-password-rule">
                  <img
                    src={meetsNumberOrSymbol ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsNumberOrSymbol ? "✓ Number or symbol requirement met" : "Number or symbol requirement not met"}
                    className={`onboarding-rule-icon ${meetsNumberOrSymbol ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsNumberOrSymbol ? "met" : ""}`}>
                    {t("quickSignup.passwordRule2", ui)}
                  </span>
                </div>
                <div className="onboarding-password-rule">
                  <img
                    src={meetsUppercase ? "/images/blue-password-checkmark.webp" : "/images/grey-password-checkmark.webp"}
                    alt={meetsUppercase ? "✓ Uppercase letter requirement met" : "Uppercase letter requirement not met"}
                    className={`onboarding-rule-icon ${meetsUppercase ? "met" : ""}`}
                  />
                  <span className={`onboarding-rule-text ${meetsUppercase ? "met" : ""}`}>
                    {t("quickSignup.passwordRule3", ui)}
                  </span>
                </div>
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
                  onSuccess(formData.email); // Trigger callback to proceed to checkout
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

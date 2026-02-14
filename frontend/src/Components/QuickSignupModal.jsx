import React, { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/QuickSignupModal.css";

const QuickSignupModal = ({ isOpen, onClose, onSuccess, selectedPlan }) => {
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    confirmPassword: ""
  });
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState("");
  const { ui } = useUiLang();
  const shouldForceContinue = success;
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

  const handleGoogleSignup = async () => {
    setError("");
    setSocialLoading("google");

    try {
      if (selectedPlan) {
        sessionStorage.setItem("checkout_selected_plan", JSON.stringify(selectedPlan));
      }

      const { error: oauthError } = await supabaseClient.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${window.location.origin}/checkout`
        }
      });

      if (oauthError) {
        throw oauthError;
      }
    } catch (oauthErr) {
      console.error("OAuth signup failed (google):", oauthErr);
      setError(oauthErr.message || t("quickSignup.signupError", ui));
      setSocialLoading("");
    }
  };

  useEffect(() => {
    if (!isOpen || !shouldForceContinue) return;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [isOpen, shouldForceContinue]);

  if (!isOpen) return null;

  return (
    <div className="quick-signup-overlay" onClick={(event) => {
      if (shouldForceContinue) {
        event.stopPropagation();
      }
    }}>
      <div
        className="quick-signup-modal"
      >
        {!success && (
          <button className="close-btn" onClick={onClose}>×</button>
        )}

        {!success ? (
          <>
            <h2 className="modal-title">{t("quickSignup.title", ui)}</h2>
            <p className="modal-subtitle">{t("quickSignup.subtitle", ui)}</p>

            <button
              type="button"
              className="social-button google quick-signup-social"
              onClick={handleGoogleSignup}
              disabled={socialLoading === "google" || loading}
            >
              {socialLoading === "google" ? (
                t("quickSignup.submitting", ui)
              ) : (
                <>
                  <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"></path>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"></path>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"></path>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"></path>
                  </svg>
                  {t("authModals.signUp.google", ui)}
                </>
              )}
            </button>

            <div className="quick-signup-divider">or</div>

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

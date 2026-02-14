import React, { useState } from "react";
import axios from "axios";
import "../Styles/ForgotPasswordModal.css";
import { API_BASE_URL } from "../config/api";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

const ForgotPasswordModal = ({ isOpen, onClose, onBackToLogin }) => {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [magicLinkLoading, setMagicLinkLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const { ui } = useUiLang();

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
      setError(t("authModals.forgotPassword.errors.missingEmailFirst", ui));
      return;
    }

    setMagicLinkLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/forgot-password/magic-link`,
        { email },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      setSuccess(
        ui === "th"
          ? t("authModals.forgotPassword.success.magicSent", ui)
          : response.data.message
      );
    } catch (error) {
      console.error("Magic Link Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || t("authModals.forgotPassword.errors.magicFail", ui));
    } finally {
      setMagicLinkLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();

    if (!email) {
      setError(t("authModals.forgotPassword.errors.missingEmail", ui));
      return;
    }

    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/forgot-password/reset`,
        { email },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      setSuccess(
        ui === "th"
          ? t("authModals.forgotPassword.success.resetSent", ui)
          : response.data.message
      );
    } catch (error) {
      console.error("Reset Password Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || t("authModals.forgotPassword.errors.resetFail", ui));
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
        <h2>{t("authModals.forgotPassword.title", ui)}</h2>

        {/* Error/Success Messages */}
        {error && <div className="forgot-password-error-message">{error}</div>}
        {success && <div className="forgot-password-success-message">{success}</div>}

        {/* Email Input - Shared for both options */}
        <p className="forgot-password-description">
          {t("authModals.forgotPassword.passwordlessNote", ui)}
        </p>
        <div className="forgot-password-section">
          <div className="forgot-password-form-group">
            <input
              type="email"
              className="forgot-password-input"
              placeholder={t("authModals.forgotPassword.emailPlaceholder", ui)}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
        </div>

        {/* Magic Link Section */}
        <div className="forgot-password-section">
          <button
            className="submit-btn forgot-password-magic-btn modal-form-submit"
            onClick={handleMagicLink}
            disabled={magicLinkLoading || loading}
          >
            {magicLinkLoading
              ? t("authModals.forgotPassword.sending", ui)
              : t("authModals.forgotPassword.sendMagicLink", ui)}
          </button>
        </div>

        {/* Divider */}
        <div className="forgot-password-divider">{t("authModals.forgotPassword.divider", ui)}</div>

        {/* Reset Password Section */}
        <div className="forgot-password-section">
          <h3>{t("authModals.forgotPassword.resetTitle", ui)}</h3>
          <p className="forgot-password-description">
            {t("authModals.forgotPassword.resetDescription", ui)}
          </p>

          <form onSubmit={handleResetPassword}>
            <button
              type="submit"
              className="submit-btn modal-form-submit forgot-password-reset-btn"
              disabled={loading || magicLinkLoading}
            >
              {loading
                ? t("authModals.forgotPassword.sending", ui)
                : t("authModals.forgotPassword.resetButton", ui)}
            </button>
          </form>
        </div>

        {/* Back to Login Link */}
        <div className="forgot-password-back">
          <span className="forgot-password-back-link" onClick={handleBackToLogin}>
            {t("authModals.forgotPassword.backToLogin", ui)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ForgotPasswordModal;

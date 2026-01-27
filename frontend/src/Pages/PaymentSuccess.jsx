import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/PaymentSuccess.css";

const PaymentSuccess = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  // Check if user email is verified
  const isVerified = user?.user_metadata?.is_verified || user?.email_confirmed_at;

  // Hide navbar and footer for unverified users
  useEffect(() => {
    if (!isVerified) {
      // Hide navbar and footer by adding a class to body
      document.body.classList.add('hide-header-footer');
    }

    return () => {
      // Clean up: remove class when component unmounts
      document.body.classList.remove('hide-header-footer');
    };
  }, [isVerified]);

  // Resend verification email
  const handleResendEmail = async () => {
    if (!user?.email) {
      setResendMessage(t("paymentSuccess.noEmail", uiLang));
      return;
    }

    setResendLoading(true);
    setResendMessage("");

    try {
      const { error } = await supabaseClient.auth.resend({
        type: 'signup',
        email: user.email,
        options: {
          emailRedirectTo: `${window.location.origin}/`
        }
      });

      if (error) {
        setResendMessage(`Error: ${error.message}`);
      } else {
        setResendMessage(t("paymentSuccess.resendSuccess", uiLang));
      }
    } catch (err) {
      setResendMessage(t("paymentSuccess.resendFail", uiLang));
      console.error("Resend email error:", err);
    } finally {
      setResendLoading(false);
    }
  };

  // Trigger fade-in animation on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  // Inline style for confetti background (to reference public folder correctly)
  const confettiStyle = {
    backgroundImage: `url(${process.env.PUBLIC_URL}/images/payment_success_confetti_bg.webp)`
  };

  return (
    <div className="payment-success-page">
      {/* Confetti overlay background */}
      <div className="confetti-overlay" style={confettiStyle}></div>

      <div className={`payment-success-container ${isVisible ? 'fade-in' : ''}`}>
        <div className="success-icon">✅</div>

        {isVerified ? (
          // Verified user - full access
          <>
            <h1 className="success-main-title">{t("paymentSuccess.verifiedTitle", uiLang)}</h1>
            <p className="success-subtitle">{t("paymentSuccess.verifiedSubtitle", uiLang)}</p>

            <p className="success-message">{t("paymentSuccess.verifiedMessage", uiLang)}</p>

            <Link to="/pathway" className="signup-cta-button success-cta-btn">
              {t("paymentSuccess.goToPathway", uiLang)}
            </Link>

            <Link to="/" className="secondary-link">
              {t("paymentSuccess.returnHome", uiLang)}
            </Link>
          </>
        ) : (
          // Unverified user - needs to verify email first
          <>
            <h1 className="success-main-title">{t("paymentSuccess.unverifiedTitle", uiLang)}</h1>
            <p className="success-subtitle">{t("paymentSuccess.unverifiedSubtitle", uiLang)}</p>

            <p className="success-message">
              {uiLang === "th"
                ? (
                  <>
                    {t("paymentSuccess.unverifiedMessagePrefix", uiLang)}
                    <strong>{user?.email}</strong>
                    {t("paymentSuccess.unverifiedMessageSuffix", uiLang)}
                  </>
                )
                : t("paymentSuccess.unverifiedMessagePrefix", uiLang)}
            </p>

            <p className="success-message" style={{ fontSize: '0.9rem', color: '#666' }}>
              {t("paymentSuccess.unverifiedNote", uiLang)}
            </p>

            <button
              className="signup-cta-button success-cta-btn"
              onClick={handleResendEmail}
              disabled={resendLoading}
            >
              {resendLoading ? t("paymentSuccess.sending", uiLang) : t("paymentSuccess.resendEmail", uiLang)}
            </button>

            {resendMessage && (
              <p className={`resend-message ${resendMessage.startsWith('Error') ? 'error' : 'success'}`}>
                {resendMessage}
              </p>
            )}

            <Link to="/" className="secondary-link" style={{ marginTop: '1rem' }}>
              {t("paymentSuccess.returnHomeToLogin", uiLang)}
            </Link>
          </>
        )}
      </div>
    </div>
  );
};

export default PaymentSuccess;

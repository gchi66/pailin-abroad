import React, { useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/EmailConfirmation.css";

const EmailConfirmationPage = ({ userEmail = "your email" }) => {
  // Prefer email from URL (e.g., /email-confirmation?email=foo@bar.com) or router state
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const emailFromParams = searchParams.get("email");
  const emailFromState = location.state?.email;
  const effectiveEmail = emailFromParams || emailFromState || userEmail;

  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const { ui } = useUiLang();

  const handleResendEmail = async () => {
    if (!effectiveEmail || effectiveEmail === "your email") {
      setResendMessage(t("authModals.emailConfirmation.noEmailError", ui));
      return;
    }

    setResendLoading(true);
    setResendMessage("");

    try {
      const { error } = await supabaseClient.auth.resend({
        type: "signup",
        email: effectiveEmail,
        options: {
          emailRedirectTo: `${window.location.origin}/onboarding`
        }
      });

      if (error) {
        setResendMessage(`Error: ${error.message}`);
      } else {
        setResendMessage(t("authModals.emailConfirmation.resendSuccess", ui));
      }
    } catch (err) {
      setResendMessage(t("authModals.emailConfirmation.resendFail", ui));
      console.error("Resend email error:", err);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <main className="email-confirmation-main">
      <div className="email-confirmation-container">
        <h1 className="email-confirmation-heading">{t("authModals.emailConfirmation.heading", ui)}</h1>

        <p className="email-confirmation-message">
          {t("authModals.emailConfirmation.messagePrefix", ui)}
          <strong>{effectiveEmail}</strong>
          {t("authModals.emailConfirmation.messageSuffix", ui)}
        </p>

        <p className="email-confirmation-instructions">
          {t("authModals.emailConfirmation.instructions", ui)}
        </p>

        <button
          className="submit-btn"
          onClick={handleResendEmail}
          disabled={resendLoading}
        >
          {resendLoading ? t("authModals.emailConfirmation.sending", ui) : t("authModals.emailConfirmation.resend", ui)}
        </button>

        {resendMessage && (
          <p className={`resend-message ${resendMessage.startsWith('Error') ? 'error' : 'success'}`}>
            {resendMessage}
          </p>
        )}
      </div>
    </main>
  );
};

export default EmailConfirmationPage;

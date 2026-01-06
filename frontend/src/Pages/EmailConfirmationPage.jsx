import React, { useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
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

  const handleResendEmail = async () => {
    if (!effectiveEmail || effectiveEmail === "your email") {
      setResendMessage("Error: No email found");
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
        setResendMessage("Verification email sent! Check your inbox.");
      }
    } catch (err) {
      setResendMessage("Failed to send email. Please try again.");
      console.error("Resend email error:", err);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <main className="email-confirmation-main">
      <div className="email-confirmation-container">
        <h1 className="email-confirmation-heading">You've got mail!</h1>

        <p className="email-confirmation-message">
          We just sent a message to you at <strong>{effectiveEmail}</strong>. Click the link inside to verify your email and complete your sign-up.
        </p>

        <p className="email-confirmation-instructions">
          If you don't receive the email within a few minutes, please check your spam or junk folder. Or, you can click the button below to resend it.
        </p>

        <button
          className="submit-btn"
          onClick={handleResendEmail}
          disabled={resendLoading}
        >
          {resendLoading ? "Sending..." : "RESEND EMAIL"}
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

import React from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import "../Styles/EmailConfirmation.css";

const EmailConfirmationPage = ({ userEmail = "your email" }) => {
  // Prefer email from URL (e.g., /email-confirmation?email=foo@bar.com) or router state
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const emailFromParams = searchParams.get("email");
  const emailFromState = location.state?.email;
  const effectiveEmail = emailFromParams || emailFromState || userEmail;

  const handleResendEmail = () => {
    // TODO: Implement resend email logic
    console.log("Resend email clicked for:", effectiveEmail);
    alert("Resend email functionality will be implemented.");
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
        >
          RESEND EMAIL
        </button>
      </div>
    </main>
  );
};

export default EmailConfirmationPage;

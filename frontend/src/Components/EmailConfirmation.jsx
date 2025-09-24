import React from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import "../Styles/EmailConfirmation.css";

const EmailConfirmation = () => {
  // Get email from URL params or location state
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Try to get email from multiple sources
  const email = searchParams.get('email') || location.state?.email || 'your email';

  const handleResendEmail = () => {
    console.log("Resend email clicked");
    // TODO: Implement resend email functionality
  };

  return (
    <div className="email-confirmation-main">
      <div className="email-confirmation-container">
        <h1 className="email-confirmation-heading">You've got mail!</h1>

        <p className="email-confirmation-message">
          We just sent a message to you at <strong>{email}</strong>.
        </p>

        <p className="email-confirmation-message">
          Click the link inside to verify your email and complete your sign-up.
        </p>

        <p className="email-confirmation-instructions">
          If you don't receive the email within a few minutes, please check your spam or junk folder.
          Or, you can click the button below to resend it.
        </p>

        <button
          className="submit-btn"
          onClick={handleResendEmail}
        >
          RESEND EMAIL
        </button>
      </div>
    </div>
  );
};

export default EmailConfirmation;

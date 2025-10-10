import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import "../Styles/PaymentSuccess.css";

const PaymentSuccess = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const { user } = useAuth();

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
      setResendMessage("Error: No email found");
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
        setResendMessage("Verification email sent! Check your inbox.");
      }
    } catch (err) {
      setResendMessage("Failed to send email. Please try again.");
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
            <h1 className="success-main-title">Payment Successful!</h1>
            <p className="success-subtitle">Welcome to Pailin Abroad Premium!</p>

            <p className="success-message">
              Your membership is now active. You now have full access to all lessons and features.
            </p>

            <Link to="/pathway" className="signup-cta-button success-cta-btn">
              Go to My Pathway
            </Link>

            <Link to="/" className="secondary-link">
              Return to Homepage
            </Link>
          </>
        ) : (
          // Unverified user - needs to verify email first
          <>
            <h1 className="success-main-title">Payment Received!</h1>
            <p className="success-subtitle">One More Step...</p>

            <p className="success-message">
              We've sent you a verification email. Please check your inbox and click the verification link to activate your account and access all lessons.
            </p>

            <p className="success-message" style={{ fontSize: '0.9rem', color: '#666' }}>
              Once verified, you can log in and start learning!
            </p>

            <button
              className="signup-cta-button success-cta-btn"
              onClick={handleResendEmail}
              disabled={resendLoading}
            >
              {resendLoading ? "Sending..." : "Resend Verification Email"}
            </button>

            {resendMessage && (
              <p className={`resend-message ${resendMessage.startsWith('Error') ? 'error' : 'success'}`}>
                {resendMessage}
              </p>
            )}

            <Link to="/" className="secondary-link" style={{ marginTop: '1rem' }}>
              Return to Homepage to Log In
            </Link>
          </>
        )}
      </div>
    </div>
  );
};

export default PaymentSuccess;

import React, { useState } from "react";
import axios from "axios";
import "../Styles/Modal.css";

const SignupModal = ({ isOpen, onClose, toggleLoginModal}) => {

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  if (!isOpen) return null;

  // Handle signup form submission
  const handleSignUp = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post("http://127.0.0.1:5000/api/signup", {
        email,
        password,
      });
      setSuccess(true);
      setError("");
      console.log("Sign Up Success:", response.data);
      alert("Sign-up successful! Please verify your email.");
    } catch (error) {
      console.error("Sign Up Error:", error);
      setError(error.response?.data?.error || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal">
      <div className="modal-content">
        <button className="modal-close" onClick={onClose}>
          &times;
        </button>
        {success ? (
          <div className="success-message">
            <h2>Sign-up Successful!</h2>
            <p>Please verify your email and return to this website to log in.</p>
          </div>
        ) : (
          <>
            <h2>Create your account</h2>
            <form onSubmit={handleSignUp}>
              <div className="form-group">
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              {error && <div className="error-message">{error}</div>}
              <div className="form-group">
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <div className="form-group">
                <input
                  type="password"
                  placeholder="Confirm Password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                />
              </div>
            <div className="divider">OR</div>
            <button className="social-button google">Sign up with Google</button>
            <button className="social-button facebook">Sign up with Facebook</button>
              <button
                type="submit"
                className="submit-btn"
                disabled={loading}
              >
                {loading ? "Signing Up..." : "Sign Up"}
              </button>
            </form>
            <p className="switch-text">
              Already a member?{" "}
              <span className="link" onClick={toggleLoginModal}>
                Sign in
              </span>
            </p>
          </>
        )}
      </div>
    </div>
  );
};

export default SignupModal;

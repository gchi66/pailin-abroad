import React, { useState } from "react";
import axios from "axios";
import "../Styles/SignUpPage.css"; // We'll add minimal CSS
import { API_BASE_URL } from "../config/api";

const SignUpPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  // Handle signup form submission
  const handleSignUp = async (e) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/signup`, {
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
    <div className="signup-container">
      {success ? (
        <div className="success-message">
          <h2>Sign-up Successful!</h2>
          <p>Please verify your email and return to this website to log in.</p>
        </div>
      ) : (
        <>
          <h2>Sign Up</h2>
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
            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? "Signing Up..." : "Sign Up"}
            </button>
          </form>
        </>
      )}
    </div>
  );
};

export default SignUpPage;

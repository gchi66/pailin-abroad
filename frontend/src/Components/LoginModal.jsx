import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import "../Styles/Modal.css";

const LoginModal = ({ isOpen, onClose, toggleSignupModal }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();

    // Basic validation
    if (!email || !password) {
      setError("Please enter both email and password.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const response = await axios.post(
        "http://127.0.0.1:5000/api/login",
        { email, password },
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const { access_token, refresh_token } = response.data.session;
      const { error: sessionError } = await supabaseClient.auth.setSession({
        access_token,
        refresh_token,
      });

      if (sessionError) {
        throw new Error("Failed to establish session");
      } else {
        console.log("Login successful!");
        onClose(); // Close modal on success
        navigate("/pathway"); // Navigate to pathway instead of profile
      }
    } catch (error) {
      console.error("Login Error:", error.response?.data || error.message);
      setError(error.response?.data?.error || error.message || "Login failed. Please try again.");
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
        <h2>Sign In</h2>
        <form onSubmit={handleLogin}>
          {error && <div className="error-message" style={{
            color: '#ff4444',
            backgroundColor: '#ffebee',
            padding: '10px',
            borderRadius: '5px',
            marginBottom: '15px',
            fontSize: '14px'
          }}>{error}</div>}

          <div className="form-group">
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#333' }}>
              Email
            </label>
            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="form-group">
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#333' }}>
              Password
            </label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="form-footer" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <input type="checkbox" /> Remember me
            </label>
            <a href="/" className="forgot-link">Forgot username/password?</a>
          </div>
          <button
            type="submit"
            className="submit-btn"
            disabled={loading}
            style={{ opacity: loading ? 0.6 : 1 }}
          >
            {loading ? "SIGNING IN..." : "SIGN IN"}
          </button>
        </form>
        <div className="divider">OR</div>
        <button className="social-button google">Sign in with Google</button>
        <button className="social-button facebook">Sign in with Facebook</button>

        {toggleSignupModal && (
          <p className="switch-text" style={{ marginTop: '20px', textAlign: 'center' }}>
            Don't have an account?{" "}
            <span className="link" onClick={() => {
              onClose(); // Close login modal
              toggleSignupModal(); // Open signup modal
            }}>
              Sign up
            </span>
          </p>
        )}
      </div>
    </div>
  );
};

export default LoginModal;

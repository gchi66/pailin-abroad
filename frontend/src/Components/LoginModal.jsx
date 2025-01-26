import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import "../Styles/Modal.css";

const LoginModal = ({ isOpen, onClose }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  if (!isOpen) return null;

  const handleLogin = async (e) => {
    e.preventDefault();
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
      const { error } = await supabaseClient.auth.setSession({
        access_token,
        refresh_token,
      });

      if (error) {
        console.error("Error setting session:", error.message);
      } else {
        console.log("Login successful!");
        onClose(); // Close modal on success
        navigate("/profile");

      }
    } catch (error) {
      console.error("Login Error:", error.response?.data || error.message);
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
          <div className="form-group">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="form-footer">
            <label>
              <input type="checkbox" /> Remember me
            </label>
            <a href="/" className="forgot-link">Forgot username/password?</a>
          </div>
          <button type="submit" className="submit-btn">
            Sign In
          </button>
        </form>
        <div className="divider">OR</div>
        <button className="social-button google">Sign in with Google</button>
        <button className="social-button facebook">Sign in with Facebook</button>
      </div>
    </div>
  );
};

export default LoginModal;

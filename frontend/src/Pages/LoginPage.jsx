import React, { useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import  supabaseClient  from "../supabaseClient"
import "../Styles/LoginPage.css";

const LoginPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  // Handle login form submission
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

      console.log("Login Success:", response.data);

    // Extract session data from the backend response
    const { access_token, refresh_token } = response.data.session;

    // Set the session in Supabase client
    const { data: session, error } = await supabaseClient.auth.setSession({
      access_token,
      refresh_token,
    });

    if (error) {
      console.error("Error setting session:", error.message);
    } else {
      console.log("Session updated in Supabase:", session);
    }

      // Redirect to home page
      navigate("/");
    } catch (error) {
      console.error("Login Error:", error.response?.data || error.message);
    }
  };

  return (
    <div className="login-container">
      <h2>Log In</h2>
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
        <button type="submit" className="submit-btn">Log In</button>
      </form>
    </div>
  );
};

export default LoginPage;

import React, { useState } from "react";
import axios from "axios";
import "../Styles/LoginPage.css"; // We'll add some minimal CSS

const LoginPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Handle login form submission
  const handleLogin = async (e) => {
    e.preventDefault(); // Prevent default form behavior
    try {
      const response = await axios.post("http://127.0.0.1:5000/api/login", {
        email,
        password,
      });
      console.log("Login Success:", response.data);
      // Redirect or handle successful login here
    } catch (error) {
      console.error("Login Error:", error);
      // Optionally, show an error message
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

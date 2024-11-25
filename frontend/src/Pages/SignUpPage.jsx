import React, { useState } from "react";
import axios from "axios";
import "../Styles/SignUpPage.css"; // We'll add minimal CSS

const SignUpPage = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Handle signup form submission
  const handleSignUp = async (e) => {
    e.preventDefault(); // Prevent default form behavior
    try {
      const response = await axios.post("http://127.0.0.1:5000/api/signup", {
        email,
        password,
      });
      console.log("Sign Up Success:", response.data);
      // Redirect or handle successful sign up here
    } catch (error) {
      console.error("Sign Up Error:", error);
      // Optionally, show an error message
    }
  };

  return (
    <div className="signup-container">
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
        <div className="form-group">
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <button type="submit" className="submit-btn">Sign Up</button>
      </form>
    </div>
  );
};

export default SignUpPage;

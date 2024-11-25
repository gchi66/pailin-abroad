import React from "react";
import { useNavigate } from "react-router-dom";

const AuthButtons = () => {
  const navigate = useNavigate();

  const handleSignup = () => {
    navigate("/signup");
  };

  const handleLogin = () => {
    navigate("/login");
  };

  return (
    <div className="auth-buttons">
      <button className="signup" onClick={handleSignup}>
        Sign Up
      </button>
      <button className="login" onClick={handleLogin}>
        Log In
      </button>
    </div>
  );
};

export default AuthButtons;

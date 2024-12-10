import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext"; // Import the useAuth hook
import  supabaseClient  from "../supabaseClient"; // Import the Supabase client

const AuthButtons = ({ onLogin, onSignup }) => {
  const { user } = useAuth(); // Access the user from the AuthContext
  console.log("AuthButtons user:", user);
  const navigate = useNavigate();

  // const handleSignup = () => {
  //   navigate("/signup");
  // };

  // const handleLogin = () => {
  //   navigate("/login");
  // };

  const handleLogout = async () => {
    try {
      await supabaseClient.auth.signOut(); // Log the user out via Supabase
      navigate("/"); // Redirect to the home page
    } catch (error) {
      console.error("Logout Error:", error.message);
    }
  };

  return (
    <div className="auth-buttons">
      {user ? (
        <button className="logout" onClick={handleLogout}>
          Log Out
        </button>
      ) : (
        <>
          <button className="signup" onClick={onSignup}>
            Sign Up
          </button>
          <button className="login" onClick={onLogin}>
            Log In
          </button>
        </>
      )}
    </div>
  );
};

export default AuthButtons;

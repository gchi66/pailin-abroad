import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

const AuthButtons = ({ onLogin, onSignup }) => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { ui } = useUiLang();

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
          {t("authButtons.logout", ui)}
        </button>
      ) : (
        <>
          <button className="join-button" onClick={onSignup}>
            {t("authButtons.signUp", ui)}
          </button>
          <button className="signin-button" onClick={onLogin}>
            {t("authButtons.signIn", ui)}
          </button>
        </>
      )}
    </div>
  );
};

export default AuthButtons;

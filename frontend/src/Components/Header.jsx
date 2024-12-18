import React, { useState } from "react";
import "../Styles/Header.css";
import LanguageToggle from "./LanguageToggle";
import SearchBar from "./SearchBar";
import AuthButtons from "./AuthButtons";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";

const Header = ({ toggleLoginModal, toggleSignupModal }) => {
  const [language, setLanguage] = useState("EN");
  const { user } = useAuth();

  return (
    <header>
      <div className="top-bar">
        <div className="social-icons">
          {/* Social icons here */}
        </div>
        <div className="logo">
          <NavLink to="/"><img src="/images/logo.png" alt="Logo" /></NavLink>
        </div>
      </div>
      <nav className="menu-buttons">
        <ul className="menu">
          <li><NavLink to="/">HOME</NavLink></li>
          <li><NavLink to="/about">ABOUT</NavLink></li>
          <li><NavLink to="/lessons">LESSONS</NavLink></li>
          <li><NavLink to="/glossary">GLOSSARY</NavLink></li>
          <li><NavLink to="/contact">CONTACT</NavLink></li>
          {/* Display PROFILE link if the user is logged in */}
          {user && <li><NavLink to="/profile">PROFILE</NavLink></li>}
        </ul>
      </nav>
      <div className="right-side">
        <LanguageToggle language={language} setLanguage={setLanguage} />
        <SearchBar />
        <AuthButtons onLogin={toggleLoginModal} onSignup={toggleSignupModal} />
      </div>
    </header>
  );
};

export default Header;

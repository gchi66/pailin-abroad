import React, { useState } from "react";
import "../Styles/Navbar.css";
import LanguageToggle from "./LanguageToggle";
import SearchBar from "./SearchBar";
import AuthButtons from "./AuthButtons";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";

const Navbar = ({ toggleLoginModal, toggleSignupModal }) => {
  const [language, setLanguage] = useState("EN");
  const { user } = useAuth();

  return (
    <header className="navbar">
      {/* Logo */}
      <div className="logo">
        <NavLink to="/">
          <img src="/images/full-logo.webp" alt="Pailin Abroad Logo" />
        </NavLink>
      </div>

      {/* Navigation Links */}
      <nav className="menu">
        <ul>
          <li>
            <NavLink to="/">HOME</NavLink>
          </li>
          <li>
            <NavLink to="/about">ABOUT</NavLink>
          </li>
          <li>
            <NavLink to="/lessons">LESSONS</NavLink>
          </li>
          <li>
            <NavLink to="/glossary">RESOURCES</NavLink>
          </li>
          <li>
            <NavLink to="/contact">CONTACT</NavLink>
          </li>
          <li className="pricing">
            <NavLink to="/membership">PRICING</NavLink>
          </li>
        </ul>
      </nav>

      {/* Right Side (Language Toggle, Search Bar, Auth Buttons) */}
      <div className="right-side">
        <LanguageToggle language={language} setLanguage={setLanguage} />
        <SearchBar />
        <AuthButtons onLogin={toggleLoginModal} onSignup={toggleSignupModal} />
      </div>
    </header>
  );
};

export default Navbar;

import React, { useState } from "react";
import "../Styles/Header.css";
import LanguageToggle from "./LanguageToggle";
import SearchBar from "./SearchBar";
import AuthButtons from "./AuthButtons";

const Header = () => {
  const [language, setLanguage] = useState("EN");

  return (
    <header>
      <div className="top-bar">
        <div className="social-icons">
          {/* Social icons here */}
        </div>
        <div className="logo">
          <a href="#home"><img src="/images/logo.png" alt="Logo" /></a>
        </div>
      </div>
      <nav className="menu-buttons">
        <ul className="menu">
          <li><a href="#home">HOME</a></li>
          <li><a href="#about">ABOUT</a></li>
          <li><a href="#lessons">LESSONS</a></li>
          <li><a href="#glossary">GLOSSARY</a></li>
          <li><a href="#contact">CONTACT</a></li>
        </ul>
      </nav>
      <div className="right-side">
        <LanguageToggle language={language} setLanguage={setLanguage} />
        <SearchBar />
        <AuthButtons />
      </div>
    </header>
  );
};

export default Header;

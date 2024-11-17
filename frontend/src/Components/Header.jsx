import React from "react";
import "../Styles/Header.css";

const Header = () => {
  const [language, setLanguage] = React.useState("EN");
  return (
    <header>
      <div className="top-bar">
        {/* <div className="social-icons">
          <img src="/instagram.png" alt="Instagram" />
          <img src="/facebook.png" alt="Facebook" />
          <img src="/youtube.png" alt="YouTube" />
          <img src="/tiktok.png" alt="TikTok" />
        </div> */}
        <div className="logo">
          <a href="#home"><img src="/logo.png" alt="Logo" /></a>
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
        <div className="language-toggle">
            <span
              className={language === "TH" ? "active" : ""}
              onClick={() => setLanguage("TH")}
            >
              TH
            </span>
            <span>|</span>
            <span
              className={language === "EN" ? "active" : ""}
              onClick={() => setLanguage("EN")}
            >
              EN
            </span>
        </div>
        <div className="search-bar">
            <input type="text" placeholder="" />
            <button className="search-icon">
              <img src="/glass.png" alt="Search" />
            </button>
        </div>
        <div className="auth-buttons">
          <button className="signup">Sign Up</button>
          <button className="login">Log In</button>
        </div>
      </div>
    </header>
  );
};

export default Header;

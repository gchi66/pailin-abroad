import React from "react";
import "../Styles/Header.css";

const Header = () => {
  return (
    <header>
      <div className="top-bar">
        <div className="social-icons">
          <img src="/instagram.png" alt="Instagram" />
          <img src="/facebook.png" alt="Facebook" />
          <img src="/youtube.png" alt="YouTube" />
        </div>
        <div className="search-bar">
          <input type="text" placeholder="Search..." />
        </div>
      </div>
      <nav>
        <div className="logo">
          <h1>Pailin Abroad</h1>
        </div>
        <ul className="menu">
          <li><a href="#home">Home</a></li>
          <li><a href="#about">About</a></li>
          <li><a href="#lessons">Lessons</a></li>
          <li><a href="#glossary">Glossary</a></li>
          <li><a href="#contact">Contact</a></li>
        </ul>
        <div className="user-actions">
          <button className="membership">Membership</button>
          <button>Sign Up</button>
          <button>Log In</button>
        </div>
      </nav>
    </header>
  );
};

export default Header;

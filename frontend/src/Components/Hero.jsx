import React from "react";
import "../Styles/Hero.css";
// import ProfileImage from "/images/Pailin-no-bg.png"; // Ensure this path is correct

const Hero = ({ onSignupClick }) => {
  return (
    <section className="hero">
      <div className="hero-card">
        <img src="/images/characters/pailin-blue-right.png" alt="Pailin" className="hero-img" />
        <div className="hero-content">
          <div className="title-container">
            <h2>
              English learning for Thai speakers
            </h2>
          </div>
          <p className="hero-subheader">Lessons based on audio conversations to teach useful, conversational, english.</p>
          <div className="hero-buttons">
            <button className="free-lessons" onClick={onSignupClick}>SIGN UP FOR FREE</button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;

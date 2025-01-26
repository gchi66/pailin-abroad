import React from "react";
import "../Styles/Hero.css";
// import ProfileImage from "/images/Pailin-no-bg.png"; // Ensure this path is correct

const Hero = () => {
  return (
    <section className="hero">
      <div className="hero-card">
        <div className="hero-content">
          <div className="title-container">
            <h2>
              PAILIN ABROAD
            </h2>
            <svg className="underline" viewBox="0 0 150 30" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5 20 Q75 12, 145 20" stroke="#FF4545" stroke-width="3" fill="none" stroke-linecap="round"/>
            </svg>
          </div>
          <p>Effective English learning for Thai speakers</p>
          <div className="hero-buttons">
            <button className="join">JOIN</button>
            <button className="free-lessons">FREE LESSONS</button>
          </div>
        </div>
        <div className="hero-image">
          <div className="profile-circle">
          <img src="/images/Pailin-no-bg.png" alt="Pailin" className="profile-pic" />
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;

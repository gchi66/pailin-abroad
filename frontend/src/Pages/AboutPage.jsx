import React from "react";
import "../Styles/AboutPage.css";

const AboutPage = () => {
  return (
    <div className="about-page-container">
      {/* page header */}
      <header className="about-page-header">
        <h1 className="about-page-header-text">ABOUT PAILIN ABROAD</h1>
        <img src="/images/about-us-pailin-and-luke.webp" alt="Pailin and Luke" className="about-header-image" />
      </header>
    </div>
  );
};

export default AboutPage;

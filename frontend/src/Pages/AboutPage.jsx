import React, { useState } from "react";
import "../Styles/AboutPage.css";
import AboutMethod from "../Components/AboutMethod";
import Team from "../Components/Team";

const AboutPage = () => {
  const [selectedSection, setSelectedSection] = useState("The Method");

  return (
    <div className="about-page-container">
      {/* Page header */}
      <header className="about-page-header">
        <h1 className="about-page-header-text">ABOUT PAILIN ABROAD</h1>
        <img
          src="/images/about-us-pailin-and-luke.webp"
          alt="Pailin and Luke"
          className="about-header-image"
        />
      </header>

      {/* Section navigation */}
      <div className="section-btns-container">
        <button
          className={`section-btn ${selectedSection === "The Method" ? "active" : ""}`}
          onClick={() => setSelectedSection("The Method")}
        >
          THE METHOD
        </button>
        <button
          className={`section-btn ${selectedSection === "Our Team" ? "active" : ""}`}
          onClick={() => setSelectedSection("Our Team")}
        >
          OUR TEAM
        </button>
        <button
          className={`section-btn ${selectedSection === "The Story" ? "active" : ""}`}
          onClick={() => setSelectedSection("The Story")}
        >
          THE STORY
        </button>
      </div>
      <div className={`about-method-section ${selectedSection === "The Method" ? "visible" : ""}`}>
        <AboutMethod />
      </div>
      <div className={`about-method-section ${selectedSection === "Our Team" ? "visible" : ""}`}>
        <Team />
      </div>

    </div> /* page container */
  );
};

export default AboutPage;

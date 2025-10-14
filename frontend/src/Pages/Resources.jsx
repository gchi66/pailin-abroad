import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "../Styles/Resources.css";

const Resources = () => {
  const [activeSection, setActiveSection] = useState(null);
  const navigate = useNavigate();

  const sections = [
    "EXERCISE BANK",
    "PHRASES & VERBS",
    "COMMON MISTAKES",
    "CULTURE NOTES",
    "TOPIC LIBRARY"
  ];

  const handleSectionClick = (section, index) => {
    if (section === "TOPIC LIBRARY") {
      navigate("/topic-library");
    } else {
      setActiveSection(index);
    }
  };

  return (
    <div className="resources-page-container">
      {/* page header */}
      <header className="resources-page-header">
        <h1 className="resources-page-header-text">RESOURCES</h1>
        <p className="resources-page-header-subtitle">Explore grammar, phrases, culture notes, and more</p>
      </header>

      {/* section buttons */}
      <div className="resources-sections">
        {sections.map((section, index) => (
          <button
            key={index}
            className={`section-btn ${activeSection === index ? 'active' : ''}`}
            onClick={() => handleSectionClick(section, index)}
          >
            {section}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Resources;

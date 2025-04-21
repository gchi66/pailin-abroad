import React, { useState } from "react";
import "../Styles/Resources.css";

const Resources = () => {
  const [activeSection, setActiveSection] = useState(null);

  const sections = [
    "GRAMMAR PRACTICE",
    "PHRASES & VERBS",
    "COMMON MISTAKES",
    "CULTURE NOTES",
    "REFERENCES"
  ];

  return (
    <div className="resources-page-container">
      {/* page header */}
      <header className="resources-page-header">
        <h1 className="resources-page-header-text">RESOURCES</h1>
        <img src="/images/characters/pailin-blue-right.png" alt="Pailin" className="resources-header-image" />
      </header>

      {/* section buttons */}
      <div className="resources-sections">
        {sections.map((section, index) => (
          <button
            key={index}
            className={`section-btn ${activeSection === index ? 'active' : ''}`}
            onClick={() => setActiveSection(index)}
          >
            {section}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Resources;

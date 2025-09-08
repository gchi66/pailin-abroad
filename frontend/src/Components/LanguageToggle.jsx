import React from "react";
import "../Styles/LanguageToggle.css";

const LanguageToggle = ({
  language,
  setLanguage,
  label,
  showLabel = false,
}) => {
  const handleLanguageChange = (newLanguage) => {
    console.log("Language toggle clicked:", newLanguage, "current:", language);
    setLanguage(newLanguage);
  };

  return (
    <div className="language-toggle">
      {showLabel && label && <span className="language-label">{label}</span>}
      <span
        className={language === "th" ? "active" : ""}
        onClick={() => handleLanguageChange("th")}
      >
        TH
      </span>
      <span>|</span>
      <span
        className={language === "en" ? "active" : ""}
        onClick={() => handleLanguageChange("en")}
      >
        EN
      </span>
    </div>
  );
};

export default LanguageToggle;

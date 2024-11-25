import React from "react";

const LanguageToggle = ({ language, setLanguage }) => {
  return (
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
  );
};

export default LanguageToggle;

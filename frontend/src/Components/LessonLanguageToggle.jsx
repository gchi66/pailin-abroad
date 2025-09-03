import React from "react";

// Button-based language toggle for lesson content
const LessonLanguageToggle = ({ language, setLanguage }) => {
  // If language is 'EN', show 'Translate to Thai' in English
  // If language is 'TH', show 'แปลเป็นภาษาอังกฤษ' (Translate to English) in Thai
  const isEnglish = language === "EN";
  const buttonText = isEnglish ? "Translate to Thai" : "แปลเป็นภาษาอังกฤษ";
  const nextLang = isEnglish ? "TH" : "EN";
  return (
    <button
      className="language-toggle-btn"
      type="button"
      onClick={() => setLanguage(nextLang)}
    >
      {buttonText}
    </button>
  );
};

export default LessonLanguageToggle;

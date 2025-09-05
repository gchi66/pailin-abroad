import React from "react";

// Button-based language toggle for lesson content language
const LessonLanguageToggle = ({ contentLang, setContentLang }) => {
  // If contentLang is 'en', show 'Translate to Thai' in English
  // If contentLang is 'th', show 'แปลเป็นภาษาอังกฤษ' (Translate to English) in Thai
  const isEnglish = contentLang === "en";
  const buttonText = isEnglish ? "แปลเป็นภาษาไทย" : "Translate to English";
  const nextLang = isEnglish ? "th" : "en";
  return (
    <button
      className="language-toggle-btn"
      type="button"
      onClick={() => setContentLang(nextLang)}
    >
      {buttonText}
    </button>
  );
};

export default LessonLanguageToggle;

import React from "react";

// Button-based language toggle for lesson content language
const LessonLanguageToggle = ({
  contentLang,
  setContentLang,
  className = "",
  disabled = false,
}) => {
  // If contentLang is 'en', show 'Translate to Thai' in English
  // If contentLang is 'th', show 'แปลเป็นภาษาอังกฤษ' (Translate to English) in Thai
  const isEnglish = contentLang === "en";
  const buttonText = isEnglish ? "แปลเป็นภาษาไทย" : "Translate to English";
  const nextLang = isEnglish ? "th" : "en";
  const classes = ["language-toggle-btn"];
  if (className) classes.push(className);
  if (disabled) classes.push("language-toggle-btn--disabled");

  const handleClick = () => {
    if (disabled) return;
    if (typeof setContentLang === "function") {
      setContentLang(nextLang);
    }
  };

  return (
    <button
      className={classes.join(" ")}
      type="button"
      onClick={handleClick}
      disabled={disabled}
      tabIndex={disabled ? -1 : 0}
    >
      {buttonText}
    </button>
  );
};

export default LessonLanguageToggle;

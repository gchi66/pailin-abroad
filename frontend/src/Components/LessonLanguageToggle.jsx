import React from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

// Button-based language toggle for lesson content language
const LessonLanguageToggle = ({
  contentLang,
  setContentLang,
  className = "",
  disabled = false,
}) => {
  const { ui: uiLang } = useUiLang();
  const isEnglish = contentLang === "en";
  const buttonText = isEnglish
    ? t("lessonToggle.toThai", uiLang)
    : t("lessonToggle.toEnglish", uiLang);
  const ariaLabel = isEnglish
    ? t("lessonToggle.toThaiContent", uiLang)
    : t("lessonToggle.toEnglishContent", uiLang);
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
      aria-label={ariaLabel}
    >
      {buttonText}
    </button>
  );
};

export default LessonLanguageToggle;

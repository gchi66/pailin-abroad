import React from "react";
import "../Styles/Method.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Method = () => {
  const { ui } = useUiLang();
  const methodCopy = copy.home.method;

  return (
    <section className="method-section">
      <div className="method-card">
        <div className="method-box">
          <h2 className="method-title">{pick(methodCopy.title, ui)}</h2>
          <p className="method-text">
            {pick(methodCopy.body, ui)}
          </p>
        </div>
      </div>
      <div className="graphic-container">
        <img
          src="/images/method-speech-bubbles.webp"
          alt="Speech Bubbles"
          className="dialogue-bubbles"
        />
      </div>
    </section>
  );
};

export default Method;

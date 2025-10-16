import React from "react";
import "../Styles/ChooseUs.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const ChooseUs = () => {
  const { ui } = useUiLang();
  const chooseCopy = copy.home.chooseUs;
  const reasons = chooseCopy.reasons || [];

  return (
    <section className="choose-us">
      <div className="choose-us-card">
        <div className="choose-us-content">
          <h2>{pick(chooseCopy.title, ui)}</h2>
          <ul className="reasons-list">
            {reasons.map((reason, index) => (
              <li key={index} className="reason-item">
                <img
                  src="/images/filled-checkmark-lesson-complete.webp"
                  alt="checkmark"
                  className="checkmark-icon"
                />
                <span>{pick(reason.text, ui)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default ChooseUs;

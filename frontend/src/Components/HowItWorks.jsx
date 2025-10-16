import React from "react";
import "../Styles/HowItWorks.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const HowItWorks = () => {
  const { ui } = useUiLang();
  const hiw = copy.home.howItWorks;
  const steps = hiw.steps || [];

  return (
    <section className="how-it-works">
      <h2 className="how-it-works-title">{pick(hiw.title, ui)}</h2>
      <div className="how-it-works-cards">
        {steps.map((step, index) => (
          <div key={index} className="hiw-card">
            <img
              src={`/images/number-${step.number}.png`}
              alt={`Step ${step.number}`}
              className="hiw-number"
            />
            <h3 className="hiw-header">{pick(step.header, ui)}</h3>
            <p className="hiw-text">{pick(step.text, ui)}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default HowItWorks;

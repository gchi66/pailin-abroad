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
              src={`/images/how_it_works_${index + 1}.png`}
              alt={`How it works step ${index + 1}`}
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

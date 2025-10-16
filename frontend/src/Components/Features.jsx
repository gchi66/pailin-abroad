import React from "react";
import "../Styles/Features.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const featureIcons = [
  <img src="/images/headphones.webp" alt="Audio icon" />,
  <img src="/images/globe.webp" alt="Globe icon" />,
  <img src="images/everyday-english.webp" alt="Everyday English" />,
];

const Features = () => {
  const { ui } = useUiLang();
  const featureCopy = copy.home.features.items || [];

  return (
    <section className="features-section">
      <div className="features-container">
        {featureCopy.map((feature, index) => (
          <div key={index} className="feature-item">
            <div className="feature-icon">{featureIcons[index]}</div>
            <p className="feature-text">{pick(feature.title, ui)}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Features;

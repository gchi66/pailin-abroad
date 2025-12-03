import React from "react";
import "../Styles/Hero.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Hero = ({ onSignupClick }) => {
  const { ui } = useUiLang();
  const heroCopy = copy.home.hero;

  return (
    <section className="hero">
      <div className="hero-card">
        <img src="/images/characters/hero_audio_bar.webp" alt="Pailin hero audio bar" className="hero-img" />
        <div className="hero-content">
          <div className="title-container">
            <h2>
              {pick(heroCopy.title, ui)}
            </h2>
          </div>
          <p className="hero-subheader">{pick(heroCopy.subtitle, ui)}</p>
          <div className="hero-buttons">
            <button className="free-lessons" onClick={onSignupClick}>{pick(heroCopy.cta, ui)}</button>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;

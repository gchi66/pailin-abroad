import React from "react";
import "../Styles/TakeTheLeapCTA.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const TakeTheLeapCTA = ({ onSignupClick }) => {
  const { ui } = useUiLang();
  const leapCopy = copy.home.takeTheLeap;

  return (
    <section className="take-the-leap-cta">
      <h2 className="take-the-leap-cta-title">
        {pick(leapCopy.title, ui)}
      </h2>
      <button className="take-the-leap-cta-button" onClick={onSignupClick}>
        {pick(leapCopy.cta, ui)}
      </button>
    </section>
  );
};

export default TakeTheLeapCTA;

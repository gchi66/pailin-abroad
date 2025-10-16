import React from "react";
import "../Styles/SignUpCTA.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const SignUpCTA = ({ onSignupClick }) => {
  const { ui } = useUiLang();
  const ctaCopy = copy.home.signUpCTA;
  const parts = ctaCopy.titleParts;
  const before = pick(parts.beforeEm, ui);
  const emphasis = pick(parts.emphasis, ui);
  const after = pick(parts.afterEm, ui);
  const spacer = ui === "th" ? "" : " ";

  return (
    <section className="signup-cta">
      <h2 className="signup-cta-title">
        {before}
        {before && emphasis ? spacer : ""}
        <em>{emphasis}</em>
        {emphasis && after ? spacer : ""}
        {after}
      </h2>
      <button className="signup-cta-button" onClick={onSignupClick}>
        {pick(ctaCopy.cta, ui)}
      </button>
    </section>
  );
};

export default SignUpCTA;

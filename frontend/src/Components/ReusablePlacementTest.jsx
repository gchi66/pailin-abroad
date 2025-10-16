import React from "react";
import "../Styles/ReusablePlacementTest.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const ReusablePlacementTest = () => {
  const { ui } = useUiLang();
  const placement = copy.home.placement;

  return (
    <section className="placement-cta">
      <h2 className="placement-title">{pick(placement.title, ui)}</h2>
      <button className="placement-button">{pick(placement.cta, ui)}</button>
    </section>
  );
};

export default ReusablePlacementTest;

import React from "react";
import LegalPage from "../Components/LegalPage";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Terms = () => {
  const { ui } = useUiLang();
  const title = pick(copy.legal.termsTitle, ui);
  return <LegalPage title={title} slug="terms" />;
};

export default Terms;

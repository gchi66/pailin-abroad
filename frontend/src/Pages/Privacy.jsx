import React from "react";
import LegalPage from "../Components/LegalPage";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Privacy = () => {
  const { ui } = useUiLang();
  const title = pick(copy.legal.privacyTitle, ui);
  return <LegalPage title={title} slug="privacy" />;
};

export default Privacy;

import React from "react";
import LegalPage from "../Components/LegalPage";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const DeleteAccount = () => {
  const { ui } = useUiLang();
  const title = pick(copy.legal.deleteAccountTitle, ui);

  return <LegalPage title={title} slug="delete-account" />;
};

export default DeleteAccount;

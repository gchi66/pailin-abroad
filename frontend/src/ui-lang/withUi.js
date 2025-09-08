import { useLocation } from "react-router-dom";
import { useUiLang } from "./UiLangContext";

export function useWithUi() {
  const location = useLocation();
  const { ui } = useUiLang();

  return (to, overrides = {}) => {
    const sp = new URLSearchParams(location.search);
    // keep current ui unless an override provides one
    sp.set("ui", overrides.ui || ui);

    if (typeof to === "string") {
      return { pathname: to, search: `?${sp.toString()}` };
    }
    // support object-style "to"
    return { ...to, search: `?${sp.toString()}` };
  };
}

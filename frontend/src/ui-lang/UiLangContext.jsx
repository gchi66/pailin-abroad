import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

const UiLangContext = createContext({ ui: "en", setUi: () => {} });

export function UiLangProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();

  // Pull from URL (?ui=th), else localStorage, else 'en'
  const search = new URLSearchParams(location.search);
  const urlUi = (search.get("ui") || "").toLowerCase();
  const [ui, setUiState] = useState(() => {
    const stored = (localStorage.getItem("ui") || "").toLowerCase();
    if (urlUi === "th" || urlUi === "en") return urlUi;
    if (stored === "th" || stored === "en") return stored;
    return "en";
  });

  // Keep URL & localStorage in sync when ui changes
  const setUi = (next) => {
    const normalized = next === "th" ? "th" : "en";
    setUiState(normalized);
    localStorage.setItem("ui", normalized);

    const sp = new URLSearchParams(location.search);
    sp.set("ui", normalized);
    navigate({ pathname: location.pathname, search: `?${sp.toString()}` }, { replace: true });
  };

  // If user manually edits URL, reflect that in state
  useEffect(() => {
    if (urlUi && urlUi !== ui) setUiState(urlUi === "th" ? "th" : "en");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlUi]);

  const value = useMemo(() => ({ ui, setUi }), [ui]);
  return <UiLangContext.Provider value={value}>{children}</UiLangContext.Provider>;
}

export const useUiLang = () => useContext(UiLangContext);

import React, { createContext, useContext, useEffect, useMemo, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";

const UiLangContext = createContext({ ui: "en", setUi: () => {} });

export function UiLangProvider({ children }) {
  const [searchParams, setSearchParams] = useSearchParams();

  // read from URL (?ui=th) OR localStorage OR default 'en'
  const urlUi = (searchParams.get("ui") || "").toLowerCase();
  const [ui, setUiState] = useState(() => {
    if (urlUi === "th" || urlUi === "en") return urlUi;
    const stored = (localStorage.getItem("ui") || "").toLowerCase();
    if (stored === "th" || stored === "en") return stored;
    return "th";
  });

  // if user manually edits URL (?ui=th), reflect that in state
  useEffect(() => {
    if (urlUi && urlUi !== ui) setUiState(urlUi === "th" ? "th" : "en");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlUi]);

  const setUi = useCallback((next) => {
    const normalized = next === "th" ? "th" : "en";
    if (normalized === ui) return;               // no-op if same
    setUiState(normalized);
    localStorage.setItem("ui", normalized);

    // 🔒 Update ONLY the query param, keep the same page, other params, and hash
    const nextParams = new URLSearchParams(searchParams);
    nextParams.set("ui", normalized);
    setSearchParams(nextParams, { replace: true }); // no push, no route change
    // NOTE: react-router keeps pathname and hash as-is when you only change search
    // via setSearchParams.
  }, [ui, searchParams, setSearchParams]);

  const value = useMemo(() => ({ ui, setUi }), [ui, setUi]);
  return <UiLangContext.Provider value={value}>{children}</UiLangContext.Provider>;
};

export const useUiLang = () => useContext(UiLangContext);

import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

const StickyLessonToggleContext = createContext({
  registerLessonToggle: () => {},
  unregisterLessonToggle: () => {},
  updateContentLang: () => {},
  setShowStickyToggle: () => {},
  showStickyToggle: false,
  contentLang: "en",
  setContentLang: null,
  isRegistered: false,
});

const createInitialState = () => ({
  registered: false,
  contentLang: "en",
  setContentLang: null,
  show: false,
});

export const StickyLessonToggleProvider = ({ children }) => {
  const [state, setState] = useState(createInitialState);

  const registerLessonToggle = useCallback(({ contentLang, setContentLang }) => {
    setState((prev) => ({
      ...prev,
      registered: true,
      contentLang: contentLang === "th" ? "th" : "en",
      setContentLang: typeof setContentLang === "function" ? setContentLang : null,
    }));
  }, []);

  const unregisterLessonToggle = useCallback(() => {
    setState(createInitialState());
  }, []);

  const updateContentLang = useCallback((lang) => {
    setState((prev) => ({
      ...prev,
      contentLang: lang === "th" ? "th" : "en",
    }));
  }, []);

  const setShowStickyToggle = useCallback((show) => {
    setState((prev) => ({
      ...prev,
      show: Boolean(show),
    }));
  }, []);

  const value = useMemo(() => ({
    registerLessonToggle,
    unregisterLessonToggle,
    updateContentLang,
    setShowStickyToggle,
    showStickyToggle: state.registered && state.show,
    contentLang: state.contentLang,
    setContentLang: state.setContentLang,
    isRegistered: state.registered,
  }), [
    registerLessonToggle,
    unregisterLessonToggle,
    updateContentLang,
    setShowStickyToggle,
    state.registered,
    state.show,
    state.contentLang,
    state.setContentLang,
  ]);

  return (
    <StickyLessonToggleContext.Provider value={value}>
      {children}
    </StickyLessonToggleContext.Provider>
  );
};

export const useStickyLessonToggle = () => useContext(StickyLessonToggleContext);

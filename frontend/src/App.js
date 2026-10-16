import React from "react";
import { BrowserRouter as Router, Navigate, Route, Routes } from "react-router-dom";
import "./Styles/App.css";
import Analytics from "./Components/Analytics";
import ScrollToTop from "./Components/ScrollToTop";
import AuthCallback from "./Pages/AuthCallback";
import Contact from "./Pages/Contact";
import DeleteAccount from "./Pages/DeleteAccount";
import Download from "./Pages/Download";
import Privacy from "./Pages/Privacy";
import SurveyRedirect from "./Pages/SurveyRedirect";
import Terms from "./Pages/Terms";
import { UiLangProvider } from "./ui-lang/UiLangContext";

function App() {
  return (
    <Router>
      <UiLangProvider>
        <ScrollToTop />
        <Analytics />
        <Routes>
          {/* Mobile authentication bridge. The browser must not consume its credentials. */}
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Public app handoff, support, and compliance pages. */}
          <Route path="/download" element={<Download />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/terms" element={<Terms />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/delete-account" element={<DeleteAccount />} />
          <Route path="/survey" element={<SurveyRedirect />} />

          {/* The legacy website remains in source but is no longer publicly routed. */}
          <Route path="*" element={<Navigate to="/download" replace />} />
        </Routes>
      </UiLangProvider>
    </Router>
  );
}

export default App;

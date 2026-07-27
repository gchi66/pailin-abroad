import React from "react";
import ReactDOM from "react-dom/client";
import "./Styles/index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import posthog from "posthog-js";
import { PostHogProvider, PostHogErrorBoundary } from "@posthog/react";

const POSTHOG_KEY = process.env.REACT_APP_PUBLIC_POSTHOG_KEY;
const POSTHOG_HOST = process.env.REACT_APP_PUBLIC_POSTHOG_HOST;

if (POSTHOG_KEY && POSTHOG_HOST) {
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    defaults: "2026-01-30",
  });
} else if (process.env.NODE_ENV !== "production") {
  console.error(
    "REACT_APP_PUBLIC_POSTHOG_KEY or REACT_APP_PUBLIC_POSTHOG_HOST variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once these variables are configured"
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <PostHogProvider client={posthog}>
      <PostHogErrorBoundary>
        <App />
      </PostHogErrorBoundary>
    </PostHogProvider>
  </React.StrictMode>
);

reportWebVitals();

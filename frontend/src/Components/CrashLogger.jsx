import { useEffect } from "react";
import { useLocation } from "react-router-dom";

const CRASH_LOG_KEY = "debug_last_crash";
const MAX_STACK = 2000;

const CrashLogger = () => {
  const location = useLocation();

  useEffect(() => {
    const handleError = (event) => {
      try {
        const payload = {
          type: "error",
          message: event?.message || "Unknown error",
          stack: (event?.error?.stack || "").slice(0, MAX_STACK),
          url: window.location.href,
          path: location.pathname,
          ts: new Date().toISOString()
        };
        localStorage.setItem(CRASH_LOG_KEY, JSON.stringify(payload));
      } catch (err) {
        // Ignore storage failures
      }
    };

    const handleRejection = (event) => {
      try {
        const reason = event?.reason;
        const payload = {
          type: "rejection",
          message: reason?.message || String(reason || "Unhandled rejection"),
          stack: (reason?.stack || "").slice(0, MAX_STACK),
          url: window.location.href,
          path: location.pathname,
          ts: new Date().toISOString()
        };
        localStorage.setItem(CRASH_LOG_KEY, JSON.stringify(payload));
      } catch (err) {
        // Ignore storage failures
      }
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
    };
  }, [location.pathname]);

  useEffect(() => {
    let stored;
    try {
      stored = localStorage.getItem(CRASH_LOG_KEY);
    } catch (err) {
      return;
    }

    if (!stored) return;

    let parsed;
    try {
      parsed = JSON.parse(stored);
    } catch (err) {
      return;
    }

    if (!parsed?.message) return;

    // Small on-screen banner on next load
    const banner = document.createElement("div");
    banner.style.position = "fixed";
    banner.style.left = "12px";
    banner.style.right = "12px";
    banner.style.bottom = "12px";
    banner.style.zIndex = "99999";
    banner.style.background = "rgba(0,0,0,0.9)";
    banner.style.color = "#fff";
    banner.style.padding = "10px 12px";
    banner.style.borderRadius = "8px";
    banner.style.fontSize = "12px";
    banner.style.fontFamily = "Menlo, Consolas, monospace";
    banner.style.whiteSpace = "pre-wrap";
    banner.textContent =
      `Previous crash captured (${parsed.type}).\n` +
      `${parsed.message}\n` +
      `${parsed.stack ? parsed.stack : ""}`;

    const close = document.createElement("button");
    close.textContent = "×";
    close.style.position = "absolute";
    close.style.top = "6px";
    close.style.right = "10px";
    close.style.background = "transparent";
    close.style.border = "none";
    close.style.color = "#fff";
    close.style.fontSize = "16px";
    close.style.cursor = "pointer";
    close.addEventListener("click", () => {
      banner.remove();
    });

    banner.style.position = "fixed";
    banner.appendChild(close);
    document.body.appendChild(banner);

    try {
      localStorage.removeItem(CRASH_LOG_KEY);
    } catch (err) {
      // Ignore storage failures
    }
  }, []);

  return null;
};

export default CrashLogger;

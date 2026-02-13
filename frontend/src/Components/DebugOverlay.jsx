import React, { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";

const MAX_ERRORS = 5;

const DebugOverlay = () => {
  const location = useLocation();
  const [errors, setErrors] = useState([]);

  const debugEnabled = useMemo(() => {
    const params = new URLSearchParams(location.search || "");
    return params.get("debug") === "1";
  }, [location.search]);

  useEffect(() => {
    if (!debugEnabled) return;

    const addError = (entry) => {
      setErrors((prev) => [entry, ...prev].slice(0, MAX_ERRORS));
    };

    const handleError = (event) => {
      addError({
        type: "error",
        message: event?.message || "Unknown error",
        stack: event?.error?.stack || ""
      });
    };

    const handleRejection = (event) => {
      const reason = event?.reason;
      addError({
        type: "rejection",
        message: reason?.message || String(reason || "Unhandled rejection"),
        stack: reason?.stack || ""
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
    };
  }, [debugEnabled]);

  if (!debugEnabled) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "12px",
        left: "12px",
        right: "12px",
        zIndex: 99999,
        background: "rgba(0, 0, 0, 0.85)",
        color: "#fff",
        borderRadius: "8px",
        padding: "10px 12px",
        fontSize: "12px",
        fontFamily: "Menlo, Consolas, monospace",
        maxHeight: "40vh",
        overflowY: "auto"
      }}
    >
      <div style={{ marginBottom: "6px", fontWeight: 600 }}>
        Debug Overlay (debug=1)
      </div>
      <div style={{ marginBottom: "8px", opacity: 0.8 }}>
        {location.pathname}
      </div>
      {errors.length === 0 ? (
        <div>No errors captured yet.</div>
      ) : (
        errors.map((err, index) => (
          <div
            key={`${err.type}-${index}`}
            style={{
              borderTop: index === 0 ? "none" : "1px solid rgba(255,255,255,0.1)",
              paddingTop: index === 0 ? 0 : "6px",
              marginTop: index === 0 ? 0 : "6px"
            }}
          >
            <div style={{ color: "#ffb3b3", fontWeight: 600 }}>
              {err.type.toUpperCase()}
            </div>
            <div style={{ whiteSpace: "pre-wrap" }}>{err.message}</div>
            {err.stack && (
              <div style={{ whiteSpace: "pre-wrap", opacity: 0.8 }}>{err.stack}</div>
            )}
          </div>
        ))
      )}
    </div>
  );
};

export default DebugOverlay;

import React, { useEffect, useMemo } from "react";
import "../Styles/AuthCallback.css";

const APP_CALLBACK_URL = "pailinabroadmobile://auth/callback";

const getCallbackState = () => {
  const query = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const error = query.get("error") || hash.get("error");
  const errorDescription =
    query.get("error_description") ||
    hash.get("error_description") ||
    query.get("error_code") ||
    hash.get("error_code");
  const hasAuthenticationPayload = Boolean(
    query.get("code") ||
      (hash.get("access_token") && hash.get("refresh_token"))
  );

  return {
    appUrl: `${APP_CALLBACK_URL}${window.location.search}${window.location.hash}`,
    error: errorDescription || error || "",
    hasAuthenticationPayload,
  };
};

const AuthCallback = () => {
  const callback = useMemo(getCallbackState, []);
  const canOpenApp = callback.hasAuthenticationPayload && !callback.error;

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "Open Pailin Abroad";

    return () => {
      document.title = previousTitle;
    };
  }, []);

  return (
    <main className="auth-handoff-page">
      <section className="auth-handoff-card" aria-labelledby="auth-handoff-title">
        <img
          className="auth-handoff-logo"
          src="/images/full-logo.webp"
          alt="Pailin Abroad"
        />

        {canOpenApp ? (
          <>
            <h1 id="auth-handoff-title">กลับไปที่แอป Pailin Abroad</h1>
            <p>
              เปิดแอปเพื่อยืนยันบัญชีและทำขั้นตอนการสมัครให้เสร็จสมบูรณ์
            </p>
            <p className="auth-handoff-english">
              Open the app to confirm your account and finish setting it up.
            </p>
            <a className="auth-handoff-primary" href={callback.appUrl}>
              เปิดแอป Pailin Abroad
            </a>
          </>
        ) : (
          <>
            <h1 id="auth-handoff-title">ไม่สามารถเปิดลิงก์นี้ได้</h1>
            <p>
              {callback.error ||
                "ลิงก์ยืนยันไม่สมบูรณ์หรือหมดอายุแล้ว กรุณาขอลิงก์ใหม่จากในแอป"}
            </p>
            <p className="auth-handoff-english">
              This confirmation link is invalid or expired. Please request a new link from the app.
            </p>
          </>
        )}

        <a className="auth-handoff-secondary" href="/download">
          ดาวน์โหลดแอป
        </a>
      </section>
    </main>
  );
};

export default AuthCallback;

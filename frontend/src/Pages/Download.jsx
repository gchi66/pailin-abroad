import { useEffect, useMemo } from "react";
import "../Styles/Download.css";

export const APP_STORE_URL =
  "https://apps.apple.com/th/app/pailin-abroad/id6762322535";
export const PLAY_STORE_URL =
  "https://play.google.com/store/apps/details?id=com.pailinabroad.app";

export function getMobileStore(userAgent, platform, maxTouchPoints) {
  const ua = userAgent || "";

  if (/android/i.test(ua)) return "android";

  // iPadOS can identify itself as macOS when desktop-class browsing is enabled.
  const isAppleMobile = /iPad|iPhone|iPod/i.test(ua);
  const isIPadDesktopMode = platform === "MacIntel" && maxTouchPoints > 1;
  return isAppleMobile || isIPadDesktopMode ? "ios" : null;
}

function AppleLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M16.37 12.85c-.03-3.08 2.52-4.57 2.64-4.64-1.44-2.11-3.68-2.4-4.47-2.43-1.9-.19-3.71 1.12-4.68 1.12s-2.46-1.09-4.04-1.06c-2.08.03-3.99 1.21-5.06 3.07-2.16 3.74-.55 9.27 1.55 12.3 1.03 1.48 2.25 3.15 3.85 3.09 1.55-.06 2.13-1 4-1 1.88 0 2.4 1 4.04.97 1.67-.03 2.72-1.51 3.74-3 1.18-1.72 1.67-3.39 1.7-3.48-.04-.01-3.25-1.25-3.28-4.94ZM13.25 3.87C14.1 2.84 14.68 1.4 14.52 0c-1.23.05-2.72.82-3.6 1.85-.79.92-1.49 2.38-1.3 3.78 1.37.11 2.76-.7 3.63-1.76Z" />
    </svg>
  );
}

function PlayLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path fill="#00d6ff" d="M3.1 1.35a2.1 2.1 0 0 0-.35 1.18v18.94c0 .43.13.84.36 1.18L13.72 12 3.1 1.35Z" />
      <path fill="#ffdf00" d="m13.72 12 3.18-3.19L5.65 2.42a2.16 2.16 0 0 0-1.54-.28L13.72 12Z" />
      <path fill="#ff3a44" d="M4.1 21.86c.5.1 1.04.01 1.55-.28l11.26-6.4L13.72 12 4.1 21.86Z" />
      <path fill="#00ef77" d="m20.11 10.64-3.21-1.83L13.72 12l3.19 3.18 3.21-1.82c1.12-.64 1.12-2.08-.01-2.72Z" />
    </svg>
  );
}

function StoreButton({ href, store, children }) {
  return (
    <a className="download-store-button" href={href} aria-label={children}>
      {store === "ios" ? <AppleLogo /> : <PlayLogo />}
      <span>{children}</span>
    </a>
  );
}

export default function Download() {
  const store = useMemo(() => {
    if (typeof navigator === "undefined") return null;
    return getMobileStore(
      navigator.userAgent,
      navigator.platform,
      navigator.maxTouchPoints
    );
  }, []);

  const destination =
    store === "ios" ? APP_STORE_URL : store === "android" ? PLAY_STORE_URL : null;

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "ดาวน์โหลด Pailin Abroad";

    if (destination) {
      window.location.replace(destination);
    }

    return () => {
      document.title = previousTitle;
    };
  }, [destination]);

  return (
    <main className="download-page">
      <section className="download-card" aria-labelledby="download-title">
        <img
          className="download-logo"
          src="/images/full-logo.webp"
          alt="Pailin Abroad"
        />

        <img
          className="download-character"
          src="/images/characters/pailin_blue_circle.webp"
          alt=""
        />

        <h1 id="download-title">เรียนภาษาอังกฤษกับ Pailin Abroad</h1>
        <p className="download-thai-copy">
          ดาวน์โหลดแอป แล้วเริ่มเรียนภาษาอังกฤษที่ใช้ได้จริงกันเลย
        </p>
        <p className="download-english-copy">
          Download the app and start learning real-world English today.
        </p>

        {destination && (
          <p className="download-redirecting" role="status">
            กำลังพาไปดาวน์โหลดแอป…
          </p>
        )}

        <div className="download-store-buttons">
          <StoreButton href={APP_STORE_URL} store="ios">
            ดาวน์โหลดบน App Store
          </StoreButton>
          <StoreButton href={PLAY_STORE_URL} store="android">
            ดาวน์โหลดบน Google Play
          </StoreButton>
        </div>
      </section>
    </main>
  );
}

import React, { useEffect, useRef, useState } from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import "../Styles/GetAppBottomSheet.css";

const APP_NUDGE_DELAY_MS = 1500;
const DISMISS_ANIMATION_MS = 250;
const SWIPE_DISMISS_THRESHOLD = 60;
const MOBILE_UA_PATTERN =
  /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile/i;

const copy = {
  en: {
    headline: "Better on the app.",
    appName: "Pailin Abroad",
    featureAudioTitle: "Audio keeps playing",
    featureAudioBody: "Lock your screen - the conversation keeps going.",
    featureScreenTitle: "Built for your screen",
    featureScreenBody: "Full-screen lesson flow, no browser chrome in the way.",
    cta: "Download on the App Store",
    dismiss: "Continue on web",
    closeLabel: "Close app download prompt",
    ctaLabel: "App Store download coming soon",
  },
  th: {
    headline: "ดีกว่าบนแอป",
    appName: "Pailin Abroad",
    featureAudioTitle: "เสียงยังเล่นต่อได้",
    featureAudioBody: "ล็อกหน้าจอได้เลย แต่บทสนทนายังเล่นต่อ",
    featureScreenTitle: "ออกแบบมาสำหรับหน้าจอคุณ",
    featureScreenBody: "เรียนได้เต็มหน้าจอ ไม่มีแถบเบราว์เซอร์มาบัง",
    cta: "ดาวน์โหลดบน App Store",
    dismiss: "ใช้งานบนเว็บต่อ",
    closeLabel: "ปิดหน้าต่างแนะนำแอป",
    ctaLabel: "ลิงก์ App Store จะมาเร็ว ๆ นี้",
  },
};

function isEligibleMobileBrowser() {
  if (typeof window === "undefined" || typeof navigator === "undefined") {
    return false;
  }

  const ua = navigator.userAgent || navigator.vendor || "";
  const hasMobileUa = MOBILE_UA_PATTERN.test(ua);
  const hasNarrowViewport = window.innerWidth < 768;

  return hasMobileUa || hasNarrowViewport;
}

export default function GetAppBottomSheet() {
  const { ui } = useUiLang();
  const activeCopy = copy[ui] || copy.en;
  const [isRendered, setIsRendered] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [dragOffset, setDragOffset] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const isRenderedRef = useRef(false);
  const dismissTimeoutRef = useRef(null);
  const showTimeoutRef = useRef(null);
  const animationFrameRef = useRef(null);
  const cleanupRenderedTimeoutRef = useRef(null);
  const touchStartYRef = useRef(0);
  const currentDragRef = useRef(0);
  const hasDismissedRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    if (!isEligibleMobileBrowser()) return undefined;

    showTimeoutRef.current = window.setTimeout(() => {
      setIsRendered(true);
      animationFrameRef.current = window.requestAnimationFrame(() => {
        setIsOpen(true);
      });
    }, APP_NUDGE_DELAY_MS);

    return () => {
      if (showTimeoutRef.current) window.clearTimeout(showTimeoutRef.current);
      if (dismissTimeoutRef.current) window.clearTimeout(dismissTimeoutRef.current);
      if (cleanupRenderedTimeoutRef.current) window.clearTimeout(cleanupRenderedTimeoutRef.current);
      if (animationFrameRef.current) window.cancelAnimationFrame(animationFrameRef.current);
    };
  }, []);

  useEffect(() => {
    isRenderedRef.current = isRendered;
  }, [isRendered]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;

    const handleResize = () => {
      if (isEligibleMobileBrowser()) return;

      if (showTimeoutRef.current) {
        window.clearTimeout(showTimeoutRef.current);
        showTimeoutRef.current = null;
      }

      if (isRenderedRef.current) {
        setIsOpen(false);
        cleanupRenderedTimeoutRef.current = window.setTimeout(() => {
          setIsRendered(false);
        }, DISMISS_ANIMATION_MS);
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  useEffect(() => {
    if (!isRendered) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isRendered]);

  const dismissSheet = () => {
    if (!isRendered || hasDismissedRef.current) return;

    hasDismissedRef.current = true;
    setIsDragging(false);
    setDragOffset(0);
    setIsOpen(false);
    dismissTimeoutRef.current = window.setTimeout(() => {
      setIsRendered(false);
    }, DISMISS_ANIMATION_MS);
  };

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget) {
      dismissSheet();
    }
  };

  const handleTouchStart = (event) => {
    if (!event.touches || event.touches.length === 0) return;
    touchStartYRef.current = event.touches[0].clientY;
    currentDragRef.current = 0;
    setIsDragging(true);
  };

  const handleTouchMove = (event) => {
    if (!event.touches || event.touches.length === 0) return;
    const nextOffset = Math.max(0, event.touches[0].clientY - touchStartYRef.current);
    currentDragRef.current = nextOffset;
    setDragOffset(nextOffset);
  };

  const handleTouchEnd = () => {
    setIsDragging(false);

    if (currentDragRef.current > SWIPE_DISMISS_THRESHOLD) {
      dismissSheet();
      return;
    }

    currentDragRef.current = 0;
    setDragOffset(0);
  };

  const handleCtaClick = (event) => {
    event.preventDefault();
  };

  if (!isRendered) return null;

  const closedOffset = "100%";
  const translateY = isOpen ? `${dragOffset}px` : `calc(${closedOffset} + ${dragOffset}px)`;

  return (
    <div
      className={`app-nudge-overlay${isOpen ? " is-open" : ""}`}
      onClick={handleOverlayClick}
      aria-hidden={!isOpen}
    >
      <section
        className={`app-nudge-sheet${isDragging ? " is-dragging" : ""}`}
        style={{ transform: `translateY(${translateY})` }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="app-nudge-title"
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div className="app-nudge-handle-wrap">
          <div className="app-nudge-handle" />
        </div>

        <button
          type="button"
          className="app-nudge-close close-btn"
          onClick={dismissSheet}
          aria-label={activeCopy.closeLabel}
        >
          <span aria-hidden="true">×</span>
        </button>

        <div className="app-nudge-header">
          <img
            className="app-nudge-icon"
            src="/images/characters/pailin_blue_circle.webp"
            alt=""
          />
          <div className="app-nudge-header-copy">
            <h2 id="app-nudge-title" className="app-nudge-title">
              {activeCopy.headline}
            </h2>
            <p className="app-nudge-app-name">{activeCopy.appName}</p>
          </div>
        </div>

        <div className="app-nudge-divider" />

        <div className="app-nudge-features">
          <div className="app-nudge-feature-row">
            <div className="app-nudge-feature-icon" aria-hidden="true">
              <svg viewBox="0 0 28 28" focusable="false">
                <rect x="8.5" y="5.5" width="11" height="17" rx="3" />
                <line x1="11" y1="8.5" x2="17" y2="8.5" />
                <circle cx="14" cy="18.5" r="1" />
              </svg>
            </div>
            <div className="app-nudge-feature-copy">
              <p className="app-nudge-feature-title">{activeCopy.featureAudioTitle}</p>
              <p className="app-nudge-feature-body">{activeCopy.featureAudioBody}</p>
            </div>
          </div>

          <div className="app-nudge-feature-row">
            <div className="app-nudge-feature-icon" aria-hidden="true">
              <svg viewBox="0 0 28 28" focusable="false">
                <rect x="6" y="7" width="16" height="14" rx="3" />
                <line x1="9.5" y1="11" x2="18.5" y2="11" />
                <line x1="9.5" y1="14.5" x2="18.5" y2="14.5" />
                <line x1="9.5" y1="18" x2="15" y2="18" />
              </svg>
            </div>
            <div className="app-nudge-feature-copy">
              <p className="app-nudge-feature-title">{activeCopy.featureScreenTitle}</p>
              <p className="app-nudge-feature-body">{activeCopy.featureScreenBody}</p>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="app-nudge-cta"
          onClick={handleCtaClick}
          aria-label={activeCopy.ctaLabel}
        >
          <svg
            className="app-nudge-cta-logo"
            viewBox="0 0 24 24"
            focusable="false"
            aria-hidden="true"
          >
            <path d="M16.365 12.853c-.03-3.086 2.522-4.571 2.638-4.642-1.442-2.108-3.682-2.398-4.468-2.431-1.902-.192-3.711 1.118-4.678 1.118-.969 0-2.457-1.09-4.038-1.06-2.078.03-3.993 1.209-5.062 3.068-2.157 3.74-.549 9.269 1.55 12.303 1.025 1.483 2.247 3.146 3.853 3.086 1.548-.062 2.132-.999 4.004-.999 1.874 0 2.397.999 4.034.968 1.665-.03 2.719-1.514 3.737-3.002 1.18-1.724 1.665-3.39 1.695-3.476-.037-.011-3.245-1.246-3.277-4.933Zm-3.114-8.98c.853-1.032 1.429-2.468 1.272-3.873-1.23.049-2.719.82-3.602 1.851-.792.919-1.49 2.38-1.302 3.783 1.369.107 2.76-.699 3.632-1.761Z" />
          </svg>
          <span>{activeCopy.cta}</span>
        </button>

        <button
          type="button"
          className="app-nudge-dismiss"
          onClick={dismissSheet}
        >
          {activeCopy.dismiss}
        </button>
      </section>
    </div>
  );
}

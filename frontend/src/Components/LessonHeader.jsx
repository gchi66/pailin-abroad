import React, { useMemo } from "react";
import { Link } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import "../Styles/LessonHeader.css";

export default function LessonHeader({
  lessonId,
  level,
  lessonOrder,
  title,
  headerImageUrl,
  headerImagePath,
  focus,
  backstory,
}) {
  const { ui: uiLang } = useUiLang();

  const trimOrEmpty = (value) => {
    if (typeof value === "string") {
      return value.trim();
    }
    return value ?? "";
  };

  const fallbackTitle = trimOrEmpty(title) || "";
  const fallbackFocus = trimOrEmpty(focus) || "";
  const fallbackBackstory = trimOrEmpty(backstory) || "";
  const backLinkText = t("lessonHeader.backLink", uiLang) || "< BACK TO LESSON LIBRARY";
  const backstoryLabel = t("lessonHeader.backstoryLabel", uiLang) || "Backstory";

  const isCheckpoint = (title || "").toLowerCase().includes("checkpoint");
  const imageSrc = useMemo(() => {
    if (headerImageUrl) return headerImageUrl;
    if (headerImagePath) {
      const { data } = supabaseClient.storage
        .from("lesson-images")
        .getPublicUrl(headerImagePath);
      return data?.publicUrl || "";
    }
    return "";
  }, [headerImageUrl, headerImagePath]);

  const hasImage = Boolean(imageSrc);
  const hasBackstory = Boolean(fallbackBackstory);
  const lessonLabel = isCheckpoint
    ? `Level ${level} · Checkpoint`
    : `Level ${level} · Lesson ${lessonOrder}`;

  return (
    <section
      className={`lesson-banner${hasImage ? "" : " no-image"}`}
      data-sticky-head-id="lesson-header"
    >
      <div className="lesson-banner-inner">
        <Link to="/lessons" className="back-link">
          {backLinkText}
        </Link>
        <div className="lesson-banner-main">
          {/* LEFT: inline graphic */}
          {hasImage ? (
            <div className="banner-graphic">
              <img
                src={imageSrc}
                alt=""
                className="graphic-image"
                loading="lazy"
              />
            </div>
          ) : null}

          {/* RIGHT: content */}
          <div className="banner-content">
            <span className="header-lesson-number">
              {lessonLabel}
            </span>

            <h1 className="lesson-title">{fallbackTitle}</h1>

            {fallbackFocus ? (
              <p className="lesson-focus-text">{fallbackFocus}</p>
            ) : null}
          </div>
        </div>

        {hasBackstory ? (
          <div className="lesson-backstory">
            <p className="lesson-backstory-text">
              <span className="lesson-backstory-label">{backstoryLabel}</span>{" "}
              {fallbackBackstory}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

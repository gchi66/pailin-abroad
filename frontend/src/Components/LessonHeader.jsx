import React, { useEffect, useState } from "react";
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
  focus,
  backstory,
}) {
  const { ui: uiLang } = useUiLang();
  const [localized, setLocalized] = useState(() => ({
    title: title ?? "",
    focus: focus ?? "",
    backstory: backstory ?? "",
  }));

  useEffect(() => {
    let isActive = true;

    async function syncLessonCopy() {
      // For non-Thai UI or missing lesson id, just mirror the incoming props
      if (!lessonId || uiLang !== "th") {
        if (isActive) {
          setLocalized({
            title: title ?? "",
            focus: focus ?? "",
            backstory: backstory ?? "",
          });
        }
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("title_th, focus_th, backstory_th, title, focus, backstory")
          .eq("id", lessonId)
          .maybeSingle();

        if (!isActive) return;

        if (!error && data) {
          setLocalized({
            title: (data.title_th && data.title_th.trim()) || data.title || title || "",
            focus: (data.focus_th && data.focus_th.trim()) || data.focus || focus || "",
            backstory: (data.backstory_th && data.backstory_th.trim()) || data.backstory || backstory || "",
          });
        } else {
          setLocalized({
            title: title ?? "",
            focus: focus ?? "",
            backstory: backstory ?? "",
          });
        }
      } catch (err) {
        if (isActive) {
          setLocalized({
            title: title ?? "",
            focus: focus ?? "",
            backstory: backstory ?? "",
          });
        }
      }
    }

    syncLessonCopy();

    return () => {
      isActive = false;
    };
  }, [lessonId, uiLang, title, focus, backstory]);

  const fallbackTitle = localized.title || "";
  const fallbackFocus = localized.focus || "";
  const fallbackBackstory = localized.backstory || "";
  const backLinkText = t("lessonHeader.backLink", uiLang) || "< BACK TO LESSON LIBRARY";
  const backstoryLabel = t("lessonHeader.backstoryLabel", uiLang) || "Backstory";

  const isCheckpoint = (title || "").toLowerCase().includes("checkpoint");
  const hasImage = Boolean(headerImageUrl);
  const hasBackstory = Boolean(fallbackBackstory);
  const lessonLabel = isCheckpoint
    ? `Level ${level} · Checkpoint`
    : `Level ${level} · Lesson ${lessonOrder}`;

  return (
    <section className={`lesson-banner${hasImage ? "" : " no-image"}`}>
      <div className="lesson-banner-inner">
        <Link to="/lessons" className="back-link">
          {backLinkText}
        </Link>
        <div className="lesson-banner-main">
          {/* LEFT: inline graphic */}
          {hasImage ? (
            <div className="banner-graphic">
              <img
                src={headerImageUrl}
                alt=""
                className="graphic-image"
                loading="lazy"
              />
            </div>
          ) : null}

          {/* RIGHT: content */}
          <div className="banner-content">
            <span className="lesson-number">
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

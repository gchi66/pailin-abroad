import React from "react";
import { Link } from "react-router-dom";
import "../Styles/LessonHeader.css";

export default function LessonHeader({
  level,
  lessonOrder,
  title,
  subtitle,
  titleTh,
  subtitleTh,
  headerImageUrl,
}) {
  const isCheckpoint = (title || "").toLowerCase().includes("checkpoint");
  const hasImage = Boolean(headerImageUrl);

  return (
    <section className="lesson-banner">
      <div className="banner-left">
        <Link to="/lessons" className="back-link">
          &lt; BACK TO LESSON LIBRARY
        </Link>

        <span className="lesson-number">
          {isCheckpoint ? `LESSON ${level} CHECKPOINT` : `LESSON ${level}.${lessonOrder}`}
        </span>
        <h1 className="lesson-title">{title}</h1>
        <h2 className="lesson-subtitle">{subtitle}</h2>

        {/* <p className="thai-line">
          {titleTh}<br />
          {subtitleTh}
        </p> */}
      </div>

      <div className="banner-right">
        <div className={`character-panel${hasImage ? " has-image" : ""}`}>
          {hasImage ? (
            <img src={headerImageUrl} alt="" className="character-image" loading="lazy" />
          ) : null}
        </div>
      </div>
    </section>
  );
}

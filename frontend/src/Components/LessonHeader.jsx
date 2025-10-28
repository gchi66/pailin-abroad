import React from "react";
import { Link } from "react-router-dom";
import "../Styles/LessonHeader.css";

export default function LessonHeader({
  level,
  lessonOrder,
  title,
  headerImageUrl,
  focus,
  backstory,
}) {
  const isCheckpoint = (title || "").toLowerCase().includes("checkpoint");
  const hasImage = Boolean(headerImageUrl);
  const hasBackstory = Boolean(backstory);
  const lessonLabel = isCheckpoint
    ? `Level ${level} · Checkpoint`
    : `Lesson ${lessonOrder} · Level ${level}`;

  return (
    <section className={`lesson-banner${hasImage ? "" : " no-image"}`}>
      {/* LEFT: inline graphic (no border, no separate panel) */}
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
        {/* <Link to="/lessons" className="back-link">
          &lt; BACK TO LESSON LIBRARY
        </Link> */}

        <span className="lesson-number">
          {lessonLabel}
        </span>

        <h1 className="lesson-title">{title}</h1>

        {focus ? (
          <p className="lesson-focus-text">{focus}</p>
        ) : null}
      </div>

      {hasBackstory ? (
        <div className="lesson-backstory">
          <p className="lesson-backstory-text">
            <span className="lesson-backstory-label">Backstory</span>{" "}
            {backstory}
          </p>
        </div>
      ) : null}
    </section>
  );
}

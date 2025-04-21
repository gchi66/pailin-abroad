import React from "react";
import { Link } from "react-router-dom";
import "../Styles/LessonHeader.css";

export default function LessonHeader({ level, lessonOrder, title, subtitle, titleTh, subtitleTh }) {
  return (
    <section className="lesson-banner">
      {/* left column */}
      <div className="banner-left">
        <Link to="/lessons" className="back-link">
          &lt; BACK TO LESSON LIBRARY
        </Link>

        <span className="lesson-number">LESSON {level}.{lessonOrder}</span>
        <h1 className="lesson-title">{title}</h1>
        <h2 className="lesson-subtitle">{subtitle}</h2>

        <p className="thai-line">
          {titleTh}<br />
          {subtitleTh}
        </p>
      </div>

      {/* right column */}
      <div className="banner-right">
        {/* placeholder panel – you'll swap in a dynamic <img /> later */}
        <div className="character-panel" aria-hidden="true" />
      </div>
    </section>
  );
}

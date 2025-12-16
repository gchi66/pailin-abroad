import React from "react";
import "../Styles/FreeLessonHeader.css";

const FreeLessonHeader = () => (
  <section className="free-lesson-header">
    <div className="flh-line" />
    <div className="flh-bubble">
      <span className="flh-text flh-text--title">
        <span className="flh-title-line">Try a free</span>
        <span className="flh-title-line">lesson now!</span>
      </span>
      <span className="flh-text flh-text--subtitle">No sign-up needed.</span>
    </div>
  </section>
);

export default FreeLessonHeader;

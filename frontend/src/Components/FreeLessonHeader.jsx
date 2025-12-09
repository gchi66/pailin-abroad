import React from "react";
import "../Styles/FreeLessonHeader.css";

const FreeLessonHeader = () => (
  <section className="free-lesson-header">
    <div className="flh-line" />
    <div className="flh-bubble">
      <span className="flh-text flh-text--title">Try a free lesson now!</span>
      <span className="flh-text flh-text--subtitle">No sign-up needed.</span>
    </div>
  </section>
);

export default FreeLessonHeader;

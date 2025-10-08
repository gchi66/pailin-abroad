import React from "react";
import { Link } from "react-router-dom";
import FreeLessonCards from "../Components/FreeLessonCards";
import "../Styles/TryLessons.css";

const TryLessons = () => {
  return (
    <div className="try-lessons-page-container">
      {/* Header */}
      <header className="try-lessons-page-header">
        <h1 className="try-lessons-header-text">TRY OUR LESSONS</h1>
        <p className="try-lessons-header-subtitle">
          3 free lessons for you to try, no sign-up needed!
        </p>
      </header>

      {/* Intro Text */}
      <div className="try-lessons-intro-section">
        <p className="try-lessons-intro">
          We're confident you'll love our unique, narrative-driven method of learning English.
          Explore a lesson from each level to see for yourself.
        </p>
      </div>

      {/* Free Lesson Cards */}
      <div className="try-lessons-cards-container">
        <FreeLessonCards showHeader={false} />
      </div>

      {/* Call-to-Action Buttons */}
      <div className="try-lessons-cta">
        <Link to="/signup" className="try-lessons-cta-link">
          <button className="signup-cta-button">SIGN UP FOR FREE</button>
        </Link>
        <Link to="/membership" className="try-lessons-cta-link">
          <button className="member-cta-button">BECOME A MEMBER</button>
        </Link>
      </div>
    </div>
  );
};

export default TryLessons;

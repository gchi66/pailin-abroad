import React, { useState } from "react";
import { Link } from "react-router-dom";
import "../Styles/MyPathway.css";

const MyPathway = () => {
  const [activeTab, setActiveTab] = useState("pathway");

  // Mock data for demonstration
  const userProfile = {
    name: "Sarah Johnson",
    level: "Upper Intermediate",
    plan: "Premium",
    lessonsComplete: 142,
    levelsComplete: 8
  };

  const currentProgress = {
    nextLesson: "Level 6 • Lesson 13",
    progressPercentage: 70
  };

  // Mock lesson data
  const pathwayLessons = [
    { id: 1, number: 11, title: "Making Small Talk", subtitle: "การพูดคุยเรื่องเล็กๆ น้อยๆ", isCompleted: true },
    { id: 2, number: 12, title: "Asking for Directions", subtitle: "การถามทาง", isCompleted: true },
    { id: 3, number: 13, title: "Ordering Food at a Restaurant", subtitle: "การสั่งอาหารที่ร้านอาหาร", isCurrent: true },
    { id: 4, number: 14, title: "Discussing Weekend Plans", subtitle: "การพูดคุยเกี่ยวกับแผนสุดสัปดาห์", isCompleted: false },
    { id: 5, number: 15, title: "Making Appointments", subtitle: "การนัดหมาย", isCompleted: false }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "pathway":
        return (
          <>
            {/* Progress Section */}
            <div className="pathway-progress-section">
              <h3 className="pathway-section-title">Your next lesson: {currentProgress.nextLesson}</h3>
              <div className="pathway-progress-bar-container">
                <div className="pathway-progress-bar">
                  <div
                    className="pathway-progress-fill"
                    style={{ width: `${currentProgress.progressPercentage}%` }}
                  ></div>
                </div>
                <span className="pathway-progress-text">{currentProgress.progressPercentage}% Complete</span>
              </div>
            </div>

            {/* Lessons List */}
            <div className="pathway-lessons-section">
              <div className="pathway-lesson-list">
                {pathwayLessons.map((lesson) => (
                  <Link
                    to={`/lesson/${lesson.id}`}
                    key={lesson.id}
                    className={`pathway-lesson-item ${lesson.isCurrent ? 'current' : ''} ${lesson.isCompleted ? 'completed' : ''}`}
                  >
                    <div className="pathway-lesson-left">
                      <span className="pathway-lesson-number">{lesson.number}</span>
                      <div className="pathway-lesson-content">
                        <span className="pathway-lesson-title">{lesson.title}</span>
                        <span className="pathway-lesson-subtitle">{lesson.subtitle}</span>
                      </div>
                    </div>
                    <div className="pathway-lesson-right">
                      {lesson.isCompleted ? (
                        <img src="/images/filled-checkmark-lesson-complete.png" alt="Completed" className="pathway-checkmark" />
                      ) : (
                        <img src="/images/CheckCircle.png" alt="Not completed" className="pathway-checkmark" />
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </>
        );

      case "completed":
        return (
          <div className="pathway-placeholder">
            <h3>Completed Lessons</h3>
            <p>Your completed lessons will appear here.</p>
          </div>
        );

      case "liked":
        return (
          <div className="pathway-placeholder">
            <h3>My Liked Lessons</h3>
            <p>Your liked lessons will appear here.</p>
          </div>
        );

      case "comments":
        return (
          <div className="pathway-placeholder">
            <h3>Comment History</h3>
            <p>Your comment history will appear here.</p>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <main className="pathway-main">
      <div className="pathway-container">

        {/* Header Section */}
        <div className="pathway-header">
          <div className="pathway-header-left">
            <img
              src="/images/characters/pailin-blue-left.png"
              alt="Profile Avatar"
              className="pathway-avatar"
            />
            <div className="pathway-user-info">
              <h2 className="pathway-welcome">Welcome back, {userProfile.name}</h2>
              <div className="pathway-account-info">
                <span className="pathway-level">Level: {userProfile.level}</span>
                <span className="pathway-plan">Plan: Full Access</span>
                <Link to="/profile" className="pathway-settings-link">Account Settings</Link>
              </div>
            </div>
          </div>

          <div className="pathway-header-right">
            <div className="pathway-counter">
              <span className="pathway-counter-label">Lessons Complete</span>
              <span className="pathway-counter-number">{userProfile.lessonsComplete}</span>
            </div>
            <div className="pathway-counter">
              <span className="pathway-counter-label">Levels Complete</span>
              <span className="pathway-counter-number">{userProfile.levelsComplete}</span>
            </div>
          </div>
        </div>


        {/* Navigation Tabs */}
        <nav className="pathway-nav">
          <div className="pathway-tabs">
            <a
              href="#"
              className={`pathway-tab ${activeTab === "pathway" ? "active" : ""}`}
              onClick={(e) => { e.preventDefault(); setActiveTab("pathway"); }}
            >
              My Pathway
            </a>
            <a
              href="#"
              className={`pathway-tab ${activeTab === "completed" ? "active" : ""}`}
              onClick={(e) => { e.preventDefault(); setActiveTab("completed"); }}
            >
              Completed
            </a>
            <a
              href="#"
              className={`pathway-tab ${activeTab === "liked" ? "active" : ""}`}
              onClick={(e) => { e.preventDefault(); setActiveTab("liked"); }}
            >
              My Liked Lessons
            </a>
            <a
              href="#"
              className={`pathway-tab ${activeTab === "comments" ? "active" : ""}`}
              onClick={(e) => { e.preventDefault(); setActiveTab("comments"); }}
            >
              Comment History
            </a>
          </div>
        </nav>

        {/* Tab Content */}
        <div className="pathway-content">
          {renderTabContent()}
        </div>

        {/* Footer Link */}
        <div className="pathway-footer">
          <Link to="/lessons" className="pathway-library-link">
            Go to Lesson Library →
          </Link>
        </div>

      </div>
    </main>
  );
};

export default MyPathway;

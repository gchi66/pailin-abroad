import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import "../Styles/MyPathway.css";

const MyPathway = () => {
  const [activeTab, setActiveTab] = useState("pathway");
  const [userProfile, setUserProfile] = useState(null);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [pathwayLessons, setPathwayLessons] = useState([]);
  const [nextLesson, setNextLesson] = useState(null);
  const [userStats, setUserStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { user } = useAuth();

  // Fetch user profile data from backend
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        // Get the current session to access the access token
        const { data: { session } } = await supabaseClient.auth.getSession();

        if (!session?.access_token) {
          setError("No authentication token found");
          setLoading(false);
          return;
        }

        // Make API call to backend for profile
        const profileResponse = await fetch('/api/user/profile', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!profileResponse.ok) {
          throw new Error(`HTTP error! status: ${profileResponse.status}`);
        }

        const profileData = await profileResponse.json();
        setUserProfile(profileData.profile);

        // Fetch completed lessons
        const lessonsResponse = await fetch('/api/user/completed-lessons', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (lessonsResponse.ok) {
          const lessonsData = await lessonsResponse.json();
          setCompletedLessons(lessonsData.completed_lessons || []);
        }

        // Fetch next lesson
        const nextLessonResponse = await fetch('/api/user/next-lesson', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (nextLessonResponse.ok) {
          const nextLessonData = await nextLessonResponse.json();
          setNextLesson(nextLessonData.next_lesson);
        }

        // Fetch pathway lessons
        const pathwayResponse = await fetch('/api/user/pathway-lessons', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (pathwayResponse.ok) {
          const pathwayData = await pathwayResponse.json();
          setPathwayLessons(pathwayData.pathway_lessons || []);
        }

        // Fetch user stats (lessons and levels completed)
        const statsResponse = await fetch('/api/user/stats', {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        });

        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setUserStats(statsData);
        }

      } catch (err) {
        console.error('Error fetching user data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchUserProfile();
  }, [user]);

  // Mock data for demonstration (will be replaced with real data later)
  const mockUserProfile = {
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

  const renderTabContent = () => {
    switch (activeTab) {
      case "pathway":
        return (
          <>
            {/* Progress Section */}
            <div className="pathway-progress-section">
              <h3 className="pathway-section-title">
                Your next lesson: {nextLesson ? nextLesson.formatted : "Loading..."}
              </h3>
              {/* <div className="pathway-progress-bar-container">
                <div className="pathway-progress-bar">
                  <div
                    className="pathway-progress-fill"
                    style={{ width: `${currentProgress.progressPercentage}%` }}
                  ></div>
                </div>
                <span className="pathway-progress-text">{currentProgress.progressPercentage}% Complete</span>
              </div> */}
            </div>

            {/* Lessons List */}
            <div className="pathway-lessons-section">
              <div className="pathway-lesson-list">
                {pathwayLessons.map((lesson, index) => (
                  <Link
                    to={`/lesson/${lesson.id}`}
                    key={lesson.id}
                    className={`pathway-lesson-item ${index === 0 ? 'next-lesson' : ''}`}
                  >
                    <div className="pathway-lesson-content">
                      <div className="pathway-lesson-header">
                        <span className="pathway-lesson-number">
                          {lesson.level}.{lesson.lesson_order}
                        </span>
                        <div className="pathway-lesson-text">
                          <span className="pathway-lesson-title">
                            {lesson.title}
                          </span>
                          {lesson.focus && (
                            <div className="pathway-lesson-focus">
                              {lesson.focus}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="pathway-lesson-right">
                      <img
                        src="/images/CheckCircle.png"
                        alt="Not completed"
                        className="pathway-checkmark"
                      />
                    </div>
                  </Link>
                ))}
              </div>
            </div>
          </>
        );

      case "completed":
        return (
          <div className="pathway-completed-section">
            <h3>Completed Lessons ({completedLessons.length})</h3>
            {completedLessons.length > 0 ? (
              <div className="pathway-lesson-list">
                {completedLessons.map((progress) => (
                  <Link
                    to={`/lesson/${progress.lesson_id}`}
                    key={progress.id}
                    className="pathway-lesson-item completed"
                  >
                    <div className="pathway-lesson-left">
                      <span className="pathway-lesson-number">
                        {progress.lessons?.level && progress.lessons?.lesson_order
                          ? `${progress.lessons.level}.${progress.lessons.lesson_order}`
                          : progress.lessons?.external_id || progress.lesson_id}
                      </span>
                      <div className="pathway-lesson-content">
                        <span className="pathway-lesson-title">
                          {progress.lessons?.title || "Lesson Title"}
                          {progress.lessons?.title_th && (
                            <span className="lesson-name-th"> {progress.lessons.title_th}</span>
                          )}
                        </span>
                        <span className="pathway-lesson-subtitle">
                          {progress.lessons?.subtitle || ""}
                          {progress.lessons?.subtitle_th && (
                            <span className="lesson-desc-th"> {progress.lessons.subtitle_th}</span>
                          )}
                        </span>
                      </div>
                    </div>
                    <div className="pathway-lesson-right">
                      <img
                        src="/images/filled-checkmark-lesson-complete.webp"
                        alt="Completed"
                        className="pathway-checkmark"
                      />
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p>No completed lessons yet. Start learning to see your progress here!</p>
            )}
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

        {/* Loading State */}
        {loading && (
          <div className="pathway-loading">
            <p>Loading your pathway...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="pathway-error">
            <p>Error: {error}</p>
          </div>
        )}

        {/* Main Content - Show only when not loading and no error */}
        {!loading && !error && (
          <>
            {/* Header Section */}
            <div className="pathway-header">
              <div className="pathway-header-left">
                <img
                  src="/images/characters/pailin-blue-left.png"
                  alt="Profile Avatar"
                  className="pathway-avatar"
                />
                <div className="pathway-user-info">
                  <h2 className="pathway-welcome">Welcome back, {userProfile?.name || "User"}</h2>
                  <div className="pathway-account-info">
                    <span className="pathway-level">Level: {mockUserProfile.level}</span>
                    <span className="pathway-plan">Plan: Full Access</span>
                    <Link to="/profile" className="pathway-settings-link">Account Settings</Link>
                  </div>
                </div>
              </div>

              <div className="pathway-header-right">
                <div className="pathway-counter">
                  <span className="pathway-counter-label">Lessons Complete</span>
                  <span className="pathway-counter-number">{userStats?.lessons_completed || 0}</span>
                </div>
                <div className="pathway-counter">
                  <span className="pathway-counter-label">Levels Complete</span>
                  <span className="pathway-counter-number">{userStats?.levels_completed || 0}</span>
                </div>
              </div>
            </div>

            {/* Navigation Tabs */}
            <nav className="pathway-nav">
              <div className="pathway-tabs">
                <button
                  className={`pathway-tab ${activeTab === "pathway" ? "active" : ""}`}
                  onClick={() => setActiveTab("pathway")}
                >
                  My Pathway
                </button>
                <button
                  className={`pathway-tab ${activeTab === "completed" ? "active" : ""}`}
                  onClick={() => setActiveTab("completed")}
                >
                  Completed
                </button>
                <button
                  className={`pathway-tab ${activeTab === "liked" ? "active" : ""}`}
                  onClick={() => setActiveTab("liked")}
                >
                  My Liked Lessons
                </button>
                <button
                  className={`pathway-tab ${activeTab === "comments" ? "active" : ""}`}
                  onClick={() => setActiveTab("comments")}
                >
                  Comment History
                </button>
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
          </>
        )}

      </div>
    </main>
  );
};

export default MyPathway;

import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import supabaseClient from "../supabaseClient";
import "../Styles/MyPathway.css";

const MyPathway = () => {
  const [activeTab, setActiveTab] = useState("pathway");
  const [userProfile, setUserProfile] = useState(null);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [pathwayLessons, setPathwayLessons] = useState([]);
  const [nextLesson, setNextLesson] = useState(null);
  const [userStats, setUserStats] = useState(null);
  const [userComments, setUserComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAllCompleted, setShowAllCompleted] = useState(false);
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();

  // Helper function to pick the right language content
  const pickLang = (en, th) => {
    if (uiLang === "th") {
      return th || en; // fallback to English if Thai is not available
    }
    return en || th; // fallback to Thai if English is not available
  };

  // UI translations
  const uiText = {
    // Progress section
    yourNextLesson: uiLang === "th" ? "บทเรียนถัดไป:" : "Your next lesson:",
    checkpoint: uiLang === "th" ? "จุดตรวจสอบ" : "Checkpoint",
    loading: uiLang === "th" ? "กำลังโหลด..." : "Loading...",

    // Tab content
    completedLessons: uiLang === "th" ? "บทเรียนที่เสร็จแล้ว" : "Completed Lessons",
    noCompletedLessons: uiLang === "th" ? "ยังไม่มีบทเรียนที่เสร็จสิ้น เริ่มเรียนเพื่อดูความคืบหน้าของคุณที่นี่!" : "No completed lessons yet. Start learning to see your progress here!",
    myLikedLessons: uiLang === "th" ? "บทเรียนที่ฉันชอบ" : "My Liked Lessons",
    likedLessonsPlaceholder: uiLang === "th" ? "บทเรียนที่คุณชอบจะปรากฏที่นี่" : "Your liked lessons will appear here.",
    commentHistory: uiLang === "th" ? "ประวัติความคิดเห็น" : "Comment History",
    noComments: uiLang === "th" ? "ยังไม่มีความคิดเห็น เริ่มมีส่วนร่วมกับบทเรียนเพื่อดูประวัติความคิดเห็นของคุณที่นี่!" : "No comments yet. Start engaging with lessons to see your comment history here!",
    lessonNoLongerAvailable: uiLang === "th" ? "บทเรียนไม่พร้อมใช้งานแล้ว" : "Lesson no longer available",
    pinnedComment: uiLang === "th" ? "ความคิดเห็นที่ปักหมุด" : "Pinned comment",

    // Expand/collapse
    seeMore: uiLang === "th" ? "ดูเพิ่มเติม" : "See more",
    seeLess: uiLang === "th" ? "ดูน้อยลง" : "See less",

    // Loading and error states
    loadingPathway: uiLang === "th" ? "กำลังโหลดเส้นทางการเรียนของคุณ..." : "Loading your pathway...",
    errorPrefix: uiLang === "th" ? "ข้อผิดพลาด:" : "Error:",
    noAuthToken: uiLang === "th" ? "ไม่พบโทเค็นการตรวจสอบสิทธิ์" : "No authentication token found",

    // Header section
    welcomeBack: uiLang === "th" ? "ยินดีต้อนรับกลับ," : "Welcome back,",
    user: uiLang === "th" ? "ผู้ใช้" : "User",
    plan: uiLang === "th" ? "แผน:" : "Plan:",
    fullAccess: uiLang === "th" ? "เข้าถึงเต็มรูปแบบ" : "Full Access",
    accountSettings: uiLang === "th" ? "การตั้งค่าบัญชี" : "Account Settings",
    lessonsComplete: uiLang === "th" ? "บทเรียนที่เสร็จสิ้น" : "Lessons Complete",
    levelsComplete: uiLang === "th" ? "ระดับที่เสร็จสิ้น" : "Levels Complete",

    // Navigation tabs
    myPathway: uiLang === "th" ? "เส้นทางของฉัน" : "My Pathway",
    completed: uiLang === "th" ? "เสร็จสิ้นแล้ว" : "Completed",
    myLikedLessonsTab: uiLang === "th" ? "บทเรียนที่ชอบ" : "My Liked Lessons",
    commentHistoryTab: uiLang === "th" ? "ประวัติความคิดเห็น" : "Comment History",

    // Footer
    goToLessonLibrary: uiLang === "th" ? "ไปที่ไลบรารีบทเรียน →" : "Go to Lesson Library →",

    // Alt text and accessibility
    profileAvatar: uiLang === "th" ? "รูปโปรไฟล์" : "Profile Avatar",
    lessonCheckpoint: uiLang === "th" ? "จุดตรวจสอบบทเรียน" : "Lesson Checkpoint",
    notCompleted: uiLang === "th" ? "ยังไม่เสร็จสิ้น" : "Not completed",
    completedAlt: uiLang === "th" ? "เสร็จสิ้นแล้ว" : "Completed",

    // Default fallbacks
    lessonTitle: uiLang === "th" ? "ชื่อบทเรียน" : "Lesson Title"
  };

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

        // Make all API calls in parallel for faster loading
        const headers = {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        };

        const [
          profileResponse,
          lessonsResponse,
          nextLessonResponse,
          pathwayResponse,
          statsResponse,
          commentsResponse
        ] = await Promise.all([
          fetch('/api/user/profile', { method: 'GET', headers }),
          fetch('/api/user/completed-lessons', { method: 'GET', headers }),
          fetch('/api/user/next-lesson', { method: 'GET', headers }),
          fetch('/api/user/pathway-lessons', { method: 'GET', headers }),
          fetch('/api/user/stats', { method: 'GET', headers }),
          fetch('/api/user/comments', { method: 'GET', headers })
        ]);

        // Process responses
        if (!profileResponse.ok) {
          throw new Error(`HTTP error! status: ${profileResponse.status}`);
        }

        const profileData = await profileResponse.json();
        setUserProfile(profileData.profile);

        if (lessonsResponse.ok) {
          const lessonsData = await lessonsResponse.json();
          console.log('Completed lessons data:', lessonsData.completed_lessons);
          setCompletedLessons(lessonsData.completed_lessons || []);
        }

        if (nextLessonResponse.ok) {
          const nextLessonData = await nextLessonResponse.json();
          setNextLesson(nextLessonData.next_lesson);
        }

        if (pathwayResponse.ok) {
          const pathwayData = await pathwayResponse.json();
          setPathwayLessons(pathwayData.pathway_lessons || []);
        }

        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setUserStats(statsData);
        }

        if (commentsResponse.ok) {
          const commentsData = await commentsResponse.json();
          setUserComments(commentsData.comments || []);
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

  const renderTabContent = () => {
    switch (activeTab) {
      case "pathway":
        return (
          <>
            {/* Progress Section */}
            <div className="pathway-progress-section">
              <h3 className="pathway-section-title">
                {uiText.yourNextLesson} {nextLesson ? (
                  (nextLesson.title || "").toLowerCase().includes("checkpoint")
                    ? `Level ${nextLesson.level} ${uiText.checkpoint}`
                    : nextLesson.formatted
                ) : uiText.loading}
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
                        {(lesson.title || "").toLowerCase().includes("checkpoint") ? (
                          <img src="/images/black-checkmark-level-checkpoint.webp" alt={uiText.lessonCheckpoint} className="pathway-lesson-checkpoint" />
                        ) : (
                          <span className="pathway-lesson-number">
                            {lesson.level}.{lesson.lesson_order}
                          </span>
                        )}
                        <div className="pathway-lesson-text">
                          <span className="pathway-lesson-title">
                            {pickLang(lesson.title, lesson.title_th)}
                          </span>
                          {(lesson.focus || lesson.focus_th) && (
                            <div className="pathway-lesson-focus">
                              {pickLang(lesson.focus, lesson.focus_th)}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="pathway-lesson-right">
                      <img
                        src="/images/CheckCircle.png"
                        alt={uiText.notCompleted}
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
        const displayedCompletedLessons = showAllCompleted ? completedLessons : completedLessons.slice(0, 5);
        const hasMoreCompleted = completedLessons.length > 5;

        return (
          <div className="pathway-completed-section">
            <h3>{uiText.completedLessons} ({completedLessons.length})</h3>
            {completedLessons.length > 0 ? (
              <>
                <div className="pathway-lesson-list">
                  {displayedCompletedLessons.map((progress) => (
                    <Link
                      to={`/lesson/${progress.lesson_id}`}
                      key={progress.id}
                      className="pathway-lesson-item completed"
                    >
                      <div className="pathway-lesson-content">
                        <div className="pathway-lesson-header">
                          {(progress.lessons?.title || "").toLowerCase().includes("checkpoint") ? (
                            <img src="/images/black-checkmark-level-checkpoint.webp" alt={uiText.lessonCheckpoint} className="pathway-lesson-checkpoint" />
                          ) : (
                            <span className="pathway-lesson-number">
                              {progress.lessons?.level && progress.lessons?.lesson_order
                                ? `${progress.lessons.level}.${progress.lessons.lesson_order}`
                                : progress.lessons?.external_id || progress.lesson_id}
                            </span>
                          )}
                          <div className="pathway-lesson-text">
                            <span className="pathway-lesson-title">
                              {pickLang(progress.lessons?.title, progress.lessons?.title_th) || uiText.lessonTitle}
                            </span>
                            {(progress.lessons?.focus || progress.lessons?.focus_th) && (
                              <div className="pathway-lesson-focus">
                                {pickLang(progress.lessons?.focus, progress.lessons?.focus_th)}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="pathway-lesson-right">
                        <img
                          src="/images/filled-checkmark-lesson-complete.webp"
                          alt={uiText.completedAlt}
                          className="pathway-checkmark"
                        />
                      </div>
                    </Link>
                  ))}
                </div>

                {hasMoreCompleted && (
                  <div className="pathway-see-more-container">
                    <button
                      className="pathway-see-more-btn"
                      onClick={() => setShowAllCompleted(!showAllCompleted)}
                    >
                      <span>{showAllCompleted ? uiText.seeLess : uiText.seeMore}</span>
                      <svg
                        className={`pathway-arrow-icon ${showAllCompleted ? 'rotated' : ''}`}
                        width="16"
                        height="16"
                        viewBox="0 0 16 16"
                        fill="currentColor"
                      >
                        <path d="M8 12l-4-4h8l-4 4z"/>
                      </svg>
                    </button>
                  </div>
                )}
              </>
            ) : (
              <p>{uiText.noCompletedLessons}</p>
            )}
          </div>
        );

      case "liked":
        return (
          <div className="pathway-placeholder">
            <h3>{uiText.myLikedLessons}</h3>
            <p>{uiText.likedLessonsPlaceholder}</p>
          </div>
        );

      case "comments":
        return (
          <div className="pathway-comments-section">
            <h3>{uiText.commentHistory} ({userComments.length})</h3>
            {userComments.length > 0 ? (
              <div className="pathway-comments-list">
                {userComments.map((comment) => (
                  <div key={comment.id} className="pathway-comment-item">
                    <div className="pathway-comment-header">
                      <div className="pathway-comment-lesson-info">
                        {comment.lessons ? (
                          <Link to={`/lesson/${comment.lesson_id}`} className="pathway-comment-lesson-link">
                            <span className="pathway-comment-lesson-number">
                              {comment.lessons.level}.{comment.lessons.lesson_order}
                            </span>
                            <span className="pathway-comment-lesson-title">
                              {pickLang(comment.lessons.title, comment.lessons.title_th)}
                            </span>
                          </Link>
                        ) : (
                          <span className="pathway-comment-lesson-deleted">{uiText.lessonNoLongerAvailable}</span>
                        )}
                      </div>
                      <div className="pathway-comment-date">
                        {new Date(comment.created_at).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                    <div className="pathway-comment-body">
                      {comment.body}
                    </div>
                    {comment.pinned && (
                      <div className="pathway-comment-pinned">
                        📌 {uiText.pinnedComment}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="pathway-placeholder">
                <p>{uiText.noComments}</p>
              </div>
            )}
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
            <p>{uiText.loadingPathway}</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="pathway-error">
            <p>{uiText.errorPrefix} {error}</p>
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
                  alt={uiText.profileAvatar}
                  className="pathway-avatar"
                />
                <div className="pathway-user-info">
                  <h2 className="pathway-welcome">{uiText.welcomeBack} {userProfile?.name || uiText.user}</h2>
                  <div className="pathway-account-info">
                    {/* <span className="pathway-level">Level: Upper Intermediate</span> */}
                    <span className="pathway-plan">{uiText.plan} {uiText.fullAccess}</span>
                    <Link to="/profile" className="pathway-settings-link">{uiText.accountSettings}</Link>
                  </div>
                </div>
              </div>

              <div className="pathway-header-right">
                <div className="pathway-counter">
                  <span className="pathway-counter-label">{uiText.lessonsComplete}</span>
                  <span className="pathway-counter-number">{userStats?.lessons_completed || 0}</span>
                </div>
                <div className="pathway-counter">
                  <span className="pathway-counter-label">{uiText.levelsComplete}</span>
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
                  {uiText.myPathway}
                </button>
                <button
                  className={`pathway-tab ${activeTab === "completed" ? "active" : ""}`}
                  onClick={() => setActiveTab("completed")}
                >
                  {uiText.completed}
                </button>
                <button
                  className={`pathway-tab ${activeTab === "liked" ? "active" : ""}`}
                  onClick={() => setActiveTab("liked")}
                >
                  {uiText.myLikedLessonsTab}
                </button>
                <button
                  className={`pathway-tab ${activeTab === "comments" ? "active" : ""}`}
                  onClick={() => setActiveTab("comments")}
                >
                  {uiText.commentHistoryTab}
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
                {uiText.goToLessonLibrary}
              </Link>
            </div>
          </>
        )}

      </div>
    </main>
  );
};

export default MyPathway;

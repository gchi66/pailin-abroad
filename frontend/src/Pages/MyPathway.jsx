import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import PlanNotice from "../Components/PlanNotice";
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
  const [isPaidMember, setIsPaidMember] = useState(null);
  const [allLessons, setAllLessons] = useState([]);
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();
  const isFreePlanUser = Boolean(user) && isPaidMember === false;
  const lessonsCompletedCount = userStats?.lessons_completed ?? userProfile?.lessons_complete ?? 0;
  const isFirstVisit = lessonsCompletedCount <= 0;

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
    welcome: uiLang === "th" ? "ยินดีต้อนรับ" : "Welcome",
    user: uiLang === "th" ? "ผู้ใช้" : "User",
    plan: uiLang === "th" ? "แผน:" : "Plan:",
    fullAccess: uiLang === "th" ? "เข้าถึงเต็มรูปแบบ" : "Full Access",
    freeAccess: uiLang === "th" ? "ฟรี" : "Free",
    upgrade: uiLang === "th" ? "อัปเกรด" : "Upgrade",
    accountSettings: uiLang === "th" ? "การตั้งค่าบัญชี" : "Account Settings",
    lessonsComplete: uiLang === "th" ? "บทเรียนที่เสร็จสิ้น" : "Lessons Complete",
    levelsComplete: uiLang === "th" ? "ระดับที่เสร็จสิ้น" : "Levels Complete",

    // Navigation tabs
    myPathway: uiLang === "th" ? "เส้นทางของฉัน" : "My Pathway",
    completed: uiLang === "th" ? "เสร็จสิ้นแล้ว" : "Completed",
    myLikedLessonsTab: uiLang === "th" ? "บทเรียนที่ชอบ" : "My Liked Lessons",
    commentHistoryTab: uiLang === "th" ? "ประวัติความคิดเห็น" : "Comment History",

    // Footer
    goToFreeLessonLibrary: uiLang === "th" ? "ไปที่ไลบรารีบทเรียนฟรี →" : "Go to Free Lesson Library →",
    freePlanNoticeHeading: uiLang === "th" ? "คุณอยู่ในแผนฟรี" : "You're on our free plan.",
    freePlanNoticeCopy: uiLang === "th"
      ? "อัปเกรดเพื่อเข้าถึงคลังบทเรียนทั้งหมดของเรา!"
      : "Upgrade to enjoy access to our full lesson library!",
    ctaBecomeMember: uiLang === "th" ? "สมัครเป็นสมาชิก" : "BECOME A MEMBER",

    // Alt text and accessibility
    profileAvatar: uiLang === "th" ? "รูปโปรไฟล์" : "Profile Avatar",
    lessonCheckpoint: uiLang === "th" ? "จุดตรวจสอบบทเรียน" : "Lesson Checkpoint",
    notCompleted: uiLang === "th" ? "ยังไม่เสร็จสิ้น" : "Not completed",
    completedAlt: uiLang === "th" ? "เสร็จสิ้นแล้ว" : "Completed",
    locked: uiLang === "th" ? "ถูกล็อก" : "Locked",

    // Default fallbacks
    lessonTitle: uiLang === "th" ? "ชื่อบทเรียน" : "Lesson Title"
  };

  // Fetch user profile data from backend
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!user) {
        setLoading(false);
        setIsPaidMember(null);
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
          fetch(`${API_BASE_URL}/api/user/profile`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/completed-lessons`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/next-lesson`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/pathway-lessons`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/stats`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/comments`, { method: 'GET', headers })
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

  // Fetch paid status so we can surface free-plan UI
  useEffect(() => {
    const fetchPlanStatus = async () => {
      if (!user) {
        setIsPaidMember(null);
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("users")
          .select("is_paid")
          .eq("id", user.id)
          .single();

        if (error) {
          throw error;
        }

        setIsPaidMember(data?.is_paid ?? null);
      } catch (planError) {
        console.error("Error fetching plan status:", planError.message || planError);
        setIsPaidMember(null);
      }
    };

    fetchPlanStatus();
  }, [user]);

  // Fetch all lessons to determine first lesson in each level (for lock logic)
  useEffect(() => {
    const fetchAllLessons = async () => {
      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("id, stage, level, lesson_order")
          .order("stage", { ascending: true })
          .order("level", { ascending: true })
          .order("lesson_order", { ascending: true });

        if (error) {
          throw error;
        }

        setAllLessons(data || []);
      } catch (lessonsError) {
        console.error("Error fetching lessons for lock logic:", lessonsError.message || lessonsError);
        setAllLessons([]);
      }
    };

    fetchAllLessons();
  }, []);

  const firstLessonIds = useMemo(() => {
    if (!allLessons?.length) return [];

    const lessonsByLevel = {};

    allLessons.forEach((lesson) => {
      const levelKey = `${lesson.stage}-${lesson.level}`;
      if (!lessonsByLevel[levelKey]) {
        lessonsByLevel[levelKey] = [];
      }
      lessonsByLevel[levelKey].push(lesson);
    });

    return Object.values(lessonsByLevel)
      .map((levelLessons) => {
        const sorted = levelLessons.sort((a, b) => a.lesson_order - b.lesson_order);
        return sorted[0]?.id;
      })
      .filter(Boolean);
  }, [allLessons]);

  const shouldShowLock = (lesson) => {
    if (!user) {
      return true;
    }

    if (isPaidMember) {
      return false;
    }

    if (!lesson?.id || !firstLessonIds.length) {
      return false;
    }

    return !firstLessonIds.includes(lesson.id);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "pathway":
        return (
          <>
            {isFreePlanUser && (
              <div className="pathway-plan-notice-wrapper">
                <PlanNotice
                  heading={uiText.freePlanNoticeHeading}
                  subtext={uiText.freePlanNoticeCopy}
                  cta={{
                    label: uiText.ctaBecomeMember,
                    to: "/membership",
                  }}
                />
              </div>
            )}
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
                      {shouldShowLock(lesson) ? (
                        <img
                          src="/images/lock.webp"
                          alt={uiText.locked}
                          className="lesson-lock-icon pathway-lock-icon"
                        />
                      ) : (
                        <img
                          src="/images/CheckCircle.png"
                          alt={uiText.notCompleted}
                          className="pathway-checkmark"
                        />
                      )}
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
                  <h2 className="pathway-welcome">
                    {isFirstVisit ? uiText.welcome : uiText.welcomeBack} {userProfile?.name || uiText.user}
                  </h2>
                  <div className="pathway-account-info">
                    {/* <span className="pathway-level">Level: Upper Intermediate</span> */}
                    <div className="pathway-plan">
                      <span className="pathway-plan-text">
                        {uiText.plan} {isFreePlanUser ? uiText.freeAccess : uiText.fullAccess}
                      </span>
                      {isFreePlanUser && (
                        <Link to="/membership" className="pathway-plan-upgrade-link">
                          {uiText.upgrade}
                        </Link>
                      )}
                    </div>
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
              <Link to="/free-lessons" className="pathway-library-link">
                {uiText.goToFreeLessonLibrary}
              </Link>
            </div>
          </>
        )}

      </div>
    </main>
  );
};

export default MyPathway;

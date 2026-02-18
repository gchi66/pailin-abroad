import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import PlanNotice from "../Components/PlanNotice";
import { resolveAvatarUrl } from "../lib/resolveAvatarUrl";
import "../Styles/MyPathway.css";

const MyPathway = () => {
  const [activeTab, setActiveTab] = useState("pathway");
  const [userProfile, setUserProfile] = useState(null);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [pathwayLessons, setPathwayLessons] = useState([]);
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
  const isPaidUser = Boolean(user) && isPaidMember === true;
  const lessonsCompletedCount = userStats?.lessons_completed ?? userProfile?.lessons_complete ?? 0;
  const hasPreviousSignIn = Boolean(
    user?.last_sign_in_at &&
      user?.created_at &&
      user.last_sign_in_at !== user.created_at
  );
  const isFirstVisit = lessonsCompletedCount <= 0 && !hasPreviousSignIn;

  // Helper function to pick the right language content
  const pickLang = (en, th) => {
    if (uiLang === "th") {
      return th || en; // fallback to English if Thai is not available
    }
    return en || th; // fallback to Thai if English is not available
  };

  // Force a line break after the first word (e.g., "Lessons" + line break + "Complete")
  const withLineBreakAfterFirstWord = (label) => {
    if (!label?.trim()) return label;
    const words = label.split(" ");
    if (words.length <= 1) return label;

    return (
      <>
        {words[0]}
        <br />
        {words.slice(1).join(" ")}
      </>
    );
  };

  // UI translations
  const uiText = {
    // Progress section
    yourNextLesson: t("pathway.yourNextLesson", uiLang),
    checkpoint: t("pathway.checkpoint", uiLang),
    loading: t("pathway.loading", uiLang),

    // Tab content
    completedLessons: t("pathway.completedLessons", uiLang),
    noCompletedLessons: t("pathway.noCompletedLessons", uiLang),
    myLikedLessons: t("pathway.myLikedLessons", uiLang),
    likedLessonsPlaceholder: t("pathway.likedLessonsPlaceholder", uiLang),
    commentHistory: t("pathway.commentHistory", uiLang),
    noComments: t("pathway.noComments", uiLang),
    lessonNoLongerAvailable: t("pathway.lessonNoLongerAvailable", uiLang),
    pinnedComment: t("pathway.pinnedComment", uiLang),

    // Expand/collapse
    seeMore: t("pathway.seeMore", uiLang),
    seeLess: t("pathway.seeLess", uiLang),

    // Loading and error states
    loadingPathway: t("pathway.loadingPathway", uiLang),
    errorPrefix: t("pathway.errorPrefix", uiLang),
    noAuthToken: t("pathway.noAuthToken", uiLang),
    loadingImageAlt: t("pathway.loadingImageAlt", uiLang),
    loadingErrorTitle: t("pathway.loadingErrorTitle", uiLang),
    loadingErrorBody: t("pathway.loadingErrorBody", uiLang),

    // Header section
    welcomeBack: t("pathway.welcomeBack", uiLang),
    welcome: t("pathway.welcome", uiLang),
    user: t("pathway.user", uiLang),
    plan: t("pathway.plan", uiLang),
    fullAccess: t("pathway.fullAccess", uiLang),
    freeAccess: t("pathway.freeAccess", uiLang),
    upgrade: t("pathway.upgrade", uiLang),
    accountSettings: t("pathway.accountSettings", uiLang),
    lessonsComplete: t("pathway.lessonsComplete", uiLang),
    levelsComplete: t("pathway.levelsComplete", uiLang),

    // Navigation tabs
    myPathway: t("pathway.myPathway", uiLang),
    completed: t("pathway.completed", uiLang),
    myLikedLessonsTab: t("pathway.myLikedLessonsTab", uiLang),
    commentHistoryTab: t("pathway.commentHistoryTab", uiLang),

    // Footer
    goToFreeLessonLibrary: t("pathway.goToFreeLessonLibrary", uiLang),
    goToLessonLibrary: t("pathway.goToLessonLibrary", uiLang),
    freePlanNoticeHeading: t("pathway.freePlanNoticeHeading", uiLang),
    freePlanNoticeCopy: t("pathway.freePlanNoticeCopy", uiLang),
    ctaBecomeMember: t("pathway.ctaBecomeMember", uiLang),

    featuredResourcesTitle: t("pathway.featuredResourcesTitle", uiLang),
    featuredResourcesFree: t("pathway.featuredResourcesFree", uiLang),
    featuredResourcesMember: t("pathway.featuredResourcesMember", uiLang),
    featuredResourcesCta: t("pathway.featuredResourcesCta", uiLang),

    // Alt text and accessibility
    profileAvatar: t("pathway.profileAvatar", uiLang),
    lessonCheckpoint: t("pathway.lessonCheckpoint", uiLang),
    notCompleted: t("pathway.notCompleted", uiLang),
    completedAlt: t("pathway.completedAlt", uiLang),
    locked: t("pathway.locked", uiLang),

    // Default fallbacks
    lessonTitle: t("pathway.lessonTitle", uiLang),
    viewLabel: t("pathway.viewLabel", uiLang),
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
          pathwayResponse,
          statsResponse,
          commentsResponse
        ] = await Promise.all([
          fetch(`${API_BASE_URL}/api/user/profile`, { method: 'GET', headers }),
          fetch(`${API_BASE_URL}/api/user/completed-lessons`, { method: 'GET', headers }),
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
          setCompletedLessons(lessonsData.completed_lessons || []);
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

  const isLessonCompleted = (lessonId) => {
    return completedLessons.some((completed) => completed.lesson_id === lessonId);
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

            {/* Lessons List */}
            <div className="pathway-lessons-section">
              <div className="pathway-lesson-list pathway-lesson-list--pathway">
                {pathwayLessons.map((lesson, index) => {
                  const lessonCompleted = isLessonCompleted(lesson.id);
                  return (
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
                        ) : lessonCompleted ? (
                          <img
                            src="/images/filled-checkmark-lesson-complete.webp"
                            alt={uiText.completedAlt}
                            className="pathway-checkmark"
                          />
                        ) : null}
                      </div>
                    </Link>
                  );
                })}
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
                        <img
                          src="/images/pinned_comment_pin.png"
                          alt=""
                          aria-hidden="true"
                          className="pathway-comment-pin-icon"
                        />
                        <span>{uiText.pinnedComment}</span>
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

  if (loading || error) {
    return (
      <main className="pathway-loading-page">
        <div className={`pathway-loading-inner${error ? " is-error" : ""}`}>
          <img
            src="/images/characters/pailin_blue_circle_right.webp"
            alt={uiText.loadingImageAlt}
            className="pathway-loading-image"
          />
          {error && (
            <>
              <div className="pathway-loading-error-title">{uiText.loadingErrorTitle}</div>
              <div className="pathway-loading-error-body">{uiText.loadingErrorBody}</div>
            </>
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="pathway-main">
      <div className="pathway-container">
          <div className="pathway-header">
            <div className="pathway-header-left">
              <Link to="/profile" className="pathway-avatar-link">
                <img
                  src={
                    resolveAvatarUrl(
                      userProfile?.avatar_image ||
                      userProfile?.avatar ||
                      userProfile?.avatar_url ||
                      ""
                    ) || "/images/characters/pailin_blue_circle_right.webp"
                  }
                  alt={uiText.profileAvatar}
                  className="pathway-avatar"
                />
              </Link>
              <div className="pathway-user-info">
                <h2 className="pathway-welcome">
                  {isFirstVisit ? uiText.welcome : uiText.welcomeBack} {userProfile?.name || uiText.user}
                </h2>
                <div className="pathway-account-info">
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
                <span className="pathway-counter-label">{withLineBreakAfterFirstWord(uiText.lessonsComplete)}</span>
                <span className="pathway-counter-number">{userStats?.lessons_completed || 0}</span>
              </div>
              <div className="pathway-counter">
                <span className="pathway-counter-label">{withLineBreakAfterFirstWord(uiText.levelsComplete)}</span>
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

          {/* Mobile topbar (progress + tab selector) */}
          <div className="pathway-mobile-topbar">
            <div className="pathway-progress-section">
              <h3 className="pathway-section-title">
                <span className="pathway-next-lesson-label">{uiText.yourNextLesson}</span>
              </h3>
            </div>

            <div className="pathway-mobile-nav">
              <label className="pathway-mobile-nav-label" htmlFor="pathway-mobile-nav-select">
                {uiText.viewLabel}
              </label>
              <select
                id="pathway-mobile-nav-select"
                className="pathway-mobile-nav-select"
                value={activeTab}
                onChange={(e) => setActiveTab(e.target.value)}
                aria-label="Select pathway view"
              >
                <option value="pathway">{uiText.myPathway}</option>
                <option value="completed">{uiText.completed}</option>
                <option value="liked">{uiText.myLikedLessonsTab}</option>
                <option value="comments">{uiText.commentHistoryTab}</option>
              </select>
            </div>
          </div>

          {/* Tab Content */}
          <div className="pathway-content">
            {renderTabContent()}
          </div>

            {/* Footer Link */}
            <div className="pathway-footer">
              <Link
                to={isPaidUser ? "/lessons" : "/free-lessons"}
                className="pathway-library-link"
              >
                {isPaidUser ? uiText.goToLessonLibrary : uiText.goToFreeLessonLibrary}
              </Link>
            </div>

            {/* Featured Resources (mobile emphasis) */}
              <div className="pathway-featured-resources">
              <div className="pathway-featured-header">
                <h3 className="pathway-featured-title">{uiText.featuredResourcesTitle}</h3>
                <p className="pathway-featured-subtitle">
                  {isFreePlanUser ? uiText.featuredResourcesFree : uiText.featuredResourcesMember}
                </p>
              </div>
              <div className="pathway-featured-cards">
                <Link to="/exercise-bank" className="resource-card-compact">
                  <div className="resource-card-compact-media">
                    <img src="/images/resources_exercise_bank.webp" alt={t("resourcesPage.cards.exerciseBank.title", uiLang)} />
                  </div>
                  <div className="resource-card-compact-copy">
                    <h4 className="resource-card-compact-title">{t("resourcesPage.cards.exerciseBank.title", uiLang)}</h4>
                    <p className="resource-card-compact-desc">{t("resourcesPage.cards.exerciseBank.description", uiLang)}</p>
                  </div>
                </Link>
                <Link to="/topic-library" className="resource-card-compact">
                  <div className="resource-card-compact-media">
                    <img src="/images/resources_topic_library.webp" alt={t("resourcesPage.cards.topicLibrary.title", uiLang)} />
                  </div>
                  <div className="resource-card-compact-copy">
                    <h4 className="resource-card-compact-title">{t("resourcesPage.cards.topicLibrary.title", uiLang)}</h4>
                    <p className="resource-card-compact-desc">{t("resourcesPage.cards.topicLibrary.description", uiLang)}</p>
                  </div>
                </Link>
              </div>
              <div className="pathway-featured-cta">
                <Link to="/resources" className="pathway-featured-link">{uiText.featuredResourcesCta}</Link>
              </div>
            </div>
      </div>
    </main>
  );
};

export default MyPathway;

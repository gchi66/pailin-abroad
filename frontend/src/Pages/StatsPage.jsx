import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";
import ProtectedRoute from "../Components/ProtectedRoute";
import "../Styles/StatsPage.css";

const STAGE_ORDER = ["Beginner", "Intermediate", "Advanced", "Expert"];
const STAGE_RANK = STAGE_ORDER.reduce((acc, stage, index) => {
  acc[stage] = index;
  return acc;
}, {});

const StatsPage = () => {
  const { user } = useAuth();
  const { ui: uiLang } = useUiLang();
  const [userStats, setUserStats] = useState(null);
  const [completedLessons, setCompletedLessons] = useState([]);
  const [pathwayLessons, setPathwayLessons] = useState([]);
  const [userComments, setUserComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showAllCompleted, setShowAllCompleted] = useState(false);
  const [activeView, setActiveView] = useState("completed");

  const stageLabelMap = useMemo(() => ({
    Beginner: t("lessonsIndexPage.stages.beginner", uiLang),
    Intermediate: t("lessonsIndexPage.stages.intermediate", uiLang),
    Advanced: t("lessonsIndexPage.stages.advanced", uiLang),
    Expert: t("lessonsIndexPage.stages.expert", uiLang),
  }), [uiLang]);

  const pickLang = (en, th) => {
    if (uiLang === "th") {
      return th || en;
    }
    return en || th;
  };

  useEffect(() => {
    const fetchStatsPageData = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        const { data: { session } } = await supabaseClient.auth.getSession();

        if (!session?.access_token) {
          throw new Error("No authentication token found");
        }

        const headers = {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        };

        const [statsResponse, completedResponse, pathwayResponse, commentsResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/user/stats`, { method: "GET", headers }),
          fetch(`${API_BASE_URL}/api/user/completed-lessons`, { method: "GET", headers }),
          fetch(`${API_BASE_URL}/api/user/pathway-lessons`, { method: "GET", headers }),
          fetch(`${API_BASE_URL}/api/user/comments`, { method: "GET", headers }),
        ]);

        if (!statsResponse.ok) {
          throw new Error(`HTTP error! status: ${statsResponse.status}`);
        }

        const statsData = await statsResponse.json();
        setUserStats(statsData);

        if (completedResponse.ok) {
          const completedData = await completedResponse.json();
          setCompletedLessons(completedData.completed_lessons || []);
        }

        if (pathwayResponse.ok) {
          const pathwayData = await pathwayResponse.json();
          setPathwayLessons(pathwayData.pathway_lessons || []);
        }

        if (commentsResponse.ok) {
          const commentsData = await commentsResponse.json();
          setUserComments(commentsData.comments || []);
        }
      } catch (fetchError) {
        console.error("Error fetching stats page data:", fetchError);
        setError(fetchError.message);
      } finally {
        setLoading(false);
      }
    };

    fetchStatsPageData();
  }, [user]);

  const sortedCompletedLessons = useMemo(() => {
    return [...completedLessons].sort((a, b) => {
      const aDate = a.completed_at || a.updated_at || a.created_at || "";
      const bDate = b.completed_at || b.updated_at || b.created_at || "";

      if (aDate && bDate && aDate !== bDate) {
        return new Date(bDate).getTime() - new Date(aDate).getTime();
      }

      const aLesson = a.lessons || {};
      const bLesson = b.lessons || {};
      const aStageRank = STAGE_RANK[aLesson.stage] ?? -1;
      const bStageRank = STAGE_RANK[bLesson.stage] ?? -1;

      if (aStageRank !== bStageRank) return bStageRank - aStageRank;
      if ((aLesson.level ?? -1) !== (bLesson.level ?? -1)) return (bLesson.level ?? -1) - (aLesson.level ?? -1);
      return (bLesson.lesson_order ?? -1) - (aLesson.lesson_order ?? -1);
    });
  }, [completedLessons]);

  const currentStageAndLevel = useMemo(() => {
    const nextLesson = pathwayLessons[0];

    if (nextLesson?.stage && nextLesson?.level) {
      return {
        stage: nextLesson.stage,
        level: nextLesson.level,
      };
    }

    const latestCompleted = sortedCompletedLessons[0]?.lessons;
    if (latestCompleted?.stage && latestCompleted?.level) {
      return {
        stage: latestCompleted.stage,
        level: latestCompleted.level,
      };
    }

    return {
      stage: "Beginner",
      level: 1,
    };
  }, [pathwayLessons, sortedCompletedLessons]);

  const currentStageLabel = stageLabelMap[currentStageAndLevel.stage] || currentStageAndLevel.stage;
  const displayedCompletedLessons = showAllCompleted
    ? sortedCompletedLessons
    : sortedCompletedLessons.slice(0, 2);
  const viewOptions = [
    { value: "completed", label: t("pathway.completed", uiLang) },
    { value: "liked", label: t("pathway.myLikedLessonsTab", uiLang) },
    { value: "comments", label: t("pathway.commentHistoryTab", uiLang) },
  ];
  const activeViewLabel = viewOptions.find((option) => option.value === activeView)?.label || viewOptions[0].label;
  const handleViewChange = (event) => {
    setActiveView(event.target.value);
  };
  const renderViewSelect = () => (
    <div className="pathway-mobile-topbar stats-page-view-switcher">
      <div className="pathway-mobile-nav">
        <label className="pathway-mobile-nav-label" htmlFor="stats-page-view-select">
          {t("pathway.viewLabel", uiLang)}
        </label>
        <div className="stats-page-view-select-shell">
          <span className="stats-page-view-select-label" aria-hidden="true">
            {activeViewLabel}
          </span>
          <span className="stats-page-view-select-arrow" aria-hidden="true">
            <svg viewBox="0 0 12 8" focusable="false">
              <path d="M1 1.5L6 6.5L11 1.5" />
            </svg>
          </span>
          <select
            id="stats-page-view-select"
            className="pathway-mobile-nav-select stats-page-view-select"
            value={activeView}
            onChange={handleViewChange}
            aria-label="Select stats view"
          >
            {viewOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );

  const renderSelectedView = () => {
    if (activeView === "liked") {
      return (
        <section className="stats-completed-section">
          {renderViewSelect()}

          <div className="stats-placeholder">
            <h3 className="stats-placeholder-title">{t("pathway.myLikedLessons", uiLang)}</h3>
            <p className="stats-placeholder-copy">{t("pathway.likedLessonsPlaceholder", uiLang)}</p>
          </div>
        </section>
      );
    }

    if (activeView === "comments") {
      return (
        <section className="stats-completed-section">
          {renderViewSelect()}

          {userComments.length > 0 ? (
            <div className="stats-comments-list">
              {userComments.map((comment) => (
                <div key={comment.id} className="stats-comment-item">
                  <div className="stats-comment-header">
                    <div className="stats-comment-lesson-info">
                      {comment.lessons ? (
                        <Link to={`/lesson/${comment.lesson_id}`} className="stats-comment-lesson-link">
                          <span className="stats-comment-lesson-number">
                            {comment.lessons.level}.{comment.lessons.lesson_order}
                          </span>
                          <span className="stats-comment-lesson-copy">
                            <span className="stats-comment-lesson-title">
                              {pickLang(comment.lessons.title, comment.lessons.title_th)}
                            </span>
                            {(comment.lessons.focus || comment.lessons.focus_th) && (
                              <span className="stats-comment-lesson-focus">
                                {pickLang(comment.lessons.focus, comment.lessons.focus_th)}
                              </span>
                            )}
                          </span>
                        </Link>
                      ) : (
                        <span className="stats-comment-lesson-deleted">
                          {t("pathway.lessonNoLongerAvailable", uiLang)}
                        </span>
                      )}
                      <div className="stats-comment-date">
                        {new Date(comment.created_at).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </div>
                  </div>
                  <div className="stats-comment-body">{comment.body}</div>
                  {comment.pinned && (
                    <div className="stats-comment-pinned">
                      <img
                        src="/images/pinned_comment_pin.png"
                        alt=""
                        aria-hidden="true"
                        className="stats-comment-pin-icon"
                      />
                      <span>{t("pathway.pinnedComment", uiLang)}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="stats-placeholder">
              <p className="stats-placeholder-copy">{t("pathway.noComments", uiLang)}</p>
            </div>
          )}
        </section>
      );
    }

    return (
      <section className="stats-completed-section">
        {renderViewSelect()}

        <div className="stats-completed-list">
          {displayedCompletedLessons.map((progress) => (
            <Link
              key={progress.id}
              to={`/lesson/${progress.lesson_id}`}
              className="stats-completed-card"
            >
              <div className="stats-completed-main">
                <div className="stats-completed-number">
                  {progress.lessons?.level && progress.lessons?.lesson_order
                    ? `${progress.lessons.level}.${progress.lessons.lesson_order}`
                    : progress.lessons?.external_id || progress.lesson_id}
                </div>

                <div className="stats-completed-copy">
                  <div className="stats-completed-title">
                    {pickLang(progress.lessons?.title, progress.lessons?.title_th) || "Lesson"}
                  </div>
                  {(progress.lessons?.focus || progress.lessons?.focus_th) && (
                    <div className="stats-completed-focus">
                      {pickLang(progress.lessons?.focus, progress.lessons?.focus_th)}
                    </div>
                  )}
                </div>
              </div>

              <img
                src="/images/check_circle_blue.webp"
                alt=""
                aria-hidden="true"
                className="stats-completed-check"
              />
            </Link>
          ))}
        </div>

        {sortedCompletedLessons.length > 2 && (
          <div className="stats-view-more-row">
            <button
              type="button"
              className="stats-view-more-button"
              onClick={() => setShowAllCompleted((current) => !current)}
            >
              {showAllCompleted ? "View Less ▲" : "View More ▼"}
            </button>
          </div>
        )}
      </section>
    );
  };

  const content = (() => {
    if (loading) {
      return <div className="stats-page-loading">Loading your stats...</div>;
    }

    if (error) {
      return <div className="stats-page-error">We couldn&apos;t load your stats right now.</div>;
    }

    return (
      <>
        <Link to="/pathway" className="stats-page-back-link">
          <span className="stats-page-back-arrow" aria-hidden="true">←</span>
          <span>My Pathway</span>
        </Link>

        <header className="stats-page-header">
          <h1 className="stats-page-title">My Stats</h1>
        </header>

        <section className="stats-stage-card">
          <div className="stats-stage-kicker">Current Stage</div>
          <div className="stats-stage-row">
            <h2 className="stats-stage-name">{currentStageLabel}</h2>
            <div className="stats-stage-pill">Level {currentStageAndLevel.level}</div>
          </div>

          <div className="stats-summary-grid">
            <div className="stats-summary-card">
              <div className="stats-summary-number">{userStats?.lessons_completed ?? 0}</div>
              <div className="stats-summary-label">Lessons Complete</div>
            </div>
            <div className="stats-summary-card">
              <div className="stats-summary-number">{userStats?.levels_completed ?? 0}</div>
              <div className="stats-summary-label">Levels Complete</div>
            </div>
            <div className="stats-summary-card">
              <div className="stats-summary-number">{userStats?.daily_streak ?? 0}</div>
              <div className="stats-summary-label">Day Streak</div>
            </div>
          </div>
        </section>
        {renderSelectedView()}
      </>
    );
  })();

  return (
    <ProtectedRoute>
      <main className="stats-page">
        <div className="stats-page-shell">{content}</div>
      </main>
    </ProtectedRoute>
  );
};

export default StatsPage;

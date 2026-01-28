import React, { useState, useEffect } from "react";
import supabaseClient from "../supabaseClient";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import "../Styles/FreeLessonsIndex.css";
import PlanNotice from "../Components/PlanNotice";
import "../Styles/LessonsIndex.css";
import { API_BASE_URL } from "../config/api";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";

const FreeLessonsIndex = () => {
  const [lessonsByStage, setLessonsByStage] = useState({
    Beginner: [],
    Intermediate: [],
    Advanced: [],
  });
  const [completedLessons, setCompletedLessons] = useState([]);
  const [sessionUser, setSessionUser] = useState(null);
  const { ui: uiLang } = useUiLang();

  // Fetch all lessons and group by stage, filtering to only first lesson of each level
  useEffect(() => {
    const fetchAllLessons = async () => {
      try {
        const { data, error } = await supabaseClient
          .from("lessons")
          .select("*")
          .in("stage", ["Beginner", "Intermediate", "Advanced"])
          .order("stage", { ascending: true })
          .order("level", { ascending: true })
          .order("lesson_order", { ascending: true });

        if (error) throw error;

        // Group lessons by stage and filter to only first lesson of each level
        const grouped = {
          Beginner: [],
          Intermediate: [],
          Advanced: [],
        };

        // Group by stage first
        const stageGroups = {
          Beginner: [],
          Intermediate: [],
          Advanced: [],
        };

        data.forEach((lesson) => {
          if (stageGroups[lesson.stage]) {
            stageGroups[lesson.stage].push(lesson);
          }
        });

        // For each stage, get only the first lesson of each level
        Object.keys(stageGroups).forEach((stage) => {
          const lessonsByLevel = {};

          stageGroups[stage].forEach((lesson) => {
            if (!lessonsByLevel[lesson.level]) {
              lessonsByLevel[lesson.level] = [];
            }
            lessonsByLevel[lesson.level].push(lesson);
          });

          // Get the first lesson from each level
          Object.values(lessonsByLevel).forEach((levelLessons) => {
            const sortedLessons = levelLessons.sort((a, b) => a.lesson_order - b.lesson_order);
            if (sortedLessons.length > 0) {
              grouped[stage].push(sortedLessons[0]);
            }
          });
        });

        setLessonsByStage(grouped);
      } catch (error) {
        console.error("Error fetching lessons:", error.message);
      }
    };

    fetchAllLessons();
  }, []);

  const { user, loading: authLoading } = useAuth();
  const currentUser = user || sessionUser;

  useEffect(() => {
    const syncSessionUser = async () => {
      const { data } = await supabaseClient.auth.getSession();
      setSessionUser(data?.session?.user || null);
    };

    const { data: listener } = supabaseClient.auth.onAuthStateChange((_event, session) => {
      setSessionUser(session?.user || null);
    });

    syncSessionUser();

    return () => listener?.subscription?.unsubscribe();
  }, []);

  useEffect(() => {
    const fetchUserIfMissing = async () => {
      if (currentUser) return;
      const { data } = await supabaseClient.auth.getUser();
      setSessionUser(data?.user || null);
    };

    fetchUserIfMissing();
  }, [currentUser]);

  useEffect(() => {
    const fetchCompletedLessons = async () => {
      if (!currentUser) {
        setCompletedLessons([]);
        return;
      }

      try {
        const {
          data: { session },
        } = await supabaseClient.auth.getSession();

        if (!session?.access_token) {
          setCompletedLessons([]);
          return;
        }

        const response = await fetch(`${API_BASE_URL}/api/user/completed-lessons`, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          const data = await response.json();
          setCompletedLessons(data.completed_lessons || []);
        } else {
          setCompletedLessons([]);
        }
      } catch (error) {
        console.error("Error fetching completed lessons:", error);
        setCompletedLessons([]);
      }
    };

    fetchCompletedLessons();
  }, [currentUser]);

  const isLessonCompleted = (lessonId) =>
    completedLessons.some((completed) => completed.lesson_id === lessonId);

  // Component for a single lesson item
  const LessonItem = ({ lesson }) => {
    const isCheckpoint = (lesson.title || "").toLowerCase().includes("checkpoint");
    const showLock = !currentUser;
    const completed = isLessonCompleted(lesson.id);

    const content = (
      <div className="lesson-item-left">
        <div className="lesson-index-slot">
          {isCheckpoint ? (
            <img
              src="/images/black-checkmark-level-checkpoint.webp"
              alt={t("lessonsIndexPage.lessonCheckpoint", uiLang)}
              className="level-checkmark"
            />
          ) : (
            <span className="lesson-number" style={{ width: "auto" }}>
              {lesson.level}.{lesson.lesson_order}
            </span>
          )}
        </div>
        <div className="name-desc-container">
          <span className="lesson-name">{lesson.title}</span>
            {lesson.focus && (
              <span className="lesson-focus">{lesson.focus}</span>
            )}
        </div>
      </div>
    );

    const rightContent = showLock ? (
      <img
        src="/images/lock.webp"
        alt={t("lessonsIndexPage.locked", uiLang)}
        className="lesson-lock-icon"
      />
    ) : (
      <img
        src={
          completed
            ? "/images/filled-checkmark-lesson-complete.webp"
            : "/images/CheckCircle.png"
        }
        alt={
          completed
            ? t("lessonsIndexPage.completed", uiLang)
            : t("freeLessonsIndexPage.notCompleted", uiLang)
        }
        className={`checkmark-img ${completed ? "checkmark-completed" : ""}`}
      />
    );

    return (
      <Link to={`/lesson/${lesson.id}`} className="lesson-item free-lesson-link">
        {content}
        <div className="lesson-item-right">{rightContent}</div>
      </Link>
    );
  };

  // Component for a stage block
  const StageBlock = ({ title, lessons, comingSoon = false }) => {
    if (comingSoon) {
      return (
        <div className="free-stage-block coming-soon">
        <div className="free-stage-header">
          <span className="free-stage-title">{title}</span>
          <span className="coming-soon-badge">
            {t("freeLessonsIndexPage.comingSoon", uiLang)}
          </span>
        </div>
      </div>
      );
    }

    return (
      <div className="free-stage-block">
        <div className="free-stage-header">
          <span className="free-stage-title">{title}</span>
        </div>
        <div className="free-lesson-list">
          {lessons.map((lesson) => (
            <LessonItem
              key={lesson.id}
              lesson={lesson}
            />
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="free-lessons-index-page-container">
      <header className="lessons-index-page-header">
        <h1 className="page-header-text">{t("freeLessonsIndexPage.title", uiLang)}</h1>
        <p className="lessons-index-page-header-subtitle">
          {t("freeLessonsIndexPage.subtitle", uiLang)}
        </p>
      </header>

      {!currentUser && !authLoading ? (
        <div className="free-plan-notice-wrapper">
          <PlanNotice
            heading={t("freeLessonsIndexPage.noAccount.heading", uiLang)}
            subtext={[
              <>
                {t("freeLessonsIndexPage.noAccount.subtextPrefix", uiLang)}
                <em>{t("freeLessonsIndexPage.noAccount.subtextEm", uiLang)}</em>
                {t("freeLessonsIndexPage.noAccount.subtextSuffix", uiLang)}
              </>,
            ]}
            cta={{
              label: t("lessonsIndexPage.signUpFree", uiLang),
              to: "/signup",
            }}
            footerNote={
              <span>
                {t("lessonsIndexPage.footerNotePrefix", uiLang)}{" "}
                <a href="/try-lessons">{t("lessonsIndexPage.footerNoteLink", uiLang)}</a>{" "}
                {t("lessonsIndexPage.footerNoteSuffix", uiLang)}
              </span>
            }
          />
        </div>
      ) : currentUser ? (
        <div className="free-upgrade-message">
          <p>{t("freeLessonsIndexPage.freePlan.line1", uiLang)}</p>
          <p className="free-upgrade-actions">
            <Link to="/membership" className="upgrade-link upgrade-link--primary">
              {t("freeLessonsIndexPage.freePlan.upgradeLink", uiLang)}
            </Link>{" "}
            {t("freeLessonsIndexPage.freePlan.upgradeRest", uiLang)}
            <Link to="/lessons" className="upgrade-link upgrade-link--secondary">
              {t("freeLessonsIndexPage.freePlan.libraryLink", uiLang)}
            </Link>
            {t("freeLessonsIndexPage.freePlan.upgradeSuffix", uiLang)}
          </p>
        </div>
      ) : null}

      <div className="free-lessons-content">
        <section className="free-lessons-section">
          <StageBlock
            title={t("freeLessonsIndexPage.stages.beginner", uiLang)}
            lessons={lessonsByStage.Beginner}
          />
          <StageBlock
            title={t("freeLessonsIndexPage.stages.intermediate", uiLang)}
            lessons={lessonsByStage.Intermediate}
          />
          <StageBlock
            title={t("freeLessonsIndexPage.stages.advanced", uiLang)}
            lessons={lessonsByStage.Advanced}
          />
          <StageBlock title={t("freeLessonsIndexPage.stages.expert", uiLang)} comingSoon />
        </section>
      </div>
    </div>
  );
};

export default FreeLessonsIndex;

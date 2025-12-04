import React, { useState, useEffect } from "react";
import supabaseClient from "../supabaseClient";
import { Link } from "react-router-dom";
import { useAuth } from "../AuthContext";
import "../Styles/FreeLessonsIndex.css";
import PlanNotice from "../Components/PlanNotice";
import "../Styles/LessonsIndex.css";
import { API_BASE_URL } from "../config/api";

const FreeLessonsIndex = () => {
  const [lessonsByStage, setLessonsByStage] = useState({
    Beginner: [],
    Intermediate: [],
    Advanced: [],
  });
  const [completedLessons, setCompletedLessons] = useState([]);

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

  const { user } = useAuth();

  useEffect(() => {
    const fetchCompletedLessons = async () => {
      if (!user) {
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
  }, [user]);

  const isLessonCompleted = (lessonId) =>
    completedLessons.some((completed) => completed.lesson_id === lessonId);

  // Component for a single lesson item
  const LessonItem = ({ lesson }) => {
    const isCheckpoint = (lesson.title || "").toLowerCase().includes("checkpoint");
    const showLock = !user;
    const completed = isLessonCompleted(lesson.id);

    const content = (
      <div className="lesson-item-left">
        <div className="lesson-index-slot">
          {isCheckpoint ? (
            <img
              src="/images/black-checkmark-level-checkpoint.webp"
              alt="Lesson Checkpoint"
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
        alt="Locked"
        className="lesson-lock-icon"
      />
    ) : (
      <img
        src={
          completed
            ? "/images/filled-checkmark-lesson-complete.webp"
            : "/images/CheckCircle.png"
        }
        alt={completed ? "Completed" : "Not completed"}
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
            <span className="coming-soon-badge">Coming Soon</span>
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
        <h1 className="page-header-text">Free Lesson Library</h1>
        <p className="lessons-index-page-header-subtitle">
          Explore the lessons available to you on your free plan
        </p>
      </header>

      {!user ? (
        <div className="free-plan-notice-wrapper">
          <PlanNotice
            heading="Looks like you don't have an account."
            subtext={[
              <>
                Make a <em>free</em> account to access all the lessons below, along with access to our featured resources!
              </>,
            ]}
            cta={{
              label: "SIGN UP FOR FREE",
              to: "/signup",
            }}
            footerNote={
              <span>
                Not ready to create an account? <a href="/try-lessons">Click here</a> to try 4 free lessons, no sign-up required!
              </span>
            }
          />
        </div>
      ) : (
        <div className="free-upgrade-message">
          <p>Your free plan gives you access to the first lesson of each level!</p>
          <p className="free-upgrade-actions">
            <Link to="/membership" className="upgrade-link upgrade-link--primary">
              Upgrade
            </Link>{" "}
            to enjoy access to our{" "}
            <Link to="/lessons" className="upgrade-link upgrade-link--secondary">
              full lesson library
            </Link>
            .
          </p>
        </div>
      )}

      <div className="free-lessons-content">
        <section className="free-lessons-section">
          <StageBlock
            title="BEGINNER"
            lessons={lessonsByStage.Beginner}
          />
          <StageBlock
            title="INTERMEDIATE"
            lessons={lessonsByStage.Intermediate}
          />
          <StageBlock
            title="ADVANCED"
            lessons={lessonsByStage.Advanced}
          />
          <StageBlock title="EXPERT" comingSoon />
        </section>
      </div>
    </div>
  );
};

export default FreeLessonsIndex;

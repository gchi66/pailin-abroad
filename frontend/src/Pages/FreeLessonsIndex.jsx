import React, { useState, useEffect } from "react";
import supabaseClient from "../supabaseClient";
import { Link } from "react-router-dom";
import "../Styles/FreeLessonsIndex.css";

const FreeLessonsIndex = () => {
  const [lessonsByStage, setLessonsByStage] = useState({
    Beginner: [],
    Intermediate: [],
    Advanced: [],
  });

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

  // Component for a single lesson item
  const LessonItem = ({ lesson }) => {
    const isCheckpoint = (lesson.title || "").toLowerCase().includes("checkpoint");

    const content = (
      <div className="free-lesson-item">
        <div className="free-lesson-item-left">
          {isCheckpoint ? (
            <img
              src="/images/black-checkmark-level-checkpoint.webp"
              alt="Lesson Checkpoint"
              className="level-checkmark"
            />
          ) : (
            <span className="free-lesson-number">
              {lesson.level}.{lesson.lesson_order}
            </span>
          )}
          <div className="free-name-desc-container">
            <span className="free-lesson-name">{lesson.title}</span>
            {lesson.focus && (
              <span className="free-lesson-focus">{lesson.focus}</span>
            )}
          </div>
        </div>
      </div>
    );

    return (
      <Link to={`/lesson/${lesson.id}`} className="free-lesson-link">
        {content}
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
      <header className="free-lessons-index-page-header">
        <h1 className="free-page-header-text">FREE LESSON LIBRARY</h1>
        <p className="free-lessons-index-page-header-subtitle">
          Explore the lessons available to you on your free plan
        </p>
      </header>

      <div className="free-upgrade-message">
        <p>Your free plan gives you access to the first lesson of each level!</p>
        <p>
          <Link to="/membership" className="upgrade-link">
            Upgrade
          </Link>{" "}
          to enjoy access to our full lesson library.
        </p>
      </div>

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

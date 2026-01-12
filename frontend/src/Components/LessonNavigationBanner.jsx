import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import "../Styles/LessonNavigationBanner.css";
import supabase from "../supabaseClient";

const LessonNavigationBanner = ({
  prevLesson,
  nextLesson,
  currentLesson,
  onMarkComplete
}) => {
  const [isCompleted, setIsCompleted] = useState(false);

  // Load saved completion state for this lesson
  useEffect(() => {
    const fetchCompletion = async () => {
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user || !currentLesson) return;

      const { data, error } = await supabase
        .from("user_lesson_progress")
        .select("is_completed")
        .eq("user_id", user.id)
        .eq("lesson_id", currentLesson.id)
        .maybeSingle();

      if (!error && data?.is_completed) {
        setIsCompleted(true);
      } else {
        setIsCompleted(false);
      }
    };

    fetchCompletion();
  }, [currentLesson]);

  const handleMarkComplete = async () => {
    const newCompletedState = !isCompleted;
    setIsCompleted(newCompletedState);

    if (onMarkComplete) {
      onMarkComplete(newCompletedState);
    }

    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user || !currentLesson) return;

    try {
      const { error } = await supabase.from("user_lesson_progress").upsert(
        {
          user_id: user.id,
          lesson_id: currentLesson.id,
          is_completed: newCompletedState,
          completed_at: newCompletedState ? new Date().toISOString() : null,
        },
        {
          onConflict: "user_id,lesson_id", // Specify the conflict columns
        }
      );

      if (error) {
        console.error("Error updating completion state:", error);
        setIsCompleted(!newCompletedState); // Revert on error
      }
    } catch (error) {
      console.error("Error updating completion state:", error);
      setIsCompleted(!newCompletedState);
    }
  };

  const isCheckpointLesson = (lesson) => {
    if (!lesson) return false;
    const externalId =
      lesson.lesson_external_id ||
      lesson.external_id ||
      lesson.lessonId ||
      "";
    if (typeof externalId === "string" && externalId.endsWith(".chp")) {
      return true;
    }
    if (lesson.lesson_order === 0) {
      return true;
    }
    const title = (lesson.title_en || lesson.title || "").toLowerCase();
    return title.includes("checkpoint");
  };

  const isCurrentCheckpoint = isCheckpointLesson(currentLesson);

  // Extract lesson numbers from lesson_external_id (e.g., "1.1")
  const getCurrentLessonNumber = () => {
    return currentLesson?.lesson_external_id || currentLesson?.external_id || "X";
  };

  const getPrevLessonNumber = () => {
    return prevLesson?.lesson_order || "";
  };

  const getNextLessonNumber = () => {
    return nextLesson?.lesson_order || "";
  };

  const getNextLessonLabel = () => {
    if (!nextLesson) return "";
    if (isCheckpointLesson(nextLesson)) {
      return "CHECKPOINT";
    }
    const nextNumber = getNextLessonNumber();
    return nextNumber ? `LESSON ${nextNumber}` : "LESSON";
  };

  const getMarkCompleteLabel = () => "MARK LESSON COMPLETE";

  return (
    <section className="lesson-navigation-banner">
      {/* Left - Previous Lesson */}
      <div className="lesson-nav-left">
        {prevLesson ? (
          <Link
            to={`/lesson/${prevLesson.id}`}
            className="lesson-navigation-text prev"
          >
            ← LESSON {getPrevLessonNumber()}
          </Link>
        ) : (
          <div className="lesson-navigation-text disabled"></div>
        )}
      </div>

      {/* Center - Mark as Complete */}
      <div className="lesson-nav-center">
        <button
          className="lesson-mark-complete-button"
          onClick={handleMarkComplete}
        >
          <span className="lesson-mark-complete-text">
            {getMarkCompleteLabel()}
          </span>
          <img
            src={
              isCompleted
                ? "/images/check_circle_blue.webp"
                : "/images/CheckCircle.png"
            }
            alt={isCompleted ? "Completed" : "Mark as complete"}
            className="lesson-checkmark-icon"
          />
        </button>
      </div>

      {/* Right - Next Lesson */}
      <div className="lesson-nav-right">
        {nextLesson ? (
          <Link
            to={`/lesson/${nextLesson.id}`}
            className="lesson-navigation-text next"
          >
            {getNextLessonLabel()} →
          </Link>
        ) : (
          <div className="lesson-navigation-text disabled"></div>
        )}
      </div>
    </section>
  );
};

export default LessonNavigationBanner;

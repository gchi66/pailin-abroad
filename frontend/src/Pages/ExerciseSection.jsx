import React, { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import LessonLanguageToggle from "../Components/LessonLanguageToggle";
import FillBlankExercise from "../Components/ExerciseTypes/FillBlankExercise";
import MultipleChoiceExercise from "../Components/ExerciseTypes/MultipleChoiceExercise";
import SentenceTransformExercise from "../Components/ExerciseTypes/SentenceTransformExercise";
import { API_BASE_URL } from "../config/api";
import "../Styles/ExerciseBank.css";

const EXERCISE_COMPONENTS = {
  fill_blank: FillBlankExercise,
  sentence_transform: SentenceTransformExercise,
  multiple_choice: MultipleChoiceExercise,
};

const EXERCISE_LABELS = {
  fill_blank: "Fill in the Blank",
  sentence_transform: "Sentence Transform",
  multiple_choice: "Multiple Choice",
};

const ExerciseSection = () => {
  const { categorySlug, sectionSlug } = useParams();
  const [section, setSection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [contentLang, setContentLang] = useState("en");
  const [expandedIds, setExpandedIds] = useState(() => new Set());

  useEffect(() => {
    if (!categorySlug || !sectionSlug) return;
    let isMounted = true;
    const controller = new AbortController();

    const fetchSection = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${API_BASE_URL}/api/exercise-bank/section/${categorySlug}/${sectionSlug}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Section not found");
        }
        const data = await response.json();
        if (!isMounted) {
          return;
        }
        setSection(data.section || null);
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("Error fetching exercise section:", err);
        if (isMounted) {
          setError(err.message || "Unable to load this section.");
          setSection(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchSection();
    return () => {
      isMounted = false;
      controller.abort();
    };
  }, [categorySlug, sectionSlug]);

  useEffect(() => {
    // reset expanded state when section changes
    setExpandedIds(new Set());
  }, [section]);

  const toggleExercise = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const localizedExercises = useMemo(() => {
    if (!Array.isArray(section?.exercises)) {
      return [];
    }
    const useThai = contentLang === "th";
    return section.exercises.map((exercise) => {
      const sourceItems =
        useThai && Array.isArray(exercise.items_th) && exercise.items_th.length
          ? exercise.items_th
          : exercise.items || [];
      const localizedItems = sourceItems.map((item) => ({ ...item }));
      return {
        ...exercise,
        title: useThai ? exercise.title_th || exercise.title : exercise.title,
        prompt: useThai ? exercise.prompt_th || exercise.prompt : exercise.prompt,
        paragraph: useThai ? exercise.paragraph_th || exercise.paragraph : exercise.paragraph,
        items: localizedItems,
      };
    });
  }, [section, contentLang]);

  const renderWithBreaks = (text = "") => {
    if (!text) return null;
    const parts = text.split("\n");
    return parts.map((line, index) => (
      <span key={index}>
        {line}
        {index < parts.length - 1 && <br />}
      </span>
    ));
  };

  if (loading) {
    return (
      <div className="exercise-section-page-container">
        <header className="exercise-bank-page-header">
          <div className="exercise-bank-header-content">
            <h1 className="exercise-bank-page-header-text">Exercise Bank</h1>
            <p className="exercise-bank-page-subtitle">
              Additional practice exercises for those difficult grammar topics.
            </p>
          </div>
        </header>
        <div className="exercise-section-content">
          <div className="exercise-bank-placeholder">
            <p>Loading section...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !section) {
    return (
      <div className="exercise-section-page-container">
        <header className="exercise-bank-page-header">
          <div className="exercise-bank-header-content">
            <h1 className="exercise-bank-page-header-text">Exercise Bank</h1>
            <p className="exercise-bank-page-subtitle">
              Additional practice exercises for those difficult grammar topics.
            </p>
          </div>
        </header>
        <div className="exercise-section-content">
          <div className="exercise-bank-placeholder">
            <p>{error || "We couldn't find that section."}</p>
            <Link to="/exercise-bank" className="exercise-section-back-link">
              ← Back to Exercise Bank
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="exercise-section-page-container">
      <header className="exercise-bank-page-header">
        <div className="exercise-bank-header-content">
          <h1 className="exercise-bank-page-header-text">Exercise Bank</h1>
          <p className="exercise-bank-page-subtitle">
            Additional practice exercises for those difficult grammar topics.
          </p>
        </div>
      </header>

      <div className="exercise-section-content">
        <div className="exercise-section-nav">
          <Link to="/exercise-bank" className="exercise-section-back-link">
            ← Back to Exercise Bank
          </Link>
          <div className="exercise-section-nav-actions">
            <span className="exercise-section-category-chip">{section.category_label}</span>
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </div>

        <div className="exercise-section-summary">
          <h2 className="exercise-section-title">{section.section}</h2>
          {section.section_th && <p className="exercise-section-title-th">{section.section_th}</p>}
          <p className="exercise-section-meta">
            {localizedExercises.length} exercise{localizedExercises.length === 1 ? "" : "s"} in this section
          </p>
        </div>

        <div className="exercise-section-list">
          {localizedExercises.map((exercise, idx) => {
            const exerciseId = exercise.id || `${exercise.title}-${idx}`;
            const isOpen = expandedIds.has(exerciseId);
            const exerciseType = (exercise.exercise_type || "").toLowerCase();
            const ExerciseComponent = EXERCISE_COMPONENTS[exerciseType];
            const exerciseLabel = EXERCISE_LABELS[exerciseType] || exercise.exercise_type || "Exercise";

            return (
              <div
                key={exerciseId}
                className={`exercise-section-item ${isOpen ? "open" : ""}`}
              >
                <button
                  type="button"
                  className="exercise-section-item-toggle"
                  onClick={() => toggleExercise(exerciseId)}
                >
                  <div className="exercise-section-item-heading">
                    <h3>{exercise.title || "Exercise"}</h3>
                    <span className="exercise-section-item-type">{exerciseLabel}</span>
                  </div>
                  <span className="exercise-section-item-icon">{isOpen ? "−" : "+"}</span>
                </button>
                {isOpen && (
                  <div className="exercise-section-item-body">
                    {ExerciseComponent ? (
                      <ExerciseComponent
                        key={`${exerciseId}-${contentLang}`}
                        exercise={exercise}
                        images={{}}
                        audioIndex={{}}
                        sourceType="bank"
                        exerciseId={exercise.id}
                        contentLang={contentLang}
                      />
                    ) : (
                      <FallbackExercise exercise={exercise} renderWithBreaks={renderWithBreaks} />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default ExerciseSection;

function FallbackExercise({ exercise, renderWithBreaks }) {
  return (
    <div className="exercise-fallback">
      {exercise.prompt && (
        <p className="exercise-fallback-prompt">{renderWithBreaks(exercise.prompt)}</p>
      )}
      {Array.isArray(exercise.items) && exercise.items.length > 0 && (
        <ul className="exercise-fallback-list">
          {exercise.items.map((item, index) => (
            <li key={item.number || index} className="exercise-fallback-item">
              {item.number ? `${item.number}. ` : ""}
              {renderWithBreaks(item.text || "")}
            </li>
          ))}
        </ul>
      )}
      {!exercise.items?.length && <p>This exercise type is coming soon.</p>}
    </div>
  );
}

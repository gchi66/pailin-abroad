import React, { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import LessonLanguageToggle from "../Components/LessonLanguageToggle";
import FillBlankExercise from "../Components/ExerciseTypes/FillBlankExercise";
import MultipleChoiceExercise from "../Components/ExerciseTypes/MultipleChoiceExercise";
import SentenceTransformExercise from "../Components/ExerciseTypes/SentenceTransformExercise";
import { API_BASE_URL } from "../config/api";
import Breadcrumbs from "../Components/Breadcrumbs";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { useStickyLessonToggle } from "../StickyLessonToggleContext";
import "../Styles/ExerciseBank.css";

const EXERCISE_COMPONENTS = {
  fill_blank: FillBlankExercise,
  sentence_transform: SentenceTransformExercise,
  multiple_choice: MultipleChoiceExercise,
};

const ExerciseSection = () => {
  const { categorySlug, sectionSlug } = useParams();
  const [section, setSection] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [contentLang, setContentLang] = useState("en");
  const [expandedIds, setExpandedIds] = useState(() => new Set());
  const { ui: uiLang } = useUiLang();
  const toggleSlotRef = useRef(null);
  const {
    registerLessonToggle,
    unregisterLessonToggle,
    updateContentLang: updateStickyContentLang,
    setShowStickyToggle,
  } = useStickyLessonToggle();

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
          setError(err.message || t("exerciseSection.notFound", uiLang));
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

  useEffect(() => {
    registerLessonToggle({ contentLang, setContentLang });
    return () => {
      unregisterLessonToggle();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerLessonToggle, unregisterLessonToggle, setContentLang]);

  useEffect(() => {
    updateStickyContentLang(contentLang);
  }, [contentLang, updateStickyContentLang]);

  useEffect(() => {
    // Only set up observer after section has loaded
    if (!section) return undefined;

    const node = toggleSlotRef.current;
    if (!node || typeof window === "undefined") return undefined;

    let observer = null;

    const computeMargin = () => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--navbar-height");
      const parsed = parseFloat(raw);
      const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
      return `-${navbarHeight}px 0px 0px 0px`;
    };

    const setupObserver = () => {
      if (observer) observer.disconnect();
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            setShowStickyToggle(!entry.isIntersecting);
          });
        },
        { threshold: 0, rootMargin: computeMargin() }
      );
      observer.observe(node);
    };

    setupObserver();
    window.addEventListener("resize", setupObserver);

    return () => {
      window.removeEventListener("resize", setupObserver);
      if (observer) observer.disconnect();
      setShowStickyToggle(false);
    };
  }, [section, setShowStickyToggle]);

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

  const sectionTitle =
    contentLang === "th" ? section?.section_th || section?.section || "" : section?.section || "";

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
      <main className="page-loading-page">
        <div className="page-loading-inner">
          <img
            src="/images/characters/pailin_blue_circle_right.webp"
            alt={t("exerciseSection.loadingImageAlt", uiLang)}
            className="page-loading-image"
          />
        </div>
      </main>
    );
  }

  if (error || !section) {
    return (
      <main className="page-loading-page">
        <div className="page-loading-inner is-error">
          <img
            src="/images/characters/pailin_blue_circle_right.webp"
            alt={t("exerciseSection.loadingImageAlt", uiLang)}
            className="page-loading-image"
          />
          <div className="page-loading-error-title">
            {t("exerciseSection.loadingErrorTitle", uiLang)}
          </div>
          <div className="page-loading-error-body">
            {t("exerciseSection.loadingErrorBody", uiLang)}
          </div>
        </div>
      </main>
    );
  }

  return (
    <div className="exercise-section-page-container">
      <header className="exercise-bank-page-header">
        <div className="exercise-bank-header-content">
          <h1 className="exercise-bank-page-header-text">{t("exerciseSection.title", uiLang)}</h1>
          <p className="exercise-bank-page-subtitle">
            {t("exerciseSection.subtitle", uiLang)}
          </p>
        </div>
      </header>

      <div className="exercise-section-content">
        <div className="exercise-section-nav">
          <Breadcrumbs
            className="exercise-section-breadcrumbs"
            items={[
              { label: t("exerciseSection.resourcesLabel", uiLang), to: "/resources" },
              { label: t("exerciseSection.title", uiLang), to: "/exercise-bank" },
              { label: section.section || t("exerciseSection.sectionLabel", uiLang) },
            ]}
          />
          <div className="exercise-section-nav-actions">
            <span className="exercise-section-category-chip">{section.category_label}</span>
            <div ref={toggleSlotRef} className="exercise-section-toggle-slot">
              <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
            </div>
          </div>
        </div>

        <div className="exercise-section-summary-wrap">
          <div className="exercise-section-summary">
            <h2 className="exercise-section-title">{sectionTitle}</h2>
            <p className="exercise-section-meta">
              {localizedExercises.length}{" "}
              {localizedExercises.length === 1
                ? t("exerciseSection.exercisesCount.singular", uiLang)
                : t("exerciseSection.exercisesCount.plural", uiLang)}
            </p>
          </div>
        </div>

        <div className="exercise-section-box">
          <div className="exercise-section-list">
            {localizedExercises.map((exercise, idx) => {
              const exerciseId = exercise.id || `${exercise.title}-${idx}`;
              const isOpen = expandedIds.has(exerciseId);
              const exerciseType = (exercise.exercise_type || "").toLowerCase();
              const ExerciseComponent = EXERCISE_COMPONENTS[exerciseType];

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
                          showTitle={false}
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

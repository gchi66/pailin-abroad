import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import "../Styles/ExerciseBank.css";

const ExerciseBank = () => {
  const [sections, setSections] = useState([]);
  const [categories, setCategories] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [loadingSections, setLoadingSections] = useState(true);
  const [loadingFeatured, setLoadingFeatured] = useState(true);
  const [error, setError] = useState(null);
  const [featuredError, setFeaturedError] = useState(null);
  const [activeView, setActiveView] = useState("featured");
  const [selectedCategory, setSelectedCategory] = useState("");

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    const fetchSections = async () => {
      try {
        setLoadingSections(true);
        const response = await fetch("/api/exercise-bank/sections", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Failed to load exercise sections");
        }
        const data = await response.json();
        if (!isMounted) return;
        setSections(data.sections || []);
        setCategories(data.categories || []);
        setError(null);
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("Error fetching exercise sections:", err);
        if (isMounted) {
          setError(err.message || "Unable to load exercise sections.");
        }
      } finally {
        if (isMounted) {
          setLoadingSections(false);
        }
      }
    };

    fetchSections();
    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    const fetchFeatured = async () => {
      try {
        setLoadingFeatured(true);
        setFeaturedError(null);
        const response = await fetch("/api/exercise-bank/featured", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Failed to load featured exercises");
        }
        const data = await response.json();
        if (!isMounted) return;
        setFeatured(data.featured || []);
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error("Error fetching featured exercises:", err);
        if (isMounted) {
          setFeaturedError(err.message || "Unable to load featured exercises.");
        }
      } finally {
        if (isMounted) {
          setLoadingFeatured(false);
        }
      }
    };

    fetchFeatured();
    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!selectedCategory && categories.length > 0) {
      setSelectedCategory(categories[0].category_slug);
    }
  }, [categories, selectedCategory]);

  const sectionsForSelectedCategory = useMemo(() => {
    if (!selectedCategory) return [];
    return sections.filter((section) => section.category_slug === selectedCategory);
  }, [selectedCategory, sections]);

  const featuredBySection = useMemo(() => {
    const map = new Map();
    featured.forEach((exercise) => {
      const key = `${exercise.category_slug}/${exercise.section_slug}`;
      if (!map.has(key)) {
        map.set(key, {
          category: exercise.category,
          category_label: exercise.category_label,
          category_slug: exercise.category_slug,
          section: exercise.section,
          section_th: exercise.section_th,
          section_slug: exercise.section_slug,
          exercises: [],
        });
      }
      map.get(key).exercises.push(exercise);
    });
    return Array.from(map.values());
  }, [featured]);

  const isLoading = loadingSections;

  return (
    <div className="exercise-bank-page-container">
      <header className="exercise-bank-page-header">
        <div className="exercise-bank-header-content">
          <h1 className="exercise-bank-page-header-text">EXERCISE BANK</h1>
          <p className="exercise-bank-page-subtitle">
            Additional practice exercises for those difficult grammar topics.
          </p>
        </div>
      </header>

      <div className="exercise-bank-content">
        <div className="exercise-bank-toggle-buttons">
          <button
            type="button"
            className={`section-btn ${activeView === "featured" ? "active" : ""}`}
            onClick={() => setActiveView("featured")}
          >
            FEATURED EXERCISES
          </button>
          <button
            type="button"
            className={`section-btn ${activeView === "categories" ? "active" : ""}`}
            onClick={() => setActiveView("categories")}
          >
            VIEW BY CATEGORY
          </button>
        </div>

        {activeView === "categories" && categories.length > 0 && (
          <div className="exercise-bank-category-buttons">
            {categories.map((category) => (
              <button
                key={category.category_slug}
                type="button"
                className={`exercise-bank-category-btn ${
                  selectedCategory === category.category_slug ? "active" : ""
                }`}
                onClick={() => setSelectedCategory(category.category_slug)}
              >
                {category.category_label}
              </button>
            ))}
          </div>
        )}

        <div className="exercise-bank-main">
          {isLoading && (
            <div className="exercise-bank-placeholder">
              <p>Loading exercise bank...</p>
            </div>
          )}

          {!isLoading && error && (
            <div className="exercise-bank-placeholder">
              <p>{error}</p>
            </div>
          )}

          {!isLoading && !error && activeView === "featured" && (
            <>
              {loadingFeatured && (
                <div className="exercise-bank-placeholder">
                  <p>Loading featured exercises...</p>
                </div>
              )}
              {!loadingFeatured && featuredError && (
                <div className="exercise-bank-placeholder">
                  <p>{featuredError}</p>
                </div>
              )}
              {!loadingFeatured && !featuredError && featuredBySection.length === 0 && (
                <div className="exercise-bank-placeholder">
                  <p>No featured exercises yet. Check back soon!</p>
                </div>
              )}
              {!loadingFeatured && !featuredError && featuredBySection.length > 0 && (
                <div className="exercise-bank-card-grid">
                  {featuredBySection.map((group) => (
                    <div key={`${group.category_slug}-${group.section_slug}`} className="exercise-bank-card">
                      <div className="exercise-bank-card-header">
                        <div className="exercise-bank-card-section">
                          <h3>{group.section}</h3>
                          {group.section_th && <p className="exercise-bank-card-section-th">{group.section_th}</p>}
                        </div>
                        <div className="exercise-bank-card-meta">
                          <span className="exercise-bank-category-chip">{group.category_label}</span>
                          <Link
                            className="exercise-bank-card-link"
                            to={`/exercise-bank/${group.category_slug}/${group.section_slug}`}
                          >
                            View section →
                          </Link>
                        </div>
                      </div>
                      <div className="exercise-bank-card-body">
                        <ul className="exercise-bank-featured-list">
                          {group.exercises.map((exercise) => (
                            <li key={exercise.id} className="exercise-bank-featured-item">
                              <span className="exercise-bank-featured-title">{exercise.title}</span>
                              {exercise.title_th && (
                                <span className="exercise-bank-featured-title-th">{exercise.title_th}</span>
                              )}
                              <span className="exercise-bank-featured-type">{exercise.exercise_type}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {!isLoading && !error && activeView === "categories" && (
            <>
              {sectionsForSelectedCategory.length === 0 ? (
                <div className="exercise-bank-placeholder">
                  <p>
                    {categories.length === 0
                      ? "We’re loading categories for the exercise bank. Check back soon!"
                      : "Pick a category to see the available sections."}
                  </p>
                </div>
              ) : (
                <div className="exercise-bank-card-grid">
                  {sectionsForSelectedCategory.map((section) => (
                    <div key={`${section.category_slug}-${section.section_slug}`} className="exercise-bank-card">
                      <div className="exercise-bank-card-header">
                        <div className="exercise-bank-card-section">
                          <h3>{section.section}</h3>
                          {section.section_th && (
                            <p className="exercise-bank-card-section-th">{section.section_th}</p>
                          )}
                        </div>
                        <div className="exercise-bank-card-meta">
                          <span className="exercise-bank-category-chip">{section.category_label}</span>
                          {section.featured_count > 0 && (
                            <span className="exercise-bank-featured-count">
                              {section.featured_count} featured
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="exercise-bank-card-body">
                        <p className="exercise-bank-card-copy">
                          {section.exercise_count} exercise{section.exercise_count === 1 ? "" : "s"} in this section.
                        </p>
                        <Link
                          className="exercise-bank-card-link"
                          to={`/exercise-bank/${section.category_slug}/${section.section_slug}`}
                        >
                          Explore section →
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ExerciseBank;

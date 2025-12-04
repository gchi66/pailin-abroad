import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import "../Styles/ExerciseBank.css";

const CATEGORY_OPTIONS = [
  { slug: "verbs-and-tenses", label: "Verbs & Tenses" },
  { slug: "nouns-and-articles", label: "Nouns & Articles" },
  { slug: "pronouns", label: "Pronouns" },
  { slug: "adjectives", label: "Adjectives" },
  { slug: "conjunctions", label: "Conjunctions" },
  { slug: "prepositions", label: "Prepositions" },
  { slug: "other-concepts", label: "Other Concepts" },
  { slug: "all", label: "View All" },
];

const CATEGORY_ORDER_INDEX = CATEGORY_OPTIONS.reduce((acc, option, index) => {
  acc[option.slug] = index;
  return acc;
}, {});

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
  const [isCategoryMenuOpen, setIsCategoryMenuOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const categoryMenuRef = useRef(null);

  useEffect(() => {
    let isMounted = true;
    const controller = new AbortController();

    const fetchSections = async () => {
      try {
        setLoadingSections(true);
        const response = await fetch(`${API_BASE_URL}/api/exercise-bank/sections`, {
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
        const response = await fetch(`${API_BASE_URL}/api/exercise-bank/featured`, {
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
      const preferred = CATEGORY_OPTIONS.find(
        (option) =>
          option.slug !== "all" && categories.some((cat) => cat.category_slug === option.slug)
      );
      const fallback = categories[0];
      setSelectedCategory((preferred && preferred.slug) || (fallback && fallback.category_slug) || "all");
    }
  }, [categories, selectedCategory]);

  useEffect(() => {
    if (!isCategoryMenuOpen) return;

    const handleClickOutside = (event) => {
      if (categoryMenuRef.current && !categoryMenuRef.current.contains(event.target)) {
        setIsCategoryMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isCategoryMenuOpen]);

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

  const normalizedSearch = searchTerm.trim().toLowerCase();

  const orderedCategoryOptions = useMemo(() => {
    const known = CATEGORY_OPTIONS.filter(
      (option) => option.slug === "all" || categories.some((cat) => cat.category_slug === option.slug)
    );
    const extras = categories
      .filter((cat) => !CATEGORY_OPTIONS.some((option) => option.slug === cat.category_slug))
      .map((cat) => ({
        slug: cat.category_slug,
        label: cat.category_label || cat.category || cat.category_slug,
      }));

    return [...known, ...extras];
  }, [categories]);

  const filteredSectionsForSelectedCategory = useMemo(() => {
    if (!selectedCategory) return [];

    const inCategory =
      selectedCategory === "all"
        ? sections
        : sections.filter((section) => section.category_slug === selectedCategory);

    if (!normalizedSearch) return inCategory;

    return inCategory.filter((section) => {
      const haystack = [
        section.section,
        section.section_th,
        section.category_label,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedSearch);
    });
  }, [normalizedSearch, sections, selectedCategory]);

  const sortedSections = useMemo(() => {
    const sorted = [...filteredSectionsForSelectedCategory];
    sorted.sort((a, b) => {
      const orderA = CATEGORY_ORDER_INDEX[a.category_slug] ?? 999;
      const orderB = CATEGORY_ORDER_INDEX[b.category_slug] ?? 999;
      if (orderA !== orderB) return orderA - orderB;
      return (a.section || "").localeCompare(b.section || "");
    });
    return sorted;
  }, [filteredSectionsForSelectedCategory]);

  const filteredFeaturedBySection = useMemo(() => {
    if (!normalizedSearch) return featuredBySection;

    return featuredBySection
      .map((group) => {
        const filteredExercises = group.exercises.filter((exercise) => {
          const haystack = [
            exercise.title,
            exercise.title_th,
            exercise.prompt,
            exercise.prompt_th,
            exercise.exercise_type,
            group.category_label,
            group.section,
            group.section_th,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase();
          return haystack.includes(normalizedSearch);
        });

        const groupMatches =
          filteredExercises.length > 0 ||
          [group.section, group.section_th, group.category_label]
            .filter(Boolean)
            .join(" ")
            .toLowerCase()
            .includes(normalizedSearch);

        if (!groupMatches) {
          return null;
        }

        return {
          ...group,
          exercises: filteredExercises.length > 0 ? filteredExercises : group.exercises,
        };
      })
      .filter(Boolean);
  }, [featuredBySection, normalizedSearch]);

  const isLoading = loadingSections;

  const handleCategorySelect = (slug) => {
    setSelectedCategory(slug);
    setActiveView("categories");
    setIsCategoryMenuOpen(false);
  };

  return (
    <div className="exercise-bank-page-container">
      <header className="exercise-bank-page-header">
        <div className="exercise-bank-header-content">
          <h1 className="exercise-bank-page-header-text">Exercise Bank</h1>
          <p className="exercise-bank-page-subtitle">
            Additional practice exercises for those difficult grammar topics.
          </p>
        </div>
      </header>

      <div className="exercise-bank-content">
        <div className="exercise-bank-toolbar-wrapper">
          <div className="exercise-bank-toolbar">
            <div className="exercise-bank-toolbar-left">
              <div className="exercise-bank-filters">
                <button
                  type="button"
                  className={`exercise-bank-filter-button ${activeView === "featured" ? "active" : ""}`}
                  onClick={() => {
                    setActiveView("featured");
                    setIsCategoryMenuOpen(false);
                  }}
                >
                  Featured Exercises
                </button>
                <div className="exercise-bank-category-dropdown" ref={categoryMenuRef}>
                  <button
                    type="button"
                    className={`exercise-bank-filter-button ${activeView === "categories" ? "active" : ""}`}
                    onClick={() => {
                      setActiveView("categories");
                      setIsCategoryMenuOpen((prev) => !prev);
                    }}
                  >
                    View by Category
                    <span className="exercise-bank-caret" aria-hidden="true">▾</span>
                  </button>
                  {isCategoryMenuOpen && (
                    <div className="exercise-bank-category-menu">
                      {orderedCategoryOptions.map((option) => (
                        <button
                          key={option.slug}
                          type="button"
                          className={`exercise-bank-category-menu-item ${
                            selectedCategory === option.slug ? "active" : ""
                          }`}
                          onClick={() => handleCategorySelect(option.slug)}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="exercise-bank-toolbar-right">
              <div className="exercise-bank-search">
                <label htmlFor="exercise-bank-search-input" className="sr-only">
                  Search exercises
                </label>
                <input
                  id="exercise-bank-search-input"
                  type="search"
                  placeholder="Search exercises"
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                />
                <span className="exercise-bank-search-icon" aria-hidden="true">
                  <img src="/images/search_icon.webp" alt="" />
                </span>
              </div>
            </div>
          </div>
        </div>

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
              {!loadingFeatured && !featuredError && filteredFeaturedBySection.length === 0 && (
                <div className="exercise-bank-placeholder">
                  <p>{normalizedSearch ? "No exercises match your search." : "No featured exercises yet. Check back soon!"}</p>
                </div>
              )}
              {!loadingFeatured && !featuredError && filteredFeaturedBySection.length > 0 && (
                <div className="exercise-bank-card-grid">
                  {filteredFeaturedBySection.map((group) => (
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
              {sortedSections.length === 0 ? (
                <div className="exercise-bank-placeholder">
                  <p>
                    {normalizedSearch
                      ? "No exercises match your search."
                      : categories.length === 0
                        ? "We’re loading categories for the exercise bank. Check back soon!"
                        : selectedCategory === "all"
                          ? "No exercises available yet."
                          : "No exercises available in this category yet."}
                  </p>
                </div>
              ) : (
                <div className="exercise-bank-card-grid">
                  {sortedSections.map((section) => (
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

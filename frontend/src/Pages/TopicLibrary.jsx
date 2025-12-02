import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";
import "../Styles/TopicLibrary.css";

const TopicLibrary = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterMode, setFilterMode] = useState("featured");
  const [searchTerm, setSearchTerm] = useState("");
  const { ui: uiLang } = useUiLang();
  const withUi = useWithUi();

  useEffect(() => {
    const controller = new AbortController();
    let isActive = true;
    const fetchTopics = async () => {
      try {
        if (isActive) {
          setLoading(true);
          setError(null);
        }
        const response = await fetch(`${API_BASE_URL}/api/topic-library?lang=${uiLang}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error('Failed to fetch topics');
        }
        const data = await response.json();
        if (isActive) {
          setTopics(data.topics || []);
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          console.error('Error fetching topics:', err);
          if (isActive) {
            setError(err.message);
          }
        }
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    fetchTopics();
    return () => {
      isActive = false;
      controller.abort();
    };
  }, [uiLang]);

  const visibleTopics = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    return topics
      .filter((topic) => (filterMode === "featured" ? topic.is_featured : true))
      .filter((topic) => {
        if (!normalizedSearch) {
          return true;
        }
        const haystack = [
          topic.name || "",
          topic.subtitle || "",
          ...(Array.isArray(topic.tags) ? topic.tags : []),
        ]
          .join(" ")
          .toLowerCase();
        return haystack.includes(normalizedSearch);
      });
  }, [topics, filterMode, searchTerm]);

  if (loading) {
    return (
      <div className="topic-library-page-container">
        <header className="topic-library-page-header">
          <div className="topic-library-header-content">
            <h1 className="topic-library-page-header-text">
              {t("topicLibraryPage.title", uiLang)}
            </h1>
            <p className="topic-library-page-subtitle">
              {t("topicLibraryPage.subtitle", uiLang)}
            </p>
          </div>
        </header>
        <div className="topic-library-content">
          <p>{t("topicLibraryPage.loading", uiLang)}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="topic-library-page-container">
        <header className="topic-library-page-header">
          <div className="topic-library-header-content">
            <h1 className="topic-library-page-header-text">
              {t("topicLibraryPage.title", uiLang)}
            </h1>
            <p className="topic-library-page-subtitle">
              {t("topicLibraryPage.subtitle", uiLang)}
            </p>
          </div>
        </header>
        <div className="topic-library-content">
          <p>{`${t("topicLibraryPage.errorTitle", uiLang)}: ${error}`}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="topic-library-page-container">
      {/* page header */}
      <header className="topic-library-page-header">
        <div className="topic-library-header-content">
          <h1 className="topic-library-page-header-text">
            {t("topicLibraryPage.title", uiLang)}
          </h1>
          <p className="topic-library-page-subtitle">
            {t("topicLibraryPage.subtitle", uiLang)}
          </p>
        </div>
      </header>

      <div className="topic-library-content">
        <div className="topic-library-toolbar-wrapper">
          <Link to={withUi("/resources")} className="topic-library-back-link">
            {t("topicLibraryPage.backToResources", uiLang)}
          </Link>
          <div className="topic-library-toolbar">
            <div className="topic-library-toolbar-left">
              <div className="topic-library-filters">
                <button
                  type="button"
                  className={`topic-filter-button ${filterMode === "featured" ? "active" : ""}`}
                  onClick={() => setFilterMode("featured")}
                >
                  {t("topicLibraryPage.featuredButton", uiLang)}
                </button>
                <button
                  type="button"
                  className={`topic-filter-button ${filterMode === "all" ? "active" : ""}`}
                  onClick={() => setFilterMode("all")}
                >
                  {t("topicLibraryPage.allButton", uiLang)}
                </button>
              </div>
            </div>
            <div className="topic-library-toolbar-right">
              <div className="topic-library-search">
                <label htmlFor="topic-library-search-input" className="sr-only">
                  {t("topicLibraryPage.searchPlaceholder", uiLang)}
                </label>
                <input
                  id="topic-library-search-input"
                  type="search"
                  placeholder={t("topicLibraryPage.searchPlaceholder", uiLang)}
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                />
                <span className="topic-library-search-icon" aria-hidden="true">
                  🔍
                </span>
              </div>
            </div>
          </div>
        </div>
        {/* Topics List */}
        <div className="topic-library-list">
          {visibleTopics.length === 0 ? (
            <div className="topic-library-placeholder">
              <h3>{t("topicLibraryPage.emptyTitle", uiLang)}</h3>
              <p>{t("topicLibraryPage.emptyBody", uiLang)}</p>
            </div>
          ) : (
            visibleTopics.map((topic) => (
              <Link
                key={topic.id}
                to={withUi(`/topic-library/${topic.slug}`)}
                className="topic-library-item"
              >
                <div className="topic-library-content-wrapper">
                  <div className="topic-library-header">
                    {/* <div className="topic-library-number">
                      {(index + 1).toString().padStart(2, '0')}
                    </div> */}
                    <div className="topic-library-text">
                      <h3 className="topic-library-title">{topic.name}</h3>
                      {topic.subtitle && (
                        <p className="topic-library-subtitle">{topic.subtitle}</p>
                      )}
                      {topic.tags && topic.tags.length > 0 && (
                        <div className="topic-library-tags">
                          {topic.tags.map((tag, tagIndex) => (
                            <span key={tagIndex} className="topic-library-tag">
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="topic-library-arrow">→</div>
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default TopicLibrary;

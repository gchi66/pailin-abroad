import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import "../Styles/TopicLibrary.css";

const TopicLibrary = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
        const response = await fetch(`/api/topic-library?lang=${uiLang}`, {
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

      {/* Topics List */}
      <div className="topic-library-content">
        <div className="topic-library-list">
          {topics.length === 0 ? (
            <div className="topic-library-placeholder">
              <h3>{t("topicLibraryPage.emptyTitle", uiLang)}</h3>
              <p>{t("topicLibraryPage.emptyBody", uiLang)}</p>
            </div>
          ) : (
            topics.map((topic, index) => (
              <Link
                key={topic.id}
                to={withUi(`/topic-library/${topic.slug}`)}
                className="topic-library-item"
              >
                <div className="topic-library-content-wrapper">
                  <div className="topic-library-header">
                    <div className="topic-library-number">
                      {(index + 1).toString().padStart(2, '0')}
                    </div>
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

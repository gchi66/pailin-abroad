import React, { useState, useEffect, useRef } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import TopicRichSectionRenderer from "../Components/TopicRichSectionRenderer";
import LessonLanguageToggle from "../Components/LessonLanguageToggle";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import "../Styles/TopicDetail.css";

const TopicDetail = () => {
  const { slug } = useParams();
  const [topic, setTopic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRefetching, setIsRefetching] = useState(false);
  const { ui: uiLang } = useUiLang();
  const withUi = useWithUi();
  const [searchParams, setSearchParams] = useSearchParams();
  const hasLoadedRef = useRef(false);

  const rawContentLang = (searchParams.get("content_lang") || "en").toLowerCase();
  const contentLang = rawContentLang === "th" ? "th" : "en";

  const setContentLang = (nextLang) => {
    const normalized = nextLang === "th" ? "th" : "en";
    const params = new URLSearchParams(searchParams);
    params.set("content_lang", normalized);
    setSearchParams(params, { replace: true });
  };

  useEffect(() => {
    if (!slug) return;
    const controller = new AbortController();
    let isActive = true;
    const initialLoad = !hasLoadedRef.current;

    if (initialLoad) {
      setLoading(true);
    } else {
      setIsRefetching(true);
    }

    const fetchTopic = async () => {
      try {
        setError(null);
        const response = await fetch(`/api/topic-library/${slug}?lang=${contentLang}`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error('Topic not found');
        }
        const data = await response.json();
        if (isActive) {
          setTopic(data.topic);
          hasLoadedRef.current = true;
        }
      } catch (err) {
        if (err.name === "AbortError") return;
        console.error('Error fetching topic:', err);
        if (isActive) {
          setError(err.message);
          if (!hasLoadedRef.current) {
            setTopic(null);
          }
        }
      } finally {
        if (!isActive) return;
        if (initialLoad) {
          setLoading(false);
        } else {
          setIsRefetching(false);
        }
      }
    };

    fetchTopic();
    return () => {
      isActive = false;
      controller.abort();
    };
  }, [slug, contentLang]);

  if (loading) {
    return (
      <div className="topic-detail-page-container">
        <div className="topic-detail-header">
          <h1 className="topic-detail-header-text">
            {t("topicDetailPage.loadingTitle", uiLang)}
          </h1>
        </div>
        <div className="topic-detail-content">
          <p>{t("topicDetailPage.loadingBody", uiLang)}</p>
        </div>
      </div>
    );
  }

  if (!topic) {
    return (
      <div className="topic-detail-page-container">
        <div className="topic-detail-header">
          <h1 className="topic-detail-header-text">
            {t("topicDetailPage.notFoundTitle", uiLang)}
          </h1>
        </div>
        <div className="topic-detail-content">
          <p>
            {t("topicDetailPage.notFoundBody", uiLang)}
            {error ? ` (${error})` : ""}
          </p>
          <Link to={withUi("/topic-library")} className="topic-detail-back-link">
            {t("topicDetailPage.backToLibrary", uiLang)}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="topic-detail-page-container">
      {/* Page banner - use same banner as Topic Library */}
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

      {/* Navigation */}
      <div className="topic-detail-nav">
        <Link to={withUi("/topic-library")} className="topic-detail-back-link">
          {t("topicDetailPage.backToLibrary", uiLang)}
        </Link>
        <div className="topic-detail-nav-right">
          {topic.tags && topic.tags.length > 0 && (
            <div className="topic-detail-tags">
              {topic.tags.map((tag, index) => (
                <span key={index} className="topic-detail-tag">
                  {tag}
                </span>
              ))}
            </div>
          )}
          <LessonLanguageToggle
            contentLang={contentLang}
            setContentLang={setContentLang}
          />
          {isRefetching && (
            <span className="topic-detail-refetching">
              {t("topicDetailPage.loadingBody", uiLang)}
            </span>
          )}
        </div>
      </div>

      {/* Topic Content */}
      <div className="topic-detail-content">
        {/* Topic title moved into content box (top-left). Subtitle intentionally removed. */}
        <div className="topic-detail-inner-header">
          <h2 className="topic-detail-content-title">
            {topic?.name}
          </h2>
        </div>

        {topic.content_jsonb && topic.content_jsonb.length > 0 ? (
          <TopicRichSectionRenderer
            nodes={topic.content_jsonb}
            uiLang={uiLang}
          />
        ) : (
          <div className="topic-detail-placeholder">
            <p>{t("topicDetailPage.emptyContent", uiLang)}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TopicDetail;

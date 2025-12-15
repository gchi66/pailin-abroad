import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import TopicRichSectionRenderer from "../Components/TopicRichSectionRenderer";
import LessonLanguageToggle from "../Components/LessonLanguageToggle";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";
import { useStickyLessonToggle } from "../StickyLessonToggleContext";
import Breadcrumbs from "../Components/Breadcrumbs";
import "../Styles/TopicDetail.css";

const TopicDetail = () => {
  const { slug } = useParams();
  const [topic, setTopic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isRefetching, setIsRefetching] = useState(false);
  const { ui: uiLang } = useUiLang();
  const withUi = useWithUi();
  const hasLoadedRef = useRef(false);
  const topicNavRef = useRef(null);

  const [contentLang, setContentLangState] = useState(() => {
    if (typeof window === "undefined") return "en";
    const stored = (localStorage.getItem("contentLang") || "").toLowerCase();
    return stored === "th" ? "th" : "en";
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("contentLang", contentLang);
    }
  }, [contentLang]);

  const setContentLang = useCallback((nextLang) => {
    const normalized = nextLang === "th" ? "th" : "en";
    setContentLangState(normalized);
  }, []);

  const handleBackToTop = useCallback(() => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, []);

  const {
    registerLessonToggle,
    unregisterLessonToggle,
    updateContentLang: updateStickyContentLang,
    setShowStickyToggle,
  } = useStickyLessonToggle();

  const observerRef = useRef(null);
  const observerMarginRef = useRef("");
  const stickyNodesRef = useRef(new Map());
  const visibleNodeIdsRef = useRef(new Set());
  const headIdCounterRef = useRef(0);

  const computeNavbarMargin = useCallback(() => {
    if (typeof window === "undefined") return "0px 0px 0px 0px";
    const raw = getComputedStyle(document.documentElement).getPropertyValue("--navbar-height");
    const parsed = parseFloat(raw);
    const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
    return `-${navbarHeight}px 0px 0px 0px`;
  }, []);

  const handleIntersection = useCallback((entries) => {
    let changed = false;
    entries.forEach((entry) => {
      const id = entry.target.getAttribute("data-topic-sticky-id");
      if (!id) return;
      if (entry.isIntersecting) {
        if (!visibleNodeIdsRef.current.has(id)) {
          visibleNodeIdsRef.current.add(id);
          changed = true;
        }
      } else if (visibleNodeIdsRef.current.has(id)) {
        visibleNodeIdsRef.current.delete(id);
        changed = true;
      }
    });
    if (changed) {
      setShowStickyToggle(visibleNodeIdsRef.current.size === 0);
    }
  }, [setShowStickyToggle]);

  const rebuildObserver = useCallback(() => {
    const margin = computeNavbarMargin();
    if (observerRef.current) {
      observerRef.current.disconnect();
    }
    const observer = new IntersectionObserver(handleIntersection, {
      root: null,
      threshold: 0,
      rootMargin: margin,
    });
    observerRef.current = observer;
    observerMarginRef.current = margin;
    stickyNodesRef.current.forEach((node) => {
      observer.observe(node);
    });
  }, [computeNavbarMargin, handleIntersection]);

  const ensureObserver = useCallback(() => {
    const margin = computeNavbarMargin();
    if (!observerRef.current || observerMarginRef.current !== margin) {
      rebuildObserver();
    }
    return observerRef.current;
  }, [computeNavbarMargin, rebuildObserver]);

  const registerStickyNodes = useCallback((nodes = []) => {
    if (!nodes.length) {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      stickyNodesRef.current.clear();
      visibleNodeIdsRef.current.clear();
      setShowStickyToggle(false);
      return;
    }

    const observer = ensureObserver();
    const map = stickyNodesRef.current;
    const incomingIds = new Set();

    nodes.forEach((node) => {
      if (!node) return;
      if (!node.getAttribute("data-topic-sticky-id")) {
        const newId = `topic-head-${headIdCounterRef.current++}`;
        node.setAttribute("data-topic-sticky-id", newId);
      }
      incomingIds.add(node.getAttribute("data-topic-sticky-id"));
    });

    map.forEach((node, id) => {
      if (!incomingIds.has(id)) {
        if (observer) observer.unobserve(node);
        map.delete(id);
        visibleNodeIdsRef.current.delete(id);
      }
    });

    nodes.forEach((node) => {
      if (!node) return;
      const id = node.getAttribute("data-topic-sticky-id");
      const existing = map.get(id);
      if (existing === node) return;
      if (existing && observer) {
        observer.unobserve(existing);
      }
      map.set(id, node);
      if (observer) {
        observer.observe(node);
      }
    });

    const navbarHeightRaw =
      typeof window !== "undefined"
        ? getComputedStyle(document.documentElement).getPropertyValue("--navbar-height")
        : "0";
    const parsed = parseFloat(navbarHeightRaw);
    const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
    const viewportHeight = typeof window !== "undefined" ? window.innerHeight : 0;

    const visibleNow = new Set();
    nodes.forEach((node) => {
      if (!node) return;
      const id = node.getAttribute("data-topic-sticky-id");
      if (!id) return;
      const rect = node.getBoundingClientRect();
      const isVisible = rect.bottom > navbarHeight && rect.top < viewportHeight;
      if (isVisible) {
        visibleNow.add(id);
      }
    });

    visibleNodeIdsRef.current = visibleNow;
    setShowStickyToggle(visibleNodeIdsRef.current.size === 0);
  }, [ensureObserver, setShowStickyToggle]);

  const registerNavForSticky = useCallback(() => {
    const nodes = [];
    if (topicNavRef.current) {
      nodes.push(topicNavRef.current);
    }
    registerStickyNodes(nodes);
  }, [registerStickyNodes]);

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
    registerNavForSticky();
    return () => {
      registerStickyNodes([]);
    };
  }, [registerNavForSticky, registerStickyNodes, topic]);

  useEffect(() => {
    const handleResize = () => {
      rebuildObserver();
    };
    if (typeof window !== "undefined") {
      window.addEventListener("resize", handleResize);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", handleResize);
      }
    };
  }, [rebuildObserver]);

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      stickyNodesRef.current.clear();
      visibleNodeIdsRef.current.clear();
      setShowStickyToggle(false);
    };
  }, [setShowStickyToggle]);

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
        const response = await fetch(`${API_BASE_URL}/api/topic-library/${slug}?lang=${contentLang}`, {
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
          <Breadcrumbs
            className="topic-detail-breadcrumbs"
            items={[
              { label: t("resourcesPage.title", uiLang), to: withUi("/resources") },
              { label: t("topicLibraryPage.title", uiLang), to: withUi("/topic-library") },
              { label: t("topicDetailPage.notFoundTitle", uiLang) },
            ]}
          />
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
      <div className="topic-detail-nav" ref={topicNavRef}>
        <Breadcrumbs
          className="topic-detail-breadcrumbs"
          items={[
            { label: t("resourcesPage.title", uiLang), to: withUi("/resources") },
            { label: t("topicLibraryPage.title", uiLang), to: withUi("/topic-library") },
            { label: topic?.name },
          ]}
        />
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
          <div className="topic-detail-language-toggle">
            <LessonLanguageToggle
              contentLang={contentLang}
              setContentLang={setContentLang}
            />
          </div>
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

      <div className="topic-detail-back-to-top-row">
        <button
          type="button"
          className="topic-detail-back-to-top"
          onClick={handleBackToTop}
        >
          <span className="topic-detail-back-to-top-label">BACK TO TOP</span>
          <span aria-hidden="true" className="topic-detail-back-to-top-arrow">
            ▸
          </span>
        </button>
      </div>
    </div>
  );
};

export default TopicDetail;

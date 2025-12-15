import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import { API_BASE_URL } from "../config/api";
import Breadcrumbs from "../Components/Breadcrumbs";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import "../Styles/TopicLibrary.css";

const MINOR_WORDS = new Set([
  "a",
  "an",
  "and",
  "as",
  "at",
  "but",
  "by",
  "for",
  "in",
  "nor",
  "of",
  "on",
  "or",
  "per",
  "the",
  "to",
  "vs",
  "via",
]);

const formatTopicTitle = (title = "") => {
  if (!title) return "";
  const words = title.trim().split(/\s+/);
  return words
    .map((word, index) => {
      const leading = word.match(/^[^A-Za-z0-9]*/)?.[0] ?? "";
      const trailing = word.match(/[^A-Za-z0-9]*$/)?.[0] ?? "";
      const core = word.slice(leading.length, word.length - trailing.length);
      if (!core) {
        return word;
      }
      const lowerCore = core.toLowerCase();
      const shouldCapitalize =
        index === 0 ||
        index === words.length - 1 ||
        !MINOR_WORDS.has(lowerCore);

      const capitalizeSegment = (segment) =>
        segment ? segment[0].toUpperCase() + segment.slice(1) : segment;

      const formattedCore = shouldCapitalize
        ? lowerCore
            .split("-")
            .map((segment) => capitalizeSegment(segment))
            .join("-")
        : lowerCore;

      return `${leading}${formattedCore}${trailing}`;
    })
    .join(" ");
};

const TopicLibrary = () => {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterMode, setFilterMode] = useState("featured");
  const [searchTerm, setSearchTerm] = useState("");
  const [isMobile, setIsMobile] = useState(false);
  const [isMobileFilterMenuOpen, setIsMobileFilterMenuOpen] = useState(false);
  const [profile, setProfile] = useState(null);
  const { ui: uiLang } = useUiLang();
  const withUi = useWithUi();
  const { user } = useAuth();

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

  useEffect(() => {
    const fetchProfile = async () => {
      if (!user) {
        setProfile(null);
        return;
      }

      try {
        const { data, error: profileError } = await supabaseClient
          .from("users")
          .select("is_paid")
          .eq("id", user.id)
          .single();

        if (profileError) {
          console.error("Error fetching user profile:", profileError.message);
          setProfile(null);
        } else {
          setProfile(data);
        }
      } catch (profileErr) {
        console.error("Error fetching user profile:", profileErr);
        setProfile(null);
      }
    };

    fetchProfile();
  }, [user]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 30rem)");
    const handleMediaChange = (event) => {
      setIsMobile(event.matches);
      if (!event.matches) {
        setIsMobileFilterMenuOpen(false);
      }
    };

    setIsMobile(mediaQuery.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleMediaChange);
    } else {
      mediaQuery.addListener(handleMediaChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleMediaChange);
      } else {
        mediaQuery.removeListener(handleMediaChange);
      }
    };
  }, []);

  const isPaid = profile?.is_paid === true;
  const isNoAccount = !user;
  const isFreePlan = user && profile?.is_paid === false;

  const isTopicLocked = (isFeatured) => {
    if (isPaid) return false;
    if (isNoAccount) return true;
    if (isFreePlan) return !isFeatured;
    return false;
  };

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
          <Breadcrumbs
            className="topic-library-breadcrumbs"
            items={[
              { label: t("resourcesPage.title", uiLang), to: withUi("/resources") },
              { label: t("topicLibraryPage.title", uiLang) },
            ]}
          />
          {(isFreePlan || isNoAccount) && (
            <div className={`topic-library-plan-notice ${isFreePlan ? "is-free-plan" : "is-no-account"}`}>
              <div className="topic-library-plan-copy">
                <p className="topic-library-plan-title">
                  {isFreePlan ? "You're on our free plan." : "Looks like you don't have an account."}
                </p>
                <p className="topic-library-plan-desc">
                  {isFreePlan
                    ? "Upgrade to enjoy full access to our Topic Library."
                    : "Sign up for free to access our featured topics!"}
                </p>
              </div>
              <Link
                className="topic-library-plan-cta"
                to={isFreePlan ? "/membership" : "/signup"}
              >
                {isFreePlan ? "BECOME A MEMBER" : "SIGN UP FOR FREE"}
              </Link>
            </div>
          )}
          {!isMobile && (
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
            </div>
          )}

          {isMobile && (
            <div className="topic-library-mobile-toolbar">
              <div className="topic-library-mobile-toggle">
                <button
                  type="button"
                  className="topic-library-mobile-view-toggle"
                  onClick={() => setIsMobileFilterMenuOpen((prev) => !prev)}
                  aria-expanded={isMobileFilterMenuOpen}
                >
                  <span>
                    {filterMode === "featured"
                      ? t("topicLibraryPage.featuredButton", uiLang)
                      : t("topicLibraryPage.allButton", uiLang)}
                  </span>
                  <span className="topic-library-mobile-caret" aria-hidden="true">▾</span>
                </button>
                {isMobileFilterMenuOpen && (
                  <div className="topic-library-mobile-menu">
                    <button
                      type="button"
                      className={`topic-library-mobile-menu-item${filterMode === "featured" ? " is-active" : ""}`}
                      onClick={() => {
                        setFilterMode("featured");
                        setIsMobileFilterMenuOpen(false);
                      }}
                    >
                      {t("topicLibraryPage.featuredButton", uiLang)}
                    </button>
                    <button
                      type="button"
                      className={`topic-library-mobile-menu-item${filterMode === "all" ? " is-active" : ""}`}
                      onClick={() => {
                        setFilterMode("all");
                        setIsMobileFilterMenuOpen(false);
                      }}
                    >
                      {t("topicLibraryPage.allButton", uiLang)}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
        {/* Topics List */}
        <div className="topic-library-list">
          {visibleTopics.length === 0 ? (
            <div className="topic-library-placeholder">
              <h3>{t("topicLibraryPage.emptyTitle", uiLang)}</h3>
              <p>{t("topicLibraryPage.emptyBody", uiLang)}</p>
            </div>
          ) : (
            visibleTopics.map((topic) => {
              const locked = isTopicLocked(topic.is_featured);
              return (
                <Link
                  key={topic.id}
                  to={withUi(`/topic-library/${topic.slug}`)}
                  className={`topic-library-item${locked ? " topic-library-item-locked" : ""}`}
                >
                  {locked && (
                    <div className="topic-library-lock-overlay">
                      <div className="topic-library-lock-content">
                        <img
                          src="/images/password-lock.webp"
                          alt=""
                          className="topic-library-lock-icon"
                        />
                        <div className="topic-library-lock-text">
                          <span>Upgrade to view!</span>
                          <Link to="/membership" className="topic-library-lock-link">
                            Become a member
                          </Link>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="topic-library-content-wrapper">
                    <div className="topic-library-header">
                      <div className="topic-library-text">
                        <h3 className="topic-library-title">{formatTopicTitle(topic.name)}</h3>
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
                  <div className="topic-library-arrow">▸</div>
                </Link>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default TopicLibrary;

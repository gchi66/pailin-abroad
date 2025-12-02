// src/Components/Navbar.jsx
import React, { useState, useEffect, useRef, useCallback } from "react";
import "../Styles/Navbar.css";
import LanguageToggle from "./LanguageToggle";
import LessonLanguageToggle from "./LessonLanguageToggle";
import ProfileDropdown from "./ProfileDropdown";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";
import { useStickyLessonToggle } from "../StickyLessonToggleContext";

const Navbar = ({ toggleLoginModal, toggleSignupModal }) => {
  const { user } = useAuth();
  const { ui, setUi } = useUiLang();
  const withUi = useWithUi();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const navRef = useRef(null);
  const {
    showStickyToggle,
    contentLang: stickyContentLang,
    setContentLang: stickySetContentLang,
    isRegistered: stickyToggleRegistered,
  } = useStickyLessonToggle();
  const stickyToggleVisible = showStickyToggle && typeof stickySetContentLang === "function";
  const stickySlotMounted = stickyToggleRegistered && typeof stickySetContentLang === "function";
  const navbarStickyLang = stickyContentLang || "en";
  const handleStickyContentLang = stickySetContentLang || (() => {});

  const [isCompactNav, setIsCompactNav] = useState(false);
  const [compactNavDropdowns, setCompactNavDropdowns] = useState({});

  const toggleCompactNavDropdown = useCallback((key) => {
    setCompactNavDropdowns((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }, []);

  const updateNavHeightVar = useCallback(() => {
    if (navRef.current) {
      const { height } = navRef.current.getBoundingClientRect();
      document.documentElement.style.setProperty("--navbar-height", `${height}px`);
    }
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 800px)");
    const handleMediaChange = (event) => setIsCompactNav(event.matches);

    handleMediaChange(mediaQuery);
    mediaQuery.addEventListener("change", handleMediaChange);

    return () => mediaQuery.removeEventListener("change", handleMediaChange);
  }, []);

  useEffect(() => {
    if (!isCompactNav) {
      setCompactNavDropdowns({});
    }
  }, [isCompactNav]);

  // Fetch user profile to check is_paid status
  useEffect(() => {
    const fetchUserProfile = async () => {
      if (!user) {
        setProfile(null);
        return;
      }

      try {
        const { data, error } = await supabaseClient
          .from("users")
          .select("is_paid")
          .eq("id", user.id)
          .single();

        if (error) {
          console.error("Error fetching user profile:", error.message);
          setProfile(null);
        } else {
          setProfile(data);
        }
      } catch (error) {
        console.error("Error fetching user profile:", error);
        setProfile(null);
      }
    };

    fetchUserProfile();
  }, [user]);

  useEffect(() => {
    updateNavHeightVar();
    window.addEventListener("resize", updateNavHeightVar);
    return () => window.removeEventListener("resize", updateNavHeightVar);
  }, [updateNavHeightVar]);

  useEffect(() => {
    updateNavHeightVar();
  }, [updateNavHeightVar, user, profile]);

  // Show dropdown if user is not logged in OR is a free user
  const shouldShowLessonsDropdown = !user || !profile?.is_paid;

  const staticNavLinks = [
    {
      id: user ? "myPathway" : "home",
      label: user ? t("nav.myPathway", ui) : t("nav.home", ui),
      href: withUi(user ? "/pathway" : "/", ui),
    },
    shouldShowLessonsDropdown
      ? {
          id: "lessons",
          label: t("nav.lessons", ui),
          dropdown: [
            { label: t("nav.sampleLessons", ui), href: withUi("/try-lessons", ui) },
            { label: t("nav.lessonLibrary", ui), href: withUi("/lessons", ui) },
            { label: t("nav.freeLessons", ui), href: withUi("/free-lessons", ui) },
          ],
        }
      : { id: "lessons", label: t("nav.lessons", ui), href: withUi("/lessons", ui) },
    { id: "resources", label: t("nav.resources", ui), href: withUi("/resources", ui) },
    { id: "about", label: t("nav.about", ui), href: withUi("/about", ui) },
    { id: "contact", label: t("nav.contact", ui), href: withUi("/contact", ui) },
    { id: "membership", label: t("nav.membership", ui), href: withUi("/membership", ui), className: "pricing" },
  ];

  return (
    <header className={`navbar${isCompactNav ? " navbar--compact" : ""}`} ref={navRef}>
      <div className="logo">
        <NavLink to={withUi("/", ui)}>
          <img src="/images/full-logo.webp" alt="Pailin Abroad Logo" />
        </NavLink>
      </div>

      {!isCompactNav && (
        <nav className="menu">
          <ul>
            {staticNavLinks.map((link, index) => {
              if (link.dropdown) {
                return (
                  <li className="lessons-dropdown-wrapper" key={`dropdown-${index}`}>
                    <span className="lessons-dropdown-trigger">{link.label}</span>
                    <ul className="lessons-dropdown">
                      {link.dropdown.map((child, childIndex) => (
                        <li key={`dropdown-item-${childIndex}`}>
                          <NavLink to={child.href}>{child.label}</NavLink>
                        </li>
                      ))}
                    </ul>
                  </li>
                );
              }

              return (
                <li key={`nav-link-${index}`} className={link.className ?? ""}>
                  <NavLink to={link.href}>{link.label}</NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
      )}

      <div className="right-side">
        {stickySlotMounted && (
          <div
            className={`navbar-lesson-toggle${stickyToggleVisible ? " is-visible" : ""}`}
            aria-hidden={stickyToggleVisible ? "false" : "true"}
          >
            <LessonLanguageToggle
              contentLang={navbarStickyLang}
              setContentLang={handleStickyContentLang}
              disabled={!stickyToggleVisible}
            />
          </div>
        )}
        {user ? (
          <ProfileDropdown
            extraLinks={isCompactNav ? staticNavLinks : null}
          />
        ) : (
          <div className="guest-menu">
            <div className="guest-menu-inner">
              <div className="guest-menu-wrapper">
                <button
                  type="button"
                  className="guest-menu-trigger"
                  aria-label="Open menu"
                >
                  <span className="guest-menu-bar" />
                  <span className="guest-menu-bar" />
                  <span className="guest-menu-bar" />
                </button>
              </div>
              <div className="guest-menu-dropdown dropdown-menu">
                <div className="dropdown-section">
                  <LanguageToggle language={ui} setLanguage={setUi} />
                </div>
                <button
                  type="button"
                  className="dropdown-link"
                  onClick={toggleSignupModal}
                >
                  {t("authButtons.signUp", ui)}
                </button>
                <button
                  type="button"
                  className="dropdown-link"
                  onClick={toggleLoginModal}
                >
                  {t("authButtons.signIn", ui)}
                </button>
                {isCompactNav && (
                  <>
                    <div className="dropdown-divider" />
                    <div className="dropdown-navlinks">
                      {staticNavLinks.map((link, index) => {
                        if (link.dropdown) {
                          const dropdownKey = link.id ?? link.href ?? `dropdown-${index}`;
                          const isDropdownOpen = Boolean(compactNavDropdowns[dropdownKey]);
                          return (
                            <div
                              key={`guest-nav-${link.id ?? index}`}
                              className={`dropdown-collapsible${isDropdownOpen ? " is-open" : ""}`}
                            >
                              <button
                                type="button"
                                className="dropdown-link dropdown-collapsible-trigger"
                                onClick={() => toggleCompactNavDropdown(dropdownKey)}
                                aria-expanded={isDropdownOpen}
                              >
                                <span>{link.label}</span>
                                <span
                                  className={`dropdown-arrow${isDropdownOpen ? " is-open" : ""}`}
                                  aria-hidden="true"
                                >
                                  ▸
                                </span>
                              </button>
                              <div
                                className={`dropdown-collapsible-content${isDropdownOpen ? " is-open" : ""}`}
                              >
                                <ul>
                                  {link.dropdown.map((child, childIndex) => (
                                    <li key={`guest-dropdown-item-${childIndex}`}>
                                      <NavLink to={child.href} className="dropdown-sub-link">
                                        {child.label}
                                      </NavLink>
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            </div>
                          );
                        }

                        return (
                          <button
                            key={`guest-nav-${link.id ?? index}`}
                            type="button"
                            className={`dropdown-link ${link.className ?? ""}`}
                            onClick={() => {
                              navigate(link.href);
                            }}
                          >
                            {link.label}
                          </button>
                        );
                      })}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </header>
  );
};

export default Navbar;

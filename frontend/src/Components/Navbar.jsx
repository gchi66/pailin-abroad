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
import { API_BASE_URL } from "../config/api";

const Navbar = ({ toggleLoginModal, toggleSignupModal }) => {
  const { user } = useAuth();
  const { ui, setUi } = useUiLang();
  const withUi = useWithUi();
  const navigate = useNavigate();
  const [profile, setProfile] = useState(null);
  const navRef = useRef(null);
  const mobileMenuRef = useRef(null);
  const mobilePanelRef = useRef(null);
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
  const [isMobileNav, setIsMobileNav] = useState(false);
  const [compactNavDropdowns, setCompactNavDropdowns] = useState({});
  const [isMobileUserMenuOpen, setIsMobileUserMenuOpen] = useState(false);
  const [userProfileInfo, setUserProfileInfo] = useState({ name: "", email: "", avatar: "" });

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
    const mediaQuery = window.matchMedia("(max-width: 1100px)");
    const mobileQuery = window.matchMedia("(max-width: 480px)");
    const handleMediaChange = (event) => setIsCompactNav(event.matches);
    const handleMobileChange = (event) => setIsMobileNav(event.matches);

    handleMediaChange(mediaQuery);
    handleMobileChange(mobileQuery);
    mediaQuery.addEventListener("change", handleMediaChange);
    mobileQuery.addEventListener("change", handleMobileChange);

    return () => {
      mediaQuery.removeEventListener("change", handleMediaChange);
      mobileQuery.removeEventListener("change", handleMobileChange);
    };
  }, []);

  useEffect(() => {
    if (!isCompactNav) {
      setCompactNavDropdowns({});
    }
  }, [isCompactNav]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      const menuNode = mobileMenuRef.current;
      const panelNode = mobilePanelRef.current;
      if (
        menuNode &&
        !menuNode.contains(event.target) &&
        panelNode &&
        !panelNode.contains(event.target)
      ) {
        setIsMobileUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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

  useEffect(() => {
    const fetchProfileInfo = async () => {
      if (!user) {
        setUserProfileInfo({ name: "", email: "", avatar: "" });
        return;
      }

      try {
        const { data: { session } } = await supabaseClient.auth.getSession();
        const token = session?.access_token;

        let name = user.user_metadata?.first_name || user.user_metadata?.name || "";
        const email = user.email || "";
        let avatar = user.user_metadata?.avatar || "";

        if (token) {
          const response = await fetch(`${API_BASE_URL}/api/user/profile`, {
            method: "GET",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
          });
          if (response.ok) {
            const data = await response.json();
            if (data?.profile) {
              name = data.profile.name || name;
              avatar = data.profile.avatar || data.profile.avatar_url || avatar;
            }
          }
        }

        setUserProfileInfo({
          name: name || "",
          email,
          avatar: avatar || "/images/characters/avatar_1.webp",
        });
      } catch (err) {
        console.error("Error fetching profile info:", err);
        setUserProfileInfo((prev) => ({
          ...prev,
          email: user.email || prev.email,
          avatar: prev.avatar || "/images/characters/avatar_1.webp",
        }));
      }
    };

    fetchProfileInfo();
  }, [user]);

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
    ...(!profile?.is_paid
      ? [{ id: "membership", label: t("nav.membership", ui), href: withUi("/membership", ui), className: "pricing" }]
      : []),
  ];

  const mobileMenuAvailable = isMobileNav;
  const showMobilePanel = isMobileNav && isMobileUserMenuOpen;
  const logoHref = withUi(user && profile?.is_paid ? "/pathway" : "/", ui);

  return (
    <header
      className={`navbar${isCompactNav ? " navbar--compact" : ""}${isMobileNav ? " navbar--mobile" : ""}${stickyToggleVisible ? " navbar--toggle-visible" : ""}`}
      ref={navRef}
    >
      {mobileMenuAvailable && (
        <div className="mobile-menu-slot" ref={mobileMenuRef}>
          <button
            type="button"
            className="mobile-user-trigger"
            aria-label="Open menu"
            onClick={() => setIsMobileUserMenuOpen((prev) => !prev)}
          >
            <img
              src="/images/menu_hamburger_icon_desktop.png"
              alt="User menu icon"
              className="guest-menu-icon"
            />
          </button>
        </div>
      )}

      <div className="logo">
        <NavLink to={logoHref}>
          <img src="/images/full-logo.webp" alt="Pailin Abroad Logo" />
        </NavLink>
      </div>

      {!isCompactNav && !isMobileNav && (
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
          isMobileNav ? null : (
            <ProfileDropdown
              extraLinks={isCompactNav ? staticNavLinks : null}
              avatarSrc={userProfileInfo.avatar}
              avatarAlt={userProfileInfo.name || user?.email || "User avatar"}
            />
          )
        ) : (
          <div className="guest-menu">
            <div className="guest-menu-inner">
              <div className="guest-menu-wrapper">
                <button
                  type="button"
                  className="guest-menu-trigger"
                  aria-label="Open menu"
                >
                  <img
                    src="/images/menu_hamburger_icon_desktop.png"
                    alt="Guest menu icon"
                    className="guest-menu-icon"
                  />
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
                                      <NavLink
                                        to={child.href}
                                        className="dropdown-link dropdown-sub-link"
                                      >
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
      {showMobilePanel && (
        <>
          <div className="mobile-menu-panel" ref={mobilePanelRef}>
            <div className="mobile-menu-header">
              <LanguageToggle language={ui} setLanguage={setUi} />
              <button
                type="button"
                className="mobile-menu-close"
                aria-label="Close menu"
                onClick={() => setIsMobileUserMenuOpen(false)}
              >
                ✕
              </button>
            </div>

            {user ? (
              <>
                <div className="mobile-user-card">
                  <img
                    src={userProfileInfo.avatar || "/images/characters/avatar_1.webp"}
                    alt={userProfileInfo.name || user?.email || "User avatar"}
                    className="mobile-user-avatar"
                  />
                  <div className="mobile-user-meta">
                    <span className="mobile-user-name">{userProfileInfo.name || "User"}</span>
                    <span className="mobile-user-email">{userProfileInfo.email || user?.email}</span>
                  </div>
                </div>
                <div className="dropdown-divider" />
              </>
            ) : (
              <div className="mobile-auth-links">
                <button
                  type="button"
                  className="dropdown-link"
                  onClick={() => {
                    setIsMobileUserMenuOpen(false);
                    toggleSignupModal();
                  }}
                >
                  {t("authButtons.signUp", ui)}
                </button>
                <button
                  type="button"
                  className="dropdown-link"
                  onClick={() => {
                    setIsMobileUserMenuOpen(false);
                    toggleLoginModal();
                  }}
                >
                  {t("authButtons.signIn", ui)}
                </button>
                <div className="dropdown-divider" />
              </div>
            )}

            <div className="dropdown-navlinks mobile-navlinks">
              {staticNavLinks.map((link, index) => {
                if (link.dropdown) {
                  return (
                    <div key={`mobile-nav-${link.id ?? index}`} className="mobile-collapsible">
                      <button
                        type="button"
                        className="dropdown-link dropdown-collapsible-trigger"
                        onClick={() => toggleCompactNavDropdown(link.id ?? `dropdown-${index}`)}
                        aria-expanded={Boolean(compactNavDropdowns[link.id ?? `dropdown-${index}`])}
                      >
                        <span>{link.label}</span>
                        <span
                          className={`dropdown-arrow${compactNavDropdowns[link.id ?? `dropdown-${index}`] ? " is-open" : ""}`}
                          aria-hidden="true"
                        >
                          ▸
                        </span>
                      </button>
                      {compactNavDropdowns[link.id ?? `dropdown-${index}`] && (
                        <div className="dropdown-collapsible-content is-open">
                          <ul>
                            {link.dropdown.map((child, childIndex) => (
                              <li key={`mobile-sub-${childIndex}`}>
                                <button
                                  type="button"
                                  className="dropdown-link dropdown-sub-link"
                                  onClick={() => {
                                    setIsMobileUserMenuOpen(false);
                                    navigate(child.href);
                                  }}
                                >
                                  {child.label}
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                }

                return (
                  <button
                    key={`mobile-nav-${link.id ?? index}`}
                    type="button"
                    className={`dropdown-link ${link.className ?? ""}`}
                    onClick={() => {
                      setIsMobileUserMenuOpen(false);
                      navigate(link.href);
                    }}
                  >
                    {link.label}
                  </button>
                );
              })}
              {user && (
                <>
                  <div className="dropdown-divider" />
                  <button
                    type="button"
                    className="dropdown-link dropdown-link--secondary"
                    onClick={() => {
                      setIsMobileUserMenuOpen(false);
                      navigate("/profile");
                    }}
                  >
                    {t("profileDropdown.accountSettings", ui)}
                  </button>
                  <button
                    type="button"
                    className="dropdown-link dropdown-link--secondary"
                    onClick={() => {
                      supabaseClient.auth.signOut();
                      setIsMobileUserMenuOpen(false);
                      navigate("/");
                    }}
                  >
                    {t("profileDropdown.logout", ui)}
                  </button>
                </>
              )}
            </div>
          </div>
          <div
            className="mobile-menu-scrim"
            onClick={() => setIsMobileUserMenuOpen(false)}
            aria-hidden="true"
          />
        </>
      )}
    </header>
  );
};

export default Navbar;

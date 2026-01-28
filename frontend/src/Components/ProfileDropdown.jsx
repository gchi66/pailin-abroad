import React, { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import "../Styles/ProfileDropdown.css";
import supabaseClient from "../supabaseClient";
import LanguageToggle from "./LanguageToggle";

const ProfileDropdown = ({ extraLinks = null }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [extraDropdowns, setExtraDropdowns] = useState({});
  const { user } = useAuth();
  const { ui, setUi } = useUiLang();
  const withUi = useWithUi();
  const navigate = useNavigate();
  const dropdownRef = useRef(null);

  const openDropdown = () => {
    setIsOpen(true);
  };

  const closeDropdown = () => {
    setIsOpen(false);
  };

  const handleLogout = async () => {
    try {
      await supabaseClient.auth.signOut();
      navigate("/");
      setIsOpen(false);
    } catch (error) {
      console.error("Logout Error:", error.message);
    }
  };

  const filteredExtraLinks = Array.isArray(extraLinks)
    ? extraLinks.filter((link) => link.id !== "myPathway")
    : [];
  const hasExtraLinks = filteredExtraLinks.length > 0;

  const toggleExtraDropdown = useCallback((key) => {
    setExtraDropdowns((prev) => ({
      ...prev,
      [key]: !prev[key],
    }));
  }, []);

  useEffect(() => {
    setExtraDropdowns({});
  }, [extraLinks]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  if (!user) return null;

  return (
    <div
      className="profile-dropdown"
      ref={dropdownRef}
      onMouseEnter={openDropdown}
      onMouseLeave={closeDropdown}
    >
      <button className="profile-button" onClick={openDropdown}>
        <img
          src="/images/characters/pailin-blue-right.png"
          alt="Profile"
          className="profile-image"
        />
      </button>

      {isOpen && (
        <div className="dropdown-menu">
          <div className="dropdown-section">
            <LanguageToggle
              language={ui}
              setLanguage={setUi}
            />
          </div>
          <button
            type="button"
            className="dropdown-link"
            onClick={() => {
              navigate(withUi("/pathway", ui));
              setIsOpen(false);
            }}
          >
            {t("nav.myPathwayDropdown", ui)}
          </button>
          <button
            type="button"
            className="dropdown-link"
            onClick={() => {
              navigate(withUi("/profile", ui));
              setIsOpen(false);
            }}
          >
            {t("profileDropdown.accountSettings", ui)}
          </button>
          <button
            className="dropdown-link"
            onClick={handleLogout}
          >
            {t("profileDropdown.logout", ui)}
          </button>
          {hasExtraLinks && <div className="dropdown-divider" />}
          {hasExtraLinks && (
            <>
              <div className="dropdown-navlinks">
                {filteredExtraLinks.map((link, index) => {
                  if (link.dropdown) {
                    const dropdownKey = link.id ?? link.href ?? `dropdown-${index}`;
                    const isDropdownOpen = Boolean(extraDropdowns[dropdownKey]);
                    return (
                      <div
                        className={`dropdown-collapsible${isDropdownOpen ? " is-open" : ""}`}
                        key={`dropdown-nav-${link.id ?? index}`}
                      >
                        <button
                          type="button"
                          className="dropdown-link dropdown-collapsible-trigger"
                          onClick={() => toggleExtraDropdown(dropdownKey)}
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
                        <div className={`dropdown-collapsible-content${isDropdownOpen ? " is-open" : ""}`}>
                          <ul>
                            {link.dropdown.map((child, childIndex) => (
                              <li key={`dropdown-sub-item-${childIndex}`}>
                                <button
                                  type="button"
                                  className="dropdown-link dropdown-sub-link"
                                  onClick={() => {
                                    navigate(child.href);
                                    setIsOpen(false);
                                  }}
                                >
                                  {child.label}
                                </button>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <button
                      key={`dropdown-nav-${link.id ?? index}`}
                      type="button"
                      className={`dropdown-link ${link.className ?? ""}`}
                      onClick={() => {
                        navigate(link.href);
                        setIsOpen(false);
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
      )}
    </div>
  );
};

export default ProfileDropdown;

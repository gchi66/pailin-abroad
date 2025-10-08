// src/Components/Navbar.jsx
import React, { useState, useEffect } from "react";
import "../Styles/Navbar.css";
import LanguageToggle from "./LanguageToggle";
import SearchBar from "./SearchBar";
import AuthButtons from "./AuthButtons";
import ProfileDropdown from "./ProfileDropdown";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import supabaseClient from "../supabaseClient";

const Navbar = ({ toggleLoginModal, toggleSignupModal }) => {
  const { user } = useAuth();
  const { ui, setUi } = useUiLang();
  const withUi = useWithUi();
  const [profile, setProfile] = useState(null);

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

  // Show dropdown if user is not logged in OR is a free user
  const shouldShowLessonsDropdown = !user || !profile?.is_paid;

  return (
    <header className="navbar">
      <div className="logo">
        <NavLink to={withUi("/", ui)}>
          <img src="/images/full-logo.webp" alt="Pailin Abroad Logo" />
        </NavLink>
      </div>

      <nav className="menu">
        <ul>
          <li><NavLink to={withUi(user ? "/pathway" : "/", ui)}>{user ? t("nav.myPathway", ui) : t("nav.home", ui)}</NavLink></li>
          <li><NavLink to={withUi("/about", ui)}>{t("nav.about", ui)}</NavLink></li>

          {/* Lessons with dropdown for non-paid users */}
          {shouldShowLessonsDropdown ? (
            <li className="lessons-dropdown-wrapper">
              <span className="lessons-dropdown-trigger">{t("nav.lessons", ui)}</span>
              <ul className="lessons-dropdown">
                <li><NavLink to={withUi("/try-lessons", ui)}>4 Sample Lessons</NavLink></li>
                <li><NavLink to={withUi("/lessons", ui)}>Lesson Library</NavLink></li>
                <li><NavLink to={withUi("/free-lessons", ui)}>Free Lessons</NavLink></li>
              </ul>
            </li>
          ) : (
            <li><NavLink to={withUi("/lessons", ui)}>{t("nav.lessons", ui)}</NavLink></li>
          )}

          <li><NavLink to={withUi("/resources", ui)}>{t("nav.resources", ui)}</NavLink></li>
          <li><NavLink to={withUi("/contact", ui)}>{t("nav.contact", ui)}</NavLink></li>
          <li className="pricing">
            <NavLink to={withUi("/membership", ui)}>{t("nav.pricing", ui)}</NavLink>
          </li>
        </ul>
      </nav>

      <div className="right-side">
        <LanguageToggle
          language={ui}
          setLanguage={setUi}
          showLabel={false}
          label={t("uiLabel", ui)}                 // <-- pass translated label
        />
        <SearchBar />
        {user ? (
          <ProfileDropdown />
        ) : (
          <AuthButtons onLogin={toggleLoginModal} onSignup={toggleSignupModal} />
        )}
      </div>
    </header>
  );
};

export default Navbar;

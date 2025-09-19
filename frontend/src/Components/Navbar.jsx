// src/Components/Navbar.jsx
import React from "react";
import "../Styles/Navbar.css";
import LanguageToggle from "./LanguageToggle";
import SearchBar from "./SearchBar";
import AuthButtons from "./AuthButtons";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";              // <-- import t()

const Navbar = ({ toggleLoginModal, toggleSignupModal }) => {
  const { user } = useAuth();
  const { ui, setUi } = useUiLang();
  const withUi = useWithUi();

  return (
    <header className="navbar">
      <div className="logo">
        <NavLink to={withUi("/", ui)}>
          <img src="/images/full-logo.webp" alt="Pailin Abroad Logo" />
        </NavLink>
      </div>

      <nav className="menu">
        <ul>
          <li><NavLink to={withUi(user ? "/pathway" : "/", ui)}>{user ? "MY PATHWAY" : t("nav.home", ui)}</NavLink></li>
          <li><NavLink to={withUi("/about", ui)}>{t("nav.about", ui)}</NavLink></li>
          <li><NavLink to={withUi("/lessons", ui)}>{t("nav.lessons", ui)}</NavLink></li>
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
        <AuthButtons onLogin={toggleLoginModal} onSignup={toggleSignupModal} />
      </div>
    </header>
  );
};

export default Navbar;

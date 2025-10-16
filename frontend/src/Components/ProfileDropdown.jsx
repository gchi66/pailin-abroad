import React, { useState, useRef, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { useUiLang } from "../ui-lang/UiLangContext";
import { useWithUi } from "../ui-lang/withUi";
import { t } from "../ui-lang/i18n";
import "../Styles/ProfileDropdown.css";
import supabaseClient from "../supabaseClient";

const ProfileDropdown = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useAuth();
  const { ui } = useUiLang();
  const withUi = useWithUi();
  const navigate = useNavigate();
  const dropdownRef = useRef(null);

  const toggleDropdown = () => {
    setIsOpen(!isOpen);
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
    <div className="profile-dropdown" ref={dropdownRef}>
      <button className="profile-button" onClick={toggleDropdown}>
        <img
          src="/images/characters/pailin-blue-right.png"
          alt="Profile"
          className="profile-image"
        />
      </button>

      {isOpen && (
        <div className="dropdown-menu">
          <NavLink
            to={withUi("/pathway", ui)}
            className="dropdown-link"
            onClick={() => setIsOpen(false)}
          >
            {t("nav.myPathway", ui)}
          </NavLink>
          <NavLink
            to={withUi("/profile", ui)}
            className="dropdown-link"
            onClick={() => setIsOpen(false)}
          >
            {t("profileDropdown.accountSettings", ui)}
          </NavLink>
          <button
            className="dropdown-link logout-link"
            onClick={handleLogout}
          >
            {t("profileDropdown.logout", ui)}
          </button>
        </div>
      )}
    </div>
  );
};

export default ProfileDropdown;

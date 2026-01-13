import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "../Styles/Footer.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";

const Footer = () => {
  const { ui } = useUiLang();
  const { user } = useAuth();
  const footerCopy = copy.footer;
  const { resources, about, help } = footerCopy.sections;
  const [profile, setProfile] = useState(null);
  const year = new Date().getFullYear();

  const isExternalLink = (url = "") =>
    /^https?:\/\//i.test(url) || url.startsWith("mailto:") || url.startsWith("tel:");

  const buildInternalLink = (target) => {
    const [pathname, ...rest] = target.split("?");
    const existingSearch = rest.length ? rest.join("?") : "";
    const params = new URLSearchParams(existingSearch);
    params.set("ui", ui);
    const queryString = params.toString();
    return queryString ? `${pathname}?${queryString}` : pathname;
  };

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

  const isPaidUser = Boolean(user && profile?.is_paid);
  const resourcesItems = isPaidUser
    ? [
        { text: copy.nav.lessonLibrary, link: "/lessons" },
        { text: copy.nav.exerciseBank, link: "/exercise-bank" },
        { text: copy.nav.topicLibrary, link: "/topic-library" },
      ]
    : [
        { text: copy.nav.sampleLessons, link: "/try-lessons" },
        { text: copy.nav.lessonLibrary, link: "/lessons" },
        { text: copy.nav.freeLessons, link: "/free-lessons" },
        { text: copy.nav.exerciseBank, link: "/exercise-bank" },
        { text: copy.nav.topicLibrary, link: "/topic-library" },
      ];
  const resourcesSection = { ...resources, items: resourcesItems };

  const renderItems = (section) =>
    (section.items || []).map((item, index) => {
      const text = pick(item.text, ui);
      const { link } = item || {};

      if (!link) {
        return <li key={index} className={item.text?.en === "FAQ" ? "footer-link faq-link" : ""}>{text}</li>;
      }

      if (isExternalLink(link)) {
        return (
          <li key={index} className={item.text?.en === "FAQ" ? "footer-link faq-link" : ""}>
            <a href={link} target="_blank" rel="noopener noreferrer">
              {text}
            </a>
          </li>
        );
      }

      return (
        <li key={index} className={item.text?.en === "FAQ" ? "footer-link faq-link" : ""}>
          <Link to={buildInternalLink(link)}>{text}</Link>
        </li>
      );
    });

  return (
    <footer className="footer">
      <div className="footer-top">
        <div className="footer-container">
          <div className="footer-column">
            <h3 className="footer-title">{pick(resources.title, ui)}</h3>
            <ul>{renderItems(resourcesSection)}</ul>
          </div>
          <div className="footer-column">
            <h3 className="footer-title">{pick(about.title, ui)}</h3>
            <ul>{renderItems(about)}</ul>
          </div>
          <div className="footer-column">
            <h3 className="footer-title">{pick(help.title, ui)}</h3>
            <ul>{renderItems(help)}</ul>
          </div>
          <div className="footer-column follow-us">
            <h3 className="footer-title">{pick(footerCopy.followUsTitle, ui)}</h3>
            <div className="social-icons">
              <button className="social-icon-link">
                <img
                  src={`${process.env.PUBLIC_URL}/images/instagram-icon-black.png`}
                  alt="Instagram"
                />
              </button>
              <button className="social-icon-link">
                <img
                  src={`${process.env.PUBLIC_URL}/images/facebook-icon-black.png`}
                  alt="Facebook"
                />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <span>{pick(footerCopy.copyright, ui).replace("{year}", year)}</span>
      </div>
    </footer>
  );
};

export default Footer;

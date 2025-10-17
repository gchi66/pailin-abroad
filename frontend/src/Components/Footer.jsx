import React from "react";
import { Link } from "react-router-dom";
import "../Styles/Footer.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Footer = () => {
  const { ui } = useUiLang();
  const footerCopy = copy.footer;
  const { resources, about, help } = footerCopy.sections;
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

  const renderItems = (section) =>
    (section.items || []).map((item, index) => {
      const text = pick(item.text, ui);
      const { link } = item || {};

      if (!link) {
        return <li key={index}>{text}</li>;
      }

      if (isExternalLink(link)) {
        return (
          <li key={index}>
            <a href={link} target="_blank" rel="noopener noreferrer">
              {text}
            </a>
          </li>
        );
      }

      return (
        <li key={index}>
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
            <ul>{renderItems(resources)}</ul>
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
                  src={`${process.env.PUBLIC_URL}/images/youtube-icon-black.png`}
                  alt="YouTube"
                />
              </button>
              <button className="social-icon-link">
                <img
                  src={`${process.env.PUBLIC_URL}/images/tiktok-icon-black.png`}
                  alt="TikTok"
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

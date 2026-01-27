import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/AboutPage.css";
import AboutMethod from "../Components/AboutMethod";
import Team from "../Components/Team";

const AboutPage = () => {
  const { ui } = useUiLang();
  const sections = useMemo(
    () => [
      { label: t("aboutPage.sectionMethod", ui), slug: "the-method" },
      { label: t("aboutPage.sectionTeam", ui), slug: "our-team" }
    ],
    [ui]
  );
  const defaultSection = sections[0];
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedSection, setSelectedSection] = useState(defaultSection.label);

  useEffect(() => {
    const sectionSlug = (searchParams.get("section") || "").toLowerCase();
    const match =
      sections.find((section) => section.slug === sectionSlug) || defaultSection;
    setSelectedSection(match.label);
  }, [searchParams, sections, defaultSection]);

  const handleSectionClick = (section) => {
    setSelectedSection(section.label);
    const nextParams = new URLSearchParams(searchParams);
    if (section.slug === defaultSection.slug) {
      nextParams.delete("section");
    } else {
      nextParams.set("section", section.slug);
    }
    setSearchParams(nextParams, { replace: true });
  };

  return (
    <div className="about-page-container">
      {/* Page header */}
      <header className="about-page-header">
        <h1 className="about-page-header-text">{t("aboutPage.title", ui)}</h1>
        <p className="about-page-header-subtitle">{t("aboutPage.subtitle", ui)}</p>
      </header>

      {/* Section navigation */}
      <div className="section-btns-container">
        {sections.map((section) => (
          <button
            key={section.slug}
            className={`section-btn ${selectedSection === section.label ? "active" : ""}`}
            onClick={() => handleSectionClick(section)}
          >
            {section.label.toUpperCase()}
          </button>
        ))}
      </div>
      <div className={`about-method-section ${selectedSection === t("aboutPage.sectionMethod", ui) ? "visible" : ""}`}>
        <AboutMethod />
      </div>
      <div className={`about-method-section ${selectedSection === t("aboutPage.sectionTeam", ui) ? "visible" : ""}`}>
        <Team />
      </div>

    </div> /* page container */
  );
};

export default AboutPage;

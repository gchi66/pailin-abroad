import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import "../Styles/AboutPage.css";
import AboutMethod from "../Components/AboutMethod";
import Team from "../Components/Team";

const AboutPage = () => {
  const sections = useMemo(
    () => [
      { label: "The Method", slug: "the-method" },
      { label: "Our Team", slug: "our-team" }
    ],
    []
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
        <h1 className="about-page-header-text">About Pailin Abroad</h1>
        <p className="about-page-header-subtitle">Learn all you need to know about us - our method, our team, and our story!</p>
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
      <div className={`about-method-section ${selectedSection === "The Method" ? "visible" : ""}`}>
        <AboutMethod />
      </div>
      <div className={`about-method-section ${selectedSection === "Our Team" ? "visible" : ""}`}>
        <Team />
      </div>

    </div> /* page container */
  );
};

export default AboutPage;

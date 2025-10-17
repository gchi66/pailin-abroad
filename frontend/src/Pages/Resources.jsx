import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "../Styles/Resources.css";

const Resources = () => {
  const sections = useMemo(
    () => [
      { label: "EXERCISE BANK", slug: "exercise-bank", path: "/exercise-bank" },
      { label: "PHRASES & VERBS", slug: "phrases-verbs" },
      { label: "COMMON MISTAKES", slug: "common-mistakes" },
      { label: "CULTURE NOTES", slug: "culture-notes" },
      { label: "TOPIC LIBRARY", slug: "topic-library", path: "/topic-library" },
    ],
    []
  );

  const [activeSection, setActiveSection] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const sectionSlug = (searchParams.get("section") || "").toLowerCase();
    if (!sectionSlug) return;

    const section = sections.find((entry) => entry.slug === sectionSlug);
    if (!section) return;

    if (section.path) {
      navigate(section.path);
      return;
    }

    setActiveSection(section.slug);
  }, [navigate, searchParams, sections]);

  const handleSectionClick = (section) => {
    if (section.path) {
      navigate(section.path);
      return;
    }

    setActiveSection(section.slug);
    const nextParams = new URLSearchParams(searchParams);
    if (section.slug) {
      nextParams.set("section", section.slug);
    }
    setSearchParams(nextParams, { replace: true });
  };

  return (
    <div className="resources-page-container">
      {/* page header */}
      <header className="resources-page-header">
        <h1 className="resources-page-header-text">RESOURCES</h1>
        <p className="resources-page-header-subtitle">Explore grammar, phrases, culture notes, and more</p>
      </header>

      {/* section buttons */}
      <div className="resources-sections">
        {sections.map((section) => (
          <button
            key={section.slug}
            className={`section-btn ${activeSection === section.slug ? 'active' : ''}`}
            onClick={() => handleSectionClick(section)}
          >
            {section.label}
          </button>
        ))}
      </div>
    </div>
  );
};

export default Resources;

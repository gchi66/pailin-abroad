import React from "react";
import { Link } from "react-router-dom";
import "../Styles/Resources.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Resources = () => {
  const { ui } = useUiLang();
  const resourcesCopy = copy.resourcesPage;
  const resourceCards = [
    {
      title: "Exercise Bank",
      description: "Additional practice exercises for those difficult grammar topics",
      to: "/exercise-bank",
      disabled: false,
      image: "/images/resources_exercise_bank.webp",
    },
    {
      title: "Topic Library",
      description: "Further explorations on a range of interesting ESL topics",
      to: "/topic-library",
      disabled: false,
      image: "/images/resources_topic_library.webp",
    },
    {
      title: "Common Mistakes",
      description: "View our full library of common mistakes made by Thai speakers and how to fix them",
      disabled: true,
      badge: "COMING SOON",
      image: "/images/resources_common_mistakes.webp",
    },
    {
      title: "Phrases & Phrasal Verbs",
      description: "Explore our bank of phrases, phrasal verbs, and idioms in our lessons",
      disabled: true,
      badge: "COMING SOON",
      image: "/images/resources_phrases_and_verbs.webp",
    },
    {
      title: "Culture Notes",
      description: "View our full collection of Culture Notes from our lessons",
      disabled: true,
      badge: "COMING SOON",
      image: "/images/resources_culture_notes.webp",
    },
  ];

  return (
    <div className="resources-page-container">
      {/* page header */}
      <header className="resources-page-header">
        <h1 className="resources-page-header-text">{pick(resourcesCopy.title, ui)}</h1>
        <p className="resources-page-header-subtitle">{pick(resourcesCopy.subtitle, ui)}</p>
      </header>

      <div className="resources-cards-shell">
        <div className="resources-grid">
          {resourceCards.map((card) => {
            const CardWrapper = card.disabled ? "article" : Link;
            const wrapperProps = card.disabled
              ? { className: "resources-card resources-card-disabled", "aria-disabled": true }
              : { className: "resources-card", to: card.to || "#" };

            return (
              <CardWrapper key={card.title} {...wrapperProps}>
                <div className="resources-card-media">
                  <img src={card.image} alt={`${card.title} illustration`} />
                </div>
                <div className="resources-card-copy">
                  <h3 className="resources-card-title">{card.title}</h3>
                  <p className="resources-card-desc">{card.description}</p>
                </div>
                {card.badge && <span className="resources-card-badge">{card.badge}</span>}
              </CardWrapper>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default Resources;

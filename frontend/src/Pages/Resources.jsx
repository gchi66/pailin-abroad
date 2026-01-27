import React from "react";
import { Link } from "react-router-dom";
import "../Styles/Resources.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const Resources = () => {
  const { ui } = useUiLang();
  const resourcesCopy = copy.resourcesPage;
  const cardsCopy = resourcesCopy.cards || {};
  const comingSoon = pick(resourcesCopy.comingSoon, ui);
  const resourceCards = [
    {
      title: pick(cardsCopy.exerciseBank?.title, ui),
      description: pick(cardsCopy.exerciseBank?.description, ui),
      to: "/exercise-bank",
      disabled: false,
      image: "/images/resources_exercise_bank.webp",
    },
    {
      title: pick(cardsCopy.topicLibrary?.title, ui),
      description: pick(cardsCopy.topicLibrary?.description, ui),
      to: "/topic-library",
      disabled: false,
      image: "/images/resources_topic_library.webp",
    },
    {
      title: pick(cardsCopy.commonMistakes?.title, ui),
      description: pick(cardsCopy.commonMistakes?.description, ui),
      disabled: true,
      badge: comingSoon,
      image: "/images/resources_common_mistakes.webp",
    },
    {
      title: pick(cardsCopy.phrasesVerbs?.title, ui),
      description: pick(cardsCopy.phrasesVerbs?.description, ui),
      disabled: true,
      badge: comingSoon,
      image: "/images/resources_phrases_and_verbs.webp",
    },
    {
      title: pick(cardsCopy.cultureNotes?.title, ui),
      description: pick(cardsCopy.cultureNotes?.description, ui),
      disabled: true,
      badge: comingSoon,
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

import React from "react";
import { Link } from "react-router-dom";
import "../Styles/Resources.css";

const Resources = () => {
  const placeholderImage = "/images/books-lesson-library.webp";
  const resourceCards = [
    {
      title: "Exercise Bank",
      description: "Additional practice exercises for those difficult grammar topics",
      to: "/exercise-bank",
      disabled: false,
    },
    {
      title: "Topic Library",
      description: "Further explorations on a range of interesting ESL topics",
      to: "/topic-library",
      disabled: false,
    },
    {
      title: "Common Mistakes",
      description: "View our full library of common mistakes made by Thai speakers and how to fix them",
      disabled: true,
      badge: "COMING SOON",
    },
    {
      title: "Phrases & Phrasal Verbs",
      description: "Explore our bank of phrases, phrasal verbs, and idioms in our lessons",
      disabled: true,
      badge: "COMING SOON",
    },
    {
      title: "Culture Notes",
      description: "View our full collection of Culture Notes from our lessons",
      disabled: true,
      badge: "COMING SOON",
    },
  ];

  return (
    <div className="resources-page-container">
      {/* page header */}
      <header className="resources-page-header">
        <h1 className="resources-page-header-text">RESOURCES</h1>
        <p className="resources-page-header-subtitle">Explore grammar, phrases, culture notes, and more</p>
      </header>

      <div className="resources-grid">
        {resourceCards.map((card) => {
          const CardWrapper = card.disabled ? "article" : Link;
          const wrapperProps = card.disabled
            ? { className: "resources-card resources-card-disabled", "aria-disabled": true }
            : { className: "resources-card", to: card.to || "#" };

          return (
            <CardWrapper key={card.title} {...wrapperProps}>
              <div className="resources-card-media">
                <img src={placeholderImage} alt={`${card.title} illustration`} />
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
  );
};

export default Resources;

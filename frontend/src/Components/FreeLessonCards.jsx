import React from "react";
import { Link } from "react-router-dom";
import "../Styles/FreeLessonCards.css";
import "../Styles/FreeLessonHeader.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const FreeLessonCards = ({ showHeader = true }) => {
  const cardImages = [
    "/images/free_lesson_beginner_surf.webp",
    "/images/free_lesson_intermediate_hollywood.webp",
    "/images/free_lesson_advanced_baseball.webp",
    "/images/free_lesson_expert_spaghetti.webp",
  ];

  const { ui } = useUiLang();
  const freeCopy = copy.home.freeLessons;
  const cards = freeCopy.cards || [];

  const renderText = (node) => pick(node, ui);

  return (
    <div>
      {showHeader && (
        <section className="free-lesson-header">
          <div className="flh-line" />
          <div className="flh-bubble">
            <span className="flh-text flh-text--title">
              <span className="flh-title-line">{renderText(freeCopy.headerTitleFirst || freeCopy.headerTitle || freeCopy.header)}</span>
              <span className="flh-title-line">{renderText(freeCopy.headerTitleSecond)}</span>
            </span>
            {freeCopy.headerSubtitle && (
              <span className="flh-text flh-text--subtitle">
                {renderText(freeCopy.headerSubtitle)}
              </span>
            )}
          </div>
        </section>
      )}

      <section className="free-lesson-cards">
        {cards.map((card, idx) => (
          <Link
            key={idx}
            to="/try-lessons"
            className={`fl-card-link${idx === 3 ? " fl-card-link-disabled" : ""}`}
            onClick={(event) => {
              if (idx === 3) {
                event.preventDefault();
              }
            }}
          >
            <div className={`fl-card${idx === 3 ? " fl-card-disabled" : ""}`}>
              {idx === 3 && (
                <span className="fl-card-comingsoon">{renderText(freeCopy.comingSoon)}</span>
              )}
              <span className="fl-card-level">{renderText(card.level)}</span>
              <h3 className="fl-card-title">{renderText(card.title)}</h3>
              <img
                src={cardImages[idx]}
                alt={`Illustration for ${renderText(card.title)}`}
                className="fl-card-img"
              />
              <span className="fl-card-focus">{renderText(card.focusLabel)}</span>
              <p className="fl-card-desc">{renderText(card.description)}</p>
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
};

export default FreeLessonCards;

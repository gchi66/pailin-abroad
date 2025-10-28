import React from "react";
import { Link } from "react-router-dom";
import "../Styles/FreeLessonCards.css";
import "../Styles/FreeLessonHeader.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const FreeLessonCards = ({ showHeader = true }) => {
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
            <span className="flh-text">{renderText(freeCopy.header)}</span>
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
              <img src="/images/globe.webp" alt="Lesson globe" className="fl-card-img" />
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

import React from "react";
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
          <div className={`fl-card${idx === 3 ? " fl-card-disabled" : ""}`} key={idx}>
            {idx === 3 && (
              <span className="fl-card-comingsoon">{renderText(freeCopy.comingSoon)}</span>
            )}
            <span className="fl-card-level">{renderText(card.level)}</span>
            <h3 className="fl-card-title">{renderText(card.title)}</h3>
            <img src="/images/globe.webp" alt="Lesson globe" className="fl-card-img" />
            <span className="fl-card-focus">{renderText(card.focusLabel)}</span>
            <p className="fl-card-desc">{renderText(card.description)}</p>
            {/* <button className="fl-card-btn" disabled={idx === 3}>
              {renderText(freeCopy.button)}
            </button> */}
          </div>
        ))}
      </section>
    </div>
  );
};

export default FreeLessonCards;

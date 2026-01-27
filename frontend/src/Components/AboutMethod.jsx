// AboutMethod.jsx
import React, { useState } from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/AboutMethod.css";

const AboutMethod = () => {
  const [expandedCards, setExpandedCards] = useState({ 0: true });
  const { ui } = useUiLang();

  const toggleCard = (index) => {
    setExpandedCards(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  };

  const cards = [
    {
      header: t("aboutMethod.card1Header", ui),
      content: (
        <>
          {t("aboutMethod.card1P1", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card2Header", ui),
      content: (
        <>
          {t("aboutMethod.card2P1", ui)}
          <br /><br />
          {t("aboutMethod.card2P2", ui)}
          <br /><br />
          {t("aboutMethod.card2DidYouKnow", ui)}
        </>
      ),
      hasImage: true
    },
    {
      header: t("aboutMethod.card3Header", ui),
      content: (
        <>
          {t("aboutMethod.card3P1", ui)}
          <br /><br />
          {t("aboutMethod.card3P2", ui)}
          <br /><br />
          {t("aboutMethod.card3P3", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card4Header", ui),
      content: (
        <>
          {t("aboutMethod.card4P1", ui)}
          <br /><br />
          {t("aboutMethod.card4P2", ui)}
          <br /><br />
          {t("aboutMethod.card4P3", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card5Header", ui),
      content: (
        <>
          {t("aboutMethod.card5Intro", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card5Strong1", ui)}</strong>
          <br />
          {t("aboutMethod.card5P1", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card5Strong2", ui)}</strong>
          <br />
          {t("aboutMethod.card5P2", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card6Header", ui),
      content: (
        <>
          <strong>{t("aboutMethod.card6StrongIntro", ui)}</strong>
          <br />
          {t("aboutMethod.card6P1", ui)}
          <br /><br />
          {t("aboutMethod.card6P2", ui)}
          <br /><br />
          {t("aboutMethod.card6P3", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card7Header", ui),
      content: (
        <>
          {t("aboutMethod.card7Intro", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7AudioTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7AudioBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7FocusTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7FocusBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7ComprehensionTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7ComprehensionBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7ApplyTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7ApplyBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7UnderstandTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7UnderstandBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7TipsTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7TipsBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7MistakesTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7MistakesBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7PhrasesTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7PhrasesBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7CultureTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7CultureBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7PracticeTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7PracticeBody", ui)}
          <br /><br />
          <strong>{t("aboutMethod.card7CommentTitle", ui)}</strong>
          <br />
          {t("aboutMethod.card7CommentBody", ui)}
        </>
      )
    },
    {
      header: t("aboutMethod.card8Header", ui),
      content: (
        <>
          {t("aboutMethod.card8P1", ui)}
          <br /><br />
          {t("aboutMethod.card8P2", ui)}
          <br /><br />
          {t("aboutMethod.card8P3", ui)}
        </>
      )
    }
  ];

  return (
    <div className="about-method-cards-container">
      {cards.map((card, index) => (
        <div
          key={index}
          className={`about-method-card ${expandedCards[index] ? 'expanded' : ''}`}
          onClick={() => toggleCard(index)}
        >
          <div className={`about-method-card-header-container ${expandedCards[index] ? 'expanded' : ''}`}>
            <span className="about-method-card-header">
              {card.header}
            </span>
            <svg
              className={`about-method-card-arrow ${expandedCards[index] ? 'expanded' : ''}`}
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#1E1E1E"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </div>

          {expandedCards[index] && (
            <>
              <hr className="about-method-card-line" />

              <div className="about-method-card-content">
                {card.hasImage && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}

                <span className="about-method-card-text">
                  {card.content}
                </span>

                {card.hasImage && card.align === 'right' && (
                  <img
                    src="/images/characters/im-pailin.png"
                    alt="I'm Pailin"
                    className="about-im-pailin-pic"
                  />
                )}
              </div>
            </>
          )}
        </div>
      ))}
    </div>
  );
};

// Ensure this is the only default export in the file
export default AboutMethod;

import React, { useState } from "react";
import "../Styles/FAQ.css";
import { useUiLang } from "../ui-lang/UiLangContext";
import { copy, pick } from "../ui-lang/i18n";

const FAQ = () => {
  const { ui } = useUiLang();
  const faqCopy = copy.home.faq;
  const items = faqCopy.items || [];
  const [openCard, setOpenCard] = useState(null);

  const toggleCard = (cardId) => {
    setOpenCard(openCard === cardId ? null : cardId);
  };

  return (
    <section className="faq-section">
      <h2 className="faq-title">{pick(faqCopy.title, ui)}</h2>
      <div className="faq-cards-container">
        {items.map((faq) => (
          <div key={faq.id} className="faq-card">
            <div
              className="faq-header"
              onClick={() => toggleCard(faq.id)}
            >
              <h3 className="faq-question">{pick(faq.question, ui)}</h3>
              <span className={`faq-arrow ${openCard === faq.id ? "open" : ""}`}>
                ▼
              </span>
            </div>
            <div className={`faq-content ${openCard === faq.id ? "open" : ""}`}>
              <p className="faq-answer">{pick(faq.answer, ui)}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default FAQ;

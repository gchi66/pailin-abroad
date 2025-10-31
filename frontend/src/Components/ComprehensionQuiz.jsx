import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ComprehensionQuiz.css";
import { copy, pick } from "../ui-lang/i18n";

export default function ComprehensionQuiz({ questions = [], uiLang = "en", images = {} }) {
  const [selected, setSelected] = useState({}); // { [qId]: ["A","C"] }
  const [checked, setChecked] = useState(false);
  const quizCopy = copy.lessonPage.quiz;

  const toggle = (qId, letter, isMulti) =>
    setSelected((prev) => {
      const prevList = prev[qId] || [];
      const nextList = isMulti
        ? prevList.includes(letter)
          ? prevList.filter((l) => l !== letter)
          : [...prevList, letter]
        : [letter];
      const updated = { ...prev, [qId]: nextList };
      setChecked(false);
      return updated;
    });

const parseOptions = (q) => {
  const rawEn = Array.isArray(q.options) ? q.options : [];
  const rawTh = Array.isArray(q.options_th) ? q.options_th : [];

  const splitThaiText = (value = "") => {
    const thaiRegex = /[\u0E00-\u0E7F]/;
    const segments = String(value)
      .split(/\r?\n+/)
      .map((segment) => segment.trim())
      .filter(Boolean);

    if (!segments.length) {
      return { en: "", th: "" };
    }

    let english = "";
    let thai = "";

    segments.forEach((segment) => {
      if (thaiRegex.test(segment)) {
        thai = thai ? `${thai}\n${segment}` : segment;
      } else if (!english) {
        english = segment;
      } else {
        english = `${english}\n${segment}`;
      }
    });

    if (!english && segments.length) {
      english = segments[0];
    }

    return { en: english, th: thai };
  };

  const parseSingle = (opt) => {
    if (typeof opt === "string") {
      const match = opt.match(/^([A-Z])\.\s*(.*)$/s);
      const label = match ? match[1] : "";
      const body = match ? match[2] : opt;
      const { en, th } = splitThaiText(body);
      return { label, text: en, textTh: th };
    }

    const { en, th } = splitThaiText(opt.text || "");

    return {
      label: opt.label || opt.letter || "",
      text: en,
      textTh: opt.text_th || opt.textTh || th,
      image_key: opt.image_key || null,
      alt_text: opt.alt_text || "",
    };
  };

  return rawEn.map((opt, idx) => {
    const parsed = parseSingle(opt);
    const thOpt = rawTh[idx];

    if (!parsed.textTh && thOpt != null) {
      const parsedTh = parseSingle(thOpt);
      parsed.textTh = parsedTh.text || "";
      if (!parsed.label && parsedTh.label) {
        parsed.label = parsedTh.label;
      }
    }

    return parsed;
  });
};

  const checkAnswers = () => {
    setChecked(true);
  };

  return (
    <>
      <div className="cq-questions">
        {questions.map((q, idx) => {
          const prompt = uiLang === "th" && q.prompt_th ? q.prompt_th : q.prompt;
          const opts = parseOptions(q);
          const isMulti = (q.answer_key || []).length > 1;
          const questionNumber = q.sort_order ?? idx + 1;
          const currentSelections = selected[q.id] || [];
          const answerSet = new Set(q.answer_key || []);

          return (
            <div key={q.id} className="fb-row cq-question">
              <div className="fb-row-number">
                <span>{questionNumber}</span>
              </div>

              <div className="fb-row-main">
                <div className="fb-row-content">
                  <div className="cq-prompt">
                    <ReactMarkdown>{prompt}</ReactMarkdown>
                  </div>

                  <div className="cq-option-list">
                    {opts.map(({ label, text, textTh, image_key, alt_text }) => {
                      const isSelected = currentSelections.includes(label);

                      const shouldShowOptionResult = checked && isSelected;
                      const isOptionCorrect = answerSet.has(label);

                      return (
                        <div key={label + text} className="cq-option-item">
                          <button
                          type="button"
                          className={isSelected ? "cq-letter selected" : "cq-letter"}
                          onClick={() => toggle(q.id, label, isMulti)}
                          aria-pressed={isSelected}
                          >
                          {label}
                          </button>
                          <span className="cq-option-text">
                            {image_key && (
                              <img
                                src={images[image_key]}
                                alt={alt_text || text || textTh || ""}
                                className="cq-option-image"
                              />
                            )}
                            {(text || textTh) && (
                              <span className="cq-option-text-lines">
                                {text && (
                                  <span className="cq-option-text-en">{text}</span>
                                )}
                                {textTh && (
                                  <span className="cq-option-text-th">{textTh}</span>
                                )}
                              </span>
                            )}
                            {shouldShowOptionResult && (
                              <span
                                className={
                                  isOptionCorrect
                                    ? "cq-option-result correct"
                                    : "cq-option-result incorrect"
                                }
                              >
                                {isOptionCorrect ? "✓" : "✗"}
                              </span>
                            )}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        <button
          type="button"
          className="apply-submit cq-check-btn"
          onClick={checkAnswers}
        >
          {pick(quizCopy.checkAnswers, uiLang)}
        </button>
      </div>
    </>
  );
}

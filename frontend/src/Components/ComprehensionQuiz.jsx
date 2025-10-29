import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ComprehensionQuiz.css";
import { copy, pick } from "../ui-lang/i18n";

export default function ComprehensionQuiz({ questions = [], uiLang = "en", images = {} }) {
  const [selected, setSelected] = useState({}); // { [qId]: ["A","C"] }
  const [results, setResults] = useState({}); // { [qId]: "correct" | "incorrect" }
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
      return { ...prev, [qId]: nextList };
    });

  const parseOptions = (q) => {
    const rawOpts = Array.isArray(q.options) ? q.options : [];
    return rawOpts.map((opt) => {
      if (typeof opt === "string") {
        const m = opt.match(/^([A-Z])\.\s*(.*)$/s);
        if (m) return { label: m[1], text: m[2] };
        return { label: "", text: opt };
      }
      return {
        label: opt.label || opt.letter || "",
        text: opt.text || "",
        image_key: opt.image_key || null,
        alt_text: opt.alt_text || "",
      };
    });
  };

  const checkAnswers = () => {
    const res = {};
    questions.forEach((q) => {
      const sel = (selected[q.id] || []).sort();
      const ans = (q.answer_key || []).sort();
      res[q.id] =
        sel.length &&
        sel.length === ans.length &&
        sel.every((l, i) => l === ans[i])
          ? "correct"
          : "incorrect";
    });
    setResults(res);
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
          const resultState = results[q.id];

          return (
            <div key={q.id} className="fb-row cq-question">
              <div className="fb-row-number">
                <span>{questionNumber}</span>
              </div>

              <div className="fb-row-main">
                <div className="fb-row-content">
                  <div className="cq-prompt">
                    <ReactMarkdown>{prompt}</ReactMarkdown>

                    {checked && (
                      <span
                        className={
                          resultState === "correct"
                            ? "cq-result correct"
                            : "cq-result incorrect"
                        }
                      >
                        {resultState === "correct" ? "✓" : "✗"}
                      </span>
                    )}
                  </div>

                  <div className="cq-option-list">
                    {opts.map(({ label, text, image_key, alt_text }) => {
                      const isSelected = currentSelections.includes(label);

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
                            {image_key ? (
                              <>
                                <img
                                  src={images[image_key]}
                                  alt={alt_text || text}
                                  className="cq-option-image"
                                />
                                {text && <span>{text}</span>}
                              </>
                            ) : (
                              text
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
      </div>

      <button
        type="button"
        className="cq-check-btn language-toggle-btn"
        onClick={checkAnswers}
      >
        {pick(quizCopy.checkAnswers, uiLang)}
      </button>
    </>
  );
}

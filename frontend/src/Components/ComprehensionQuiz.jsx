import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ComprehensionQuiz.css";
import { copy, pick } from "../ui-lang/i18n";

export default function ComprehensionQuiz({ questions = [], uiLang = "en", images = {} }) {
  const [selected, setSelected] = useState({});   // { [qId]: ["A","C"] }
  const [results,  setResults]  = useState({});   // { [qId]: "correct" | "incorrect" }
  const [checked,  setChecked]  = useState(false);
  const quizCopy = copy.lessonPage.quiz;

  /* toggle one letter */
  const toggle = (qId, letter, isMulti) =>
    setSelected((prev) => {
      const prevList = prev[qId] || [];
      const nextList = isMulti
        ? prevList.includes(letter)
          ? prevList.filter((l) => l !== letter)
          : [...prevList, letter]
        : [letter];                               // radio style
      return { ...prev, [qId]: nextList };
    });

  /* Normalize options to structured objects: {label,text,image_key,alt_text} */
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

  /* ---------------------------------- check answers */
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
  /* ------------------------------------------------- */

  return (
    <>
      <ol className="cq-questions">
        {questions.map((q) => {
          const prompt =
            uiLang === "th" && q.prompt_th ? q.prompt_th : q.prompt;
          const opts    = parseOptions(q);
          const isMulti = (q.answer_key || []).length > 1;

          return (
            <li key={q.id} className="cq-question-item">
              <div className="cq-prompt">
                <ReactMarkdown>{prompt}</ReactMarkdown>

                {checked && (
                  <span
                    className={
                      results[q.id] === "correct"
                        ? "cq-result correct"
                        : "cq-result incorrect"
                    }
                  >
                    {results[q.id] === "correct" ? "✓" : "✗"}
                  </span>
                )}
              </div>

              <div className="cq-option-list">
                {opts.map(({ label, text, image_key, alt_text }) => (
                  <div key={label + text} className="cq-option-item">
                    <button
                      type="button"
                      className={
                        (selected[q.id] || []).includes(label)
                          ? "cq-letter selected"
                          : "cq-letter"
                      }
                      onClick={() => toggle(q.id, label, isMulti)}
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
                            style={{ maxWidth: 120, display: "block" }}
                          />
                          {text && <span>{text}</span>}
                        </>
                      ) : (
                        text
                      )}
                    </span>
                  </div>
                ))}
              </div>
            </li>
          );
        })}
      </ol>

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

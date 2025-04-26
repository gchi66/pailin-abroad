import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ComprehensionQuiz.css";

export default function ComprehensionQuiz({ questions = [], uiLang = "en" }) {
  const [selected, setSelected] = useState({});   // { [qId]: ["A","C"] }
  const [results,  setResults]  = useState({});   // { [qId]: "correct" | "incorrect" }
  const [checked,  setChecked]  = useState(false);

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

  /* turn options (string[] or inline) → [{letter,text}] */
  const parseOptions = (q) => {
    let optStrings =
      uiLang === "th" && Array.isArray(q.options_th) && q.options_th.length
        ? q.options_th
        : q.options;

    if (!Array.isArray(optStrings) || !optStrings.length) {
      const raw = uiLang === "th" && q.prompt_th ? q.prompt_th : q.prompt;
      const lines = raw.split("\n").map((l) => l.trim()).filter(Boolean);
      optStrings = lines.slice(1);
    }

    return optStrings.map((str) => {
      const [letter, ...rest] = str.split(". ");
      return { letter: letter.trim(), text: rest.join(". ").trim() };
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
                {opts.map(({ letter, text }) => (
                  <div key={letter} className="cq-option-item">
                    <button
                      type="button"
                      className={
                        (selected[q.id] || []).includes(letter)
                          ? "cq-letter selected"
                          : "cq-letter"
                      }
                      onClick={() => toggle(q.id, letter, isMulti)}
                    >
                      {letter}
                    </button>
                    <span className="cq-option-text">{text}</span>
                  </div>
                ))}
              </div>
            </li>
          );
        })}
      </ol>

      <button
        type="button"
        className="cq-check-btn"
        onClick={checkAnswers}
      >
        Check answers
      </button>
    </>
  );
}

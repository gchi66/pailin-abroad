import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ComprehensionQuiz.css";

export default function ComprehensionQuiz({ questions = [], uiLang = "en" }) {
  // track which letters are selected per question
  const [selected, setSelected] = useState({});

  const toggle = (qId, letter) => {
    setSelected((prev) => {
      const prevList = prev[qId] || [];
      const isOn = prevList.includes(letter);
      const nextList = isOn
        ? prevList.filter((l) => l !== letter)
        : [...prevList, letter];
      return { ...prev, [qId]: nextList };
    });
  };

  return (
    <ol className="cq-questions">
      {questions.map((q) => {
        // split prompt + options
        const raw = uiLang === "th" && q.prompt_th ? q.prompt_th : q.prompt;
        const lines = raw
          .split("\n")
          .map((l) => l.trim())
          .filter(Boolean);
        const prompt = lines[0];
        const opts = lines.slice(1).map((line) => {
          const [letter, ...rest] = line.split(". ");
          return { letter, text: rest.join(". ") };
        });

        return (
          <li key={q.id} className="cq-question-item">
          {console.log(q)};
            <div className="cq-prompt">
              <ReactMarkdown>{prompt}</ReactMarkdown>
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
                    onClick={() => toggle(q.id, letter)}
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
  );
}

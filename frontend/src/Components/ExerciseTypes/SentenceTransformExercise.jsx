import React, { useState } from "react";

export default function SentenceTransformExercise({ exercise = {} }) {
  const { title = "", prompt = "", items = [] } = exercise || {};
  const [answers, setAnswers] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
  };

  const passed = (idx) => {
    if (!checked) return null;

    const item = items[idx];
    const isCorrect = item.correct === "yes";

    // For sentences that are already correct (correct === "yes"),
    // the user might just leave it blank or write the original sentence
    if (isCorrect) {
      // If they left it blank, that's correct too
      if (!answers[idx].trim()) return true;

      // If they wrote something, it should match the original text
      const originalText = item.text.toLowerCase().replace(/\s+/g, " ").trim();
      const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();
      return got === originalText;
    }

    // For sentences that need transformation, check against possible answers
    if (!item.answer) return false;

    // Split answer by comma to handle multiple acceptable answers
    const acceptableAnswers = item.answer.split(',').map(ans =>
      ans.toLowerCase().replace(/\s+/g, " ").trim()
    );
    const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();

    return acceptableAnswers.includes(got);
  };

  return (
    <div className="st-wrap">
      {prompt && <p className="st-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        const isCorrect = item.correct === "yes";

        return (
          <div key={`question-${idx}`} className="st-question">
            <p className="st-stem">{item.number}. {item.text}</p>
            <div className="st-input-container">
              <input
                type="text"
                value={answers[idx]}
                onChange={(e) => handleChange(idx, e.target.value)}
                disabled={checked}
                placeholder={isCorrect ? "This sentence is correct (leave blank or rewrite)" : "Correct this sentence"}
                className="st-input"
              />

              {checked && (
                <span className={`st-mark ${passed(idx) ? "correct" : "wrong"}`}>
                  {passed(idx) ? "✓" : "✗"}
                </span>
              )}
            </div>

            {checked && !passed(idx) && (
              <p className="st-correct-answer">
                <span className="st-label">Correct answer:</span>{" "}
                {isCorrect ? "(The sentence is already correct)" : item.answer}
              </p>
            )}
          </div>
        );
      })}

      <div className="st-buttons">
        {!checked ? (
          <button
            onClick={() => setChecked(true)}
            className="st-btn check"
          >
            Check
          </button>
        ) : (
          <button
            onClick={() => {
              setAnswers(Array(items.length).fill(""));
              setChecked(false);
            }}
            className="st-btn reset"
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}

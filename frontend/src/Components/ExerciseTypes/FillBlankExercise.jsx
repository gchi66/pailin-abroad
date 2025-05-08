import React, { useState } from "react";

/**
 * Fill-in-the-blank component that supports
 *   • paragraph exercises  – exercise.paragraph !== ""
 *   • row exercises        – each item.text contains ____ (underscores)
 */
export default function FillBlankExercise({ exercise }) {
  // IMPORTANT: Make sure the exercise object is properly structured
  // Explicitly check for the paragraph property
  const { title, prompt, paragraph, items = [] } = exercise || {};

  // Debug log to see what we're receiving
  console.log("Exercise object:", exercise);
  console.log("Paragraph:", paragraph);
  console.log("Has paragraph?", Boolean(paragraph));

  /* ---------- state ---------- */
  const [inputs, setInputs] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);

  /* ---------- helpers ---------- */
  const handleChange = (idx, val) => {
    const next = [...inputs];
    next[idx] = val;
    setInputs(next);
  };

  const isCorrect = (idx) => {
    if (!checked) return null;
    const correctAnswer = items[idx]?.answer?.toLowerCase()?.trim() || "";
    const userAnswer = inputs[idx]?.toLowerCase()?.trim() || "";
    return userAnswer && correctAnswer.includes(userAnswer);
  };

  const handleCheck = () => setChecked(true);
  const handleReset = () => { setInputs(Array(items.length).fill("")); setChecked(false); };

  /* ================================================================
   *  RENDER – PARAGRAPH STYLE
   * ================================================================ */
  // Strengthen the check for paragraph - make sure it's a non-empty string
  if (paragraph && typeof paragraph === 'string' && paragraph.trim() !== '') {
    console.log("Using paragraph style");

    // Fixed regex to match ___1___ pattern
    const parts = paragraph.split(/___([\d]+)___/g);
    console.log("Paragraph parts:", parts);

    return (
      <div className="fb-wrap">
        {title && <h3 className="fb-title">{title}</h3>}
        {prompt && <p className="fb-prompt">{prompt}</p>}

        <p className="fb-paragraph">
          {parts.map((part, idx) =>
            /* even indices = plain text */
            idx % 2 === 0 ? (
              <span key={`text-${idx}`}>{part}</span>
            ) : (
              /* odd indices = number placeholder */
              <span key={`blank-${idx}`} className="fb-inline">
                <input
                  type="text"
                  className="fb-input"
                  value={inputs[parseInt(part) - 1] || ""}
                  onChange={(e) => handleChange(parseInt(part) - 1, e.target.value)}
                  disabled={checked}
                  placeholder="___"
                />
                {checked && (
                  <span className={`fb-mark ${isCorrect(parseInt(part) - 1) ? "correct" : "wrong"}`}>
                    {isCorrect(parseInt(part) - 1) ? "✓" : "✗"}
                    {!isCorrect(parseInt(part) - 1) && (
                      <span className="correct-answer">
                        {" "}(Correct: {items[parseInt(part) - 1].answer})
                      </span>
                    )}
                  </span>
                )}
              </span>
            )
          )}
        </p>

        <Buttons
          checked={checked}
          inputs={inputs}
          handleCheck={handleCheck}
          handleReset={handleReset}
        />
      </div>
    );
  }

  /* ================================================================
   *  RENDER – ROW STYLE
   * ================================================================ */
  console.log("Using row style");
  return (
    <div className="fb-wrap">
      {title && <h3 className="fb-title">{title}</h3>}
      {prompt && <p className="fb-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        // split at the first run of underscores (___ or ____)
        const parts = item.text.split(/_+/);
        return (
          <div key={`${item.number}-${idx}`} className="fb-row">
            {parts[0]}
            <input
              type="text"
              className="fb-input"
              value={inputs[idx]}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={checked}
              placeholder="___"
            />
            {parts[1] /* might be undefined but that's fine */}
            {checked && (
              <span className={`fb-mark ${isCorrect(idx) ? "correct" : "wrong"}`}>
                {isCorrect(idx) ? "✓" : "✗"}
                {!isCorrect(idx) && (
                  <span className="correct-answer">
                    {" "}(Correct: {items[idx].answer})
                  </span>
                )}
              </span>
            )}
          </div>
        );
      })}

      <Buttons
        checked={checked}
        inputs={inputs}
        handleCheck={handleCheck}
        handleReset={handleReset}
      />
    </div>
  );
}

/* ------------------------------------------------
 *  Re-usable buttons block
 * ------------------------------------------------ */
function Buttons({ checked, inputs, handleCheck, handleReset }) {
  return (
    <div className="fb-button-container">
      {!checked ? (
        <button
          className="fb-btn check"
          onClick={handleCheck}
          disabled={inputs.every((input) => !input.trim())}
        >
          Check Answers
        </button>
      ) : (
        <button className="fb-btn reset" onClick={handleReset}>
          Try Again
        </button>
      )}
    </div>
  );
}

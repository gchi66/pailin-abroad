import React, { useState } from "react";

/**
 * Fill-in-the-blank component that supports
 *   • paragraph exercises  – exercise.paragraph !== ""
 *   • row exercises        – each item.text contains ____ (underscores)
 */
export default function FillBlankExercise({ exercise }) {
  const { title, prompt, paragraph, items = [] } = exercise || {};

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
  const handleReset = () => {
    setInputs(Array(items.length).fill(""));
    setChecked(false);
  };

  // Create answer key from items array for paragraph style
  const answerKey = items.reduce((acc, item) => {
    acc[item.number] = item.answer.toLowerCase().trim();
    return acc;
  }, {});

  // Handle input changes for paragraph style (by question number)
  const handleParagraphInputChange = (number, value) => {
    const itemIndex = items.findIndex(item => item.number === number);
    if (itemIndex !== -1) {
      handleChange(itemIndex, value);
    }
  };

  // Check if paragraph answer is correct by question number
  const isParagraphCorrect = (number) => {
    const itemIndex = items.findIndex(item => item.number === number);
    return isCorrect(itemIndex);
  };

  // Get user answer for paragraph style
  const getParagraphUserAnswer = (number) => {
    const itemIndex = items.findIndex(item => item.number === number);
    return inputs[itemIndex] || '';
  };

  // Convert paragraph with **number** or ___number___ markers to JSX with input fields
  const renderParagraphWithInputs = (paragraph) => {
    // Handle both **number** and ___number___ formats
    const parts = paragraph.split(/(\*\*\d+\*\*|_{2,3}\d+_{2,3})/);

    return parts.map((part, index) => {
      // Check for **number** format
      let numberMatch = part.match(/\*\*(\d+)\*\*/);
      // Check for ___number___ format if first didn't match
      if (!numberMatch) {
        numberMatch = part.match(/_{2,3}(\d+)_{2,3}/);
      }

      if (numberMatch) {
        const number = numberMatch[1];
        const inputValue = getParagraphUserAnswer(number);

        return (
          <span key={index} className="fb-inline">
            <input
              type="text"
              className="fb-input"
              value={inputValue}
              onChange={(e) => handleParagraphInputChange(number, e.target.value)}
              disabled={checked}
              placeholder="___"
            />
            {checked && (
              <span className={`fb-mark ${isParagraphCorrect(number) ? "correct" : "wrong"}`}>
                {isParagraphCorrect(number) ? "✓" : "✗"}
                {!isParagraphCorrect(number) && (
                  <span className="correct-answer">
                    {" "}(Correct: {answerKey[number]})
                  </span>
                )}
              </span>
            )}
          </span>
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  /* ================================================================
   *  RENDER – PARAGRAPH STYLE
   * ================================================================ */
  if (paragraph && typeof paragraph === 'string' && paragraph.trim() !== '') {
    return (
      <div className="fb-wrap">
        {title && <h3 className="fb-title">{title}</h3>}
        {prompt && <p className="fb-prompt">{prompt}</p>}

        <p className="fb-paragraph">
          {renderParagraphWithInputs(paragraph)}
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
            {parts[1]}
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

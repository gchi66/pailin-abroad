import React, { useState } from "react";

export default function FillBlankExercise({ exercise }) {
  const { title, prompt, items = [] } = exercise;
  const [inputs, setInputs] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);

  const handleChange = (idx, val) => {
    const next = [...inputs];
    next[idx] = val;
    setInputs(next);
  };

  const isCorrect = (idx) => {
    if (!checked) return null;
    const correctAnswer = items[idx]?.answer?.toLowerCase()?.trim() || "";
    const userAnswer = inputs[idx]?.toLowerCase()?.trim() || "";
    return userAnswer && userAnswer.includes(correctAnswer);
  };

  const handleCheck = () => setChecked(true);
  const handleReset = () => {
    setInputs(Array(items.length).fill(""));
    setChecked(false);
  };

  return (
    <div className="fb-wrap">
      {/* Debug output - remove after verification */}
      <div style={{ display: 'none' }}>
        <pre>{JSON.stringify(exercise, null, 2)}</pre>
      </div>

      {title && <h3 className="fb-title">{title}</h3>}
      {prompt && <p className="fb-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        const [beforeBlank, afterBlank] = item.text.split("___");
        return (
          <div key={`${item.number}-${idx}`} className="fb-row">
            <label>
              {beforeBlank}
              <input
                type="text"
                value={inputs[idx]}
                onChange={(e) => handleChange(idx, e.target.value)}
                disabled={checked}
                className="fb-input"
                placeholder="Type your answer here"
              />
              {afterBlank}
            </label>
            {checked && (
              <span className={`fb-mark ${isCorrect(idx) ? "correct" : "wrong"}`}>
                {isCorrect(idx) ? "✓" : "✗"}
                {!isCorrect(idx) && (
                  <span className="correct-answer"> (Correct: {items[idx].answer})</span>
                )}
              </span>
            )}
          </div>
        );
      })}

      <div className="fb-button-container">
        {!checked ? (
          <button
            className="fb-btn check"
            onClick={handleCheck}
            disabled={inputs.every(input => !input.trim())}
          >
            Check Answers
          </button>
        ) : (
          <button className="fb-btn reset" onClick={handleReset}>
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}

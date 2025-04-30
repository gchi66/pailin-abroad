import React, { useState } from "react";

export default function FillBlankExercise({ exercise }) {
  const { prompt, options = [], answer_key = [] } = exercise;
  const [inputs, setInputs]   = useState(Array(options.length).fill(""));
  const [checked, setChecked] = useState(false);

  const handleChange = (idx, val) => {
    const next = [...inputs];
    next[idx] = val;
    setInputs(next);
  };

  const handleCheck = () => setChecked(true);

  const isCorrect = (idx) => {
    if (!checked) return null;
    if (!answer_key.length) return inputs[idx].trim().length > 0;
    const want = answer_key[idx].toLowerCase();
    return inputs[idx].toLowerCase().startsWith(want);
  };

  return (
    <div className="fb-wrap">
      <p className="fb-prompt">{prompt}</p>

      {options.map((stem, idx) => (
        <div key={idx} className="fb-row">
          <label>
            {stem.replace(/___/, "")}
            <input
              type="text"
              value={inputs[idx]}
              onChange={(e) => handleChange(idx, e.target.value)}
              disabled={checked}
            />
          </label>
          {checked && (
            <span className={`fb-mark ${isCorrect(idx) ? "correct" : "wrong"}`}>
              {isCorrect(idx) ? "✓" : "✗"}
            </span>
          )}
        </div>
      ))}

      {!checked && (
        <button className="fb-btn" onClick={handleCheck}>
          Check
        </button>
      )}
    </div>
  );
}

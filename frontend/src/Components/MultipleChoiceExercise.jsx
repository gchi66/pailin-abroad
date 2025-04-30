import React, { useState } from "react";

export default function MultipleChoiceExercise({ exercise }) {
  const { prompt, options = [], answer_key = [] } = exercise;
  const [choice, setChoice]   = useState(null);
  const [checked, setChecked] = useState(false);

  const correctLetter = answer_key[0]?.match(/[A-Z]/)?.[0] || null;
  const isCorrect = checked && correctLetter && choice === correctLetter;

  return (
    <div className="mc-wrap">
      <p className="mc-prompt">{prompt}</p>

      <ul className="mc-options">
        {options.map((optLine) => {
          const letter = optLine.match(/^[A-Z]/)?.[0];
          const text   = optLine.replace(/^[A-Z]\)\s*/, "");

          return (
            <li key={letter}>
              <label>
                <input
                  type="radio"
                  name="mc"
                  value={letter}
                  disabled={checked}
                  onChange={() => setChoice(letter)}
                />
                {letter}) {text}
              </label>
            </li>
          );
        })}
      </ul>

      {!checked ? (
        <button
          className="mc-btn"
          disabled={choice == null}
          onClick={() => setChecked(true)}
        >
          Check
        </button>
      ) : (
        <p className="mc-feedback">
          {isCorrect ? "✓ Correct!" : `✗ Correct answer: ${correctLetter}`}
        </p>
      )}
    </div>
  );
}

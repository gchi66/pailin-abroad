import React, { useState } from "react";

export default function MultipleChoiceExercise({ exercise }) {
  const { items = [] } = exercise;
  const [choices, setChoices] = useState(Array(items.length).fill(null));
  const [checked, setChecked] = useState(false);

  const pick = (qIdx, letter) => {
    const next = [...choices];
    next[qIdx] = letter;
    setChoices(next);
  };

  const allAnswered = choices.every(c => c);
  const score =
    checked ? choices.filter((c, i) => c === items[i].answer).length : null;

  return (
    <div className="mc-wrap">
      {items.map((q, qIdx) => (
        <fieldset key={qIdx} className="mc-fieldset">
          <legend>{q.text}</legend>
          <ul className="mc-options">
            {q.options.map((optLine) => {
              const letter = optLine.match(/^[A-Z]/)?.[0];     // “A”
              const text   = optLine.replace(/^[A-Z]\.\s*/, ""); // “Please.”
              return (
                <li key={`${qIdx}-${letter}`}>
                  <label>
                    <input
                      type="radio"
                      name={`mc-${exercise.id}-${qIdx}`} // unique group
                      value={letter}
                      checked={choices[qIdx] === letter}
                      disabled={checked}
                      onChange={() => pick(qIdx, letter)}
                    />
                    {letter}. {text}
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>
      ))}

      {!checked ? (
        <button
          className="mc-btn"
          disabled={!allAnswered}
          onClick={() => setChecked(true)}
        >
          Check
        </button>
      ) : (
        <p className="mc-feedback">
          You got {score} / {items.length} correct.
        </p>
      )}
    </div>
  );
}

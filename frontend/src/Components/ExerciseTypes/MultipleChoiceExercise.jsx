import React, { useState } from "react";
import AudioButton from "../AudioButton";

export default function MultipleChoiceExercise({ exercise, images = {}, audioIndex = {} }) {
  const { title, prompt, items = [] } = exercise;
  const [choices, setChoices] = useState(Array(items.length).fill(null));
  const [checked, setChecked] = useState(false);

  const pick = (qIdx, letter) => {
    const next = [...choices];
    next[qIdx] = letter;
    setChoices(next);
  };

  const allAnswered = choices.every(c => c);
  const score = checked ? choices.filter((c, i) => c === items[i].answer).length : null;

  const resetExercise = () => {
    setChoices(Array(items.length).fill(null));
    setChecked(false);
  };

  return (
    <div className="mc-wrap">
      {prompt && <p className="mc-prompt">{prompt}</p>}

      {items.map((q, qIdx) => {
        const imageUrl = q.image_key ? images[q.image_key] : null;

        return (
          <div key={`question-${qIdx}`} className="mc-question">
            {/* Display image if available */}
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt={`Question ${q.number}`} className="fb-image" />
              </div>
            )}
            <p className="mc-question-text">
              <AudioButton audioKey={q.audio_key} audioIndex={audioIndex} className="inline mr-2" />
              {q.number}. {q.text}
            </p>
          <ul className="mc-options">
            {q.options.map((optLine) => {
              const letter = optLine.match(/^[A-Z]/)?.[0];     // "A"
              const text = optLine.replace(/^[A-Z]\.\s*/, ""); // "Please."
              return (
                <li key={`${qIdx}-${letter}`} className="mc-option">
                  <label className="mc-label">
                    <input
                      type="radio"
                      name={`mc-${qIdx}`}
                      value={letter}
                      checked={choices[qIdx] === letter}
                      disabled={checked}
                      onChange={() => pick(qIdx, letter)}
                      className="mc-radio"
                    />
                    <span className="mc-option-text">{letter}. {text}</span>
                  </label>

                  {checked && choices[qIdx] === letter && (
                    <span className={`mc-result ${letter === q.answer ? "correct" : "wrong"}`}>
                      {letter === q.answer ? "✓" : "✗"}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>

          {checked && choices[qIdx] !== q.answer && (
            <p className="mc-correct-answer">
              <span className="mc-label">Correct answer:</span> {q.answer}
            </p>
          )}
        </div>
        );
      })}

      <div className="mc-buttons">
        {!checked ? (
          <button
            className="mc-btn check"
            disabled={!allAnswered}
            onClick={() => setChecked(true)}
          >
            Check
          </button>
        ) : (
          <>
            <p className="mc-feedback">
              You got {score} / {items.length} correct.
            </p>
            <button className="mc-btn reset" onClick={resetExercise}>
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

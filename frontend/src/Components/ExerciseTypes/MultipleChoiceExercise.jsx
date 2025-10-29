import React, { useMemo, useState } from "react";
import AudioButton from "../AudioButton";

const normalizeOption = (option) => {
  if (typeof option === "string") {
    const match = option.match(/^([A-Z])\.\s*(.*)$/s);
    return match
      ? { label: match[1], text: match[2] }
      : { label: "", text: option };
  }
  return {
    label: option.label || option.letter || "",
    text: option.text || "",
    image_key: option.image_key || null,
    alt_text: option.alt_text || option.text || option.label || "",
  };
};

export default function MultipleChoiceExercise({ exercise, images = {}, audioIndex = {} }) {
  const { prompt, items = [] } = exercise;
  const [choices, setChoices] = useState(Array(items.length).fill(null));
  const [checked, setChecked] = useState(false);

  const normalizedItems = useMemo(
    () =>
      items.map((item = {}) => ({
        ...item,
        options: Array.isArray(item.options)
          ? item.options.map(normalizeOption)
          : [],
      })),
    [items]
  );

  const pick = (qIdx, letter) => {
    setChoices((prev) => {
      const next = [...prev];
      next[qIdx] = letter;
      return next;
    });
  };

  const allAnswered = choices.every((choice) => choice);
  const score = checked
    ? choices.filter((choice, idx) => choice === normalizedItems[idx]?.answer).length
    : null;

  const resetExercise = () => {
    setChoices(Array(items.length).fill(null));
    setChecked(false);
  };

  return (
    <div className="fb-wrap mc-wrap">
      {prompt && <p className="mc-prompt">{prompt}</p>}

      {normalizedItems.map((q, qIdx) => {
        const imageUrl = q.image_key ? images[q.image_key] : null;
        const hasAudio = Boolean(q.audio_key);
        const numberLabel = q.number ?? qIdx + 1;
        const selected = choices[qIdx];
        const isCorrect = checked && selected === q.answer;

        return (
          <div key={`mc-question-${qIdx}`} className="fb-row mc-question">
            <div className="fb-row-number">
              <span>{numberLabel}</span>
            </div>

            <div className="fb-row-main">
              {imageUrl && (
                <div className="fb-image-container">
                  <img
                    src={imageUrl}
                    alt={`Question ${numberLabel}`}
                    className="fb-image"
                  />
                </div>
              )}

              <div className="fb-row-content">
                {hasAudio && (
                  <div className="practice-audio-container">
                    <AudioButton
                      audioKey={q.audio_key}
                      audioIndex={audioIndex}
                      className="practice-audio-button"
                    />
                  </div>
                )}

                <p className="mc-question-text">{q.text}</p>

                <div className="mc-options">
                  {q.options.map(({ label, text, image_key, alt_text }) => {
                    const isSelected = selected === label;
                    const isAnswer = q.answer === label;
                    const showResult = checked && (isSelected || isAnswer);

                    return (
                      <div key={`${qIdx}-${label}-${text}`} className="mc-option">
                        <button
                          type="button"
                          className={`mc-letter${isSelected ? " selected" : ""}`}
                          onClick={() => pick(qIdx, label)}
                          disabled={checked}
                          aria-pressed={isSelected}
                        >
                          {label}
                        </button>

                        <span className="mc-option-text">
                          {image_key ? (
                            <>
                              <img
                                src={images[image_key]}
                                alt={alt_text || text}
                                className="mc-option-image"
                              />
                              {text && <span>{text}</span>}
                            </>
                          ) : (
                            text
                          )}
                        </span>

                        {showResult && (
                          <span
                            className={`mc-result ${isAnswer ? "correct" : "incorrect"}`}
                            aria-label={isAnswer ? "Correct" : "Incorrect"}
                          >
                            {isAnswer ? "✓" : "✗"}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {checked && selected && !isCorrect && (
                  <p className="mc-feedback-text">
                    <strong>Correct answer:</strong> {q.answer}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      <div className="fb-button-container">
        {!checked ? (
          <button
            className="cq-check-btn language-toggle-btn fb-check-btn"
            disabled={!allAnswered}
            onClick={() => setChecked(true)}
          >
            Check Answers
          </button>
        ) : (
          <>
            <p className="mc-score">You got {score} / {items.length} correct.</p>
            <button className="ai-eval-button ai-reset" onClick={resetExercise}>
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}

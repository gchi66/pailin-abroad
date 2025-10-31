import React, { useEffect, useMemo, useState } from "react";
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

const normalizeArray = (values) => {
  const list = Array.isArray(values)
    ? values
    : values != null
    ? [values]
    : [];

  const cleaned = list
    .map((val) =>
      String(val || "")
        .trim()
        .replace(/\.$/, "")
        .toUpperCase()
    )
    .filter(Boolean);

  return [...new Set(cleaned)].sort();
};

const parseAnswerString = (answer) => {
  if (answer == null) return [];
  const parts = String(answer)
    .split(",")
    .map((segment) => segment.trim().replace(/\.$/, ""));
  return normalizeArray(parts);
};

const arraysMatch = (a, b) => {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
};

const createInitialChoices = (list = []) => list.map(() => []);

export default function MultipleChoiceExercise({ exercise, images = {}, audioIndex = {} }) {
  const { prompt, items = [] } = exercise;
  const [choices, setChoices] = useState(() => createInitialChoices(items));
  const [checked, setChecked] = useState(false);

  const normalizedItems = useMemo(
    () =>
      items.map((item = {}) => {
        const options = Array.isArray(item.options)
          ? item.options.map(normalizeOption)
          : [];
        const answerLetters = parseAnswerString(item.answer);
        const answerDisplay =
          item.answer && String(item.answer).trim().length > 0
            ? item.answer
            : answerLetters.join(", ");

        return {
          ...item,
          options,
          answerLetters,
          answerSet: new Set(answerLetters),
          answerDisplay,
        };
      }),
    [items]
  );
  useEffect(() => {
    setChoices(createInitialChoices(items));
    setChecked(false);
  }, [items]);

  const toggleChoice = (questionIdx, letter, allowMultiple) => {
    const normalizedLetter = normalizeArray([letter])[0];
    if (!normalizedLetter) return;

    setChoices((prev) =>
      prev.map((selection, idx) => {
        if (idx !== questionIdx) {
          return Array.isArray(selection)
            ? selection
            : normalizeArray(selection);
        }

        const current = normalizeArray(selection);

        let nextSelection;
        if (allowMultiple) {
          nextSelection = current.includes(normalizedLetter)
            ? current.filter((value) => value !== normalizedLetter)
            : [...current, normalizedLetter];
        } else {
          nextSelection =
            current.length === 1 && current[0] === normalizedLetter
              ? []
              : [normalizedLetter];
        }

        return normalizeArray(nextSelection);
      })
    );
  };

  const allAnswered = choices.every(
    (choice) => normalizeArray(choice).length > 0
  );
  const score = checked
    ? choices.filter((choice, idx) =>
        arraysMatch(
          normalizeArray(choice),
          normalizedItems[idx]?.answerLetters || []
        )
      ).length
    : null;

  const resetExercise = () => {
    setChoices(createInitialChoices(items));
    setChecked(false);
  };

  return (
    <div className="fb-wrap mc-wrap">
      {prompt && <p className="mc-prompt">{prompt}</p>}

      {normalizedItems.map((q, qIdx) => {
        const imageUrl = q.image_key ? images[q.image_key] : null;
        const hasAudio = Boolean(q.audio_key);
        const numberLabel = q.number ?? qIdx + 1;
        const selected = normalizeArray(choices[qIdx]);
        const selectedSet = new Set(selected);
        const allowMultiple = q.answerLetters.length > 1;
        const isCorrect = checked && arraysMatch(selected, q.answerLetters);

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
                    const normalizedLabel = normalizeArray([label])[0];
                    const isSelected = normalizedLabel
                      ? selectedSet.has(normalizedLabel)
                      : false;
                    const isAnswer = normalizedLabel
                      ? q.answerSet.has(normalizedLabel)
                      : false;
                    const showResult = checked && (isSelected || isAnswer);

                    let resultSymbol = "";
                    let resultClass = "";

                    if (showResult) {
                      if (isAnswer) {
                        resultSymbol = "✓";
                        resultClass = "correct";
                      } else if (isSelected) {
                        resultSymbol = "✗";
                        resultClass = "incorrect";
                      }
                    }

                    return (
                      <div key={`${qIdx}-${label}-${text}`} className="mc-option">
                        <button
                          type="button"
                          className={`mc-letter${isSelected ? " selected" : ""}`}
                          onClick={() => toggleChoice(qIdx, label, allowMultiple)}
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

                        {resultSymbol && (
                          <span
                            className={`mc-result ${resultClass}`}
                            aria-label={
                              resultClass === "correct" ? "Correct" : "Incorrect"
                            }
                          >
                            {resultSymbol}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>

                {checked && selected.length > 0 && !isCorrect && (
                  <p className="mc-feedback-text">
                    <strong>Correct answer:</strong>{" "}
                    {q.answerDisplay || q.answerLetters.join(", ")}
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
            className="apply-submit"
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

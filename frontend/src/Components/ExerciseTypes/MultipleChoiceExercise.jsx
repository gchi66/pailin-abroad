import React, { useEffect, useMemo, useState } from "react";
import AudioButton from "../AudioButton";
import InlineText from "../InlineText";
import { copy, pick } from "../../ui-lang/i18n";
import CheckAnswersButton from "./CheckAnswersButton";

const stripOptionPrefix = (label, value) => {
  if (!label || typeof value !== "string") return value;
  const pattern = new RegExp(`^${label}\\.\\s*`, "i");
  return value.replace(pattern, "");
};

const stripOptionPrefixInlines = (label, inlines) => {
  if (!label || !Array.isArray(inlines) || inlines.length === 0) {
    return inlines;
  }
  const [first, ...rest] = inlines;
  const nextText = stripOptionPrefix(label, first?.text || "");
  if (nextText === (first?.text || "")) return inlines;
  if (!nextText) return rest;
  return [{ ...first, text: nextText }, ...rest];
};

const normalizeOption = (option) => {
  if (typeof option === "string") {
    const match = option.match(/^([A-Z])\.\s*(.*)$/s);
    return match
      ? { label: match[1], text: match[2] }
      : { label: "", text: option };
  }
  const label = option.label || option.letter || "";
  const text = stripOptionPrefix(label, option.text || "");
  const text_jsonb = stripOptionPrefixInlines(label, option.text_jsonb || null);
  const alt_text = stripOptionPrefix(
    label,
    option.alt_text || option.text || option.label || ""
  );
  return {
    label,
    text,
    text_jsonb,
    image_key: option.image_key || null,
    alt_text,
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

export default function MultipleChoiceExercise({
  exercise,
  images = {},
  audioIndex = {},
  contentLang = "en",
}) {
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
    setChecked(false);
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
  const checkLabel = pick(copy.lessonContent.checkAnswers, contentLang);
  const hasIncompleteAnswers =
    normalizedItems.length > 0 && !allAnswered;

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
        const questionText = q.text;
        const questionTextTh = contentLang === "th" ? q.text_th : "";
        const questionInlines = q.text_jsonb || null;
        const questionInlinesTh = q.text_jsonb_th || null;
        const selected = normalizeArray(choices[qIdx]);
        const selectedSet = new Set(selected);
        const allowMultiple = q.answerLetters.length > 1;

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

                <InlineText
                  as="p"
                  className="mc-question-text"
                  inlines={questionInlines}
                  text={questionText}
                />
                {questionTextTh && (
                  <InlineText
                    as="p"
                    className="mc-question-text th"
                    inlines={questionInlinesTh}
                    text={questionTextTh}
                  />
                )}

                <div className="mc-options">
                  {q.options.map(({ label, text, text_jsonb, image_key, alt_text }) => {
                    const normalizedLabel = normalizeArray([label])[0];
                    const isSelected = normalizedLabel
                      ? selectedSet.has(normalizedLabel)
                      : false;
                    const isAnswer = normalizedLabel
                      ? q.answerSet.has(normalizedLabel)
                      : false;
                    const shouldShowResult = checked && isSelected;

                    return (
                      <div key={`${qIdx}-${label}-${text}`} className="mc-option">
                        <button
                          type="button"
                          className={`mc-letter${isSelected ? " selected" : ""}`}
                          onClick={() => toggleChoice(qIdx, label, allowMultiple)}
                          aria-pressed={isSelected}
                        >
                          {label}
                        </button>

                        <span className="mc-option-text">
                          {image_key && (
                            <img
                              src={images[image_key]}
                              alt={alt_text || text}
                              className="mc-option-image"
                            />
                          )}
                          {text && (
                            <InlineText
                              as="span"
                              className="mc-option-text-lines"
                              inlines={text_jsonb}
                              text={text}
                            />
                          )}

                          {shouldShowResult && (
                            <span
                              className={`mc-option-result ${
                                isAnswer ? "correct" : "incorrect"
                              }`}
                              aria-label={isAnswer ? "Correct" : "Incorrect"}
                            >
                              {isAnswer ? "✓" : "✗"}
                            </span>
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>

                {/* {checked && selected.length > 0 && !isCorrect && (
                  <p className="mc-feedback-text">
                    <strong>Correct answer:</strong>{" "}
                    {q.answerDisplay || q.answerLetters.join(", ")}
                  </p>
                )} */}
              </div>
            </div>
          </div>
        );
      })}

      <div className="fb-button-container">
        {!checked ? (
          <CheckAnswersButton
            onClick={() => setChecked(true)}
            disabled={!allAnswered}
            label={checkLabel}
            hasIncompleteAnswers={hasIncompleteAnswers}
            contentLang={contentLang}
          />
        ) : (
          <>
            <button className="apply-submit mc-try-again" type="button" onClick={resetExercise}>
              TRY AGAIN
            </button>
            <p className="mc-score">You got {score} / {items.length} correct.</p>
          </>
        )}
      </div>
    </div>
  );
}

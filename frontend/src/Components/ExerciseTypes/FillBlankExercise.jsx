import React, { useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import "./evaluateAnswer.css";

/**
 * Fill-in-the-blank component that supports
 *   • paragraph exercises  – exercise.paragraph !== ""
 *   • row exercises        – each item.text contains ____ (underscores)
 *   • images              – items with image_key property will display images
 */
export default function FillBlankExercise({
  exercise,
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
}) {
  const { title, prompt, paragraph, items = [] } = exercise || {};
  const { user } = useAuth();
  const userId = userIdProp || user?.id || null;
  const evaluationSourceType = ["bank", "practice"].includes(
    (sourceType || "").toLowerCase()
  )
    ? (sourceType || "").toLowerCase()
    : "practice";
  const resolvedExerciseId = exerciseId ?? exercise?.id ?? null;

  /* ---------- state ---------- */
  const [inputs, setInputs] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [error, setError] = useState("");

  /* ---------- helpers ---------- */
  const handleChange = (idx, val) => {
    const next = [...inputs];
    next[idx] = val;
    setInputs(next);
    if (error) {
      setError("");
    }
  };

  const isCorrect = (idx) => {
    if (!checked) return null;
    const correctAnswer = items[idx]?.answer?.toLowerCase()?.trim() || "";
    const userAnswer = inputs[idx]?.toLowerCase()?.trim() || "";
    return userAnswer && correctAnswer.includes(userAnswer);
  };

  const handleCheck = async () => {
    if (isChecking) return;
    if (!userId) {
      setError("Please log in to check your answer.");
      return;
    }
    const hasInput = inputs.some((input) => (input || "").trim());
    if (!hasInput) {
      setError("Please fill in at least one blank before checking.");
      return;
    }

    setIsChecking(true);
    setError("");

    const learnerAnswers = items.map((item, idx) => ({
      number: item?.number ?? idx + 1,
      prompt: item?.text || item?.question || "",
      answer: inputs[idx] || "",
    }));

    const expectedAnswers = items.map((item, idx) => ({
      number: item?.number ?? idx + 1,
      prompt: item?.text || item?.question || "",
      answer: item?.answer || "",
    }));

    try {
      const result = await evaluateAnswer({
        userId,
        exerciseType: "fill_blank",
        userAnswer: {
          title,
          prompt,
          paragraph,
          answers: learnerAnswers,
        },
        correctAnswer: {
          title,
          prompt,
          paragraph,
          answers: expectedAnswers,
        },
        sourceType: evaluationSourceType,
        exerciseId: resolvedExerciseId,
      });
      setAiResult(result);
      setChecked(true);
    } catch (err) {
      setError(err.message || "Unable to check your answer right now.");
    } finally {
      setIsChecking(false);
    }
  };

  const handleReset = () => {
    setInputs(Array(items.length).fill(""));
    setChecked(false);
    setAiResult(null);
    setError("");
  };

  // Create answer key from items array for paragraph style
  const answerKey = items.reduce((acc, item) => {
    if (!item) return acc;
    const key = item.number;
    const answerText =
      typeof item.answer === "string" ? item.answer.toLowerCase().trim() : "";
    if (key != null && answerText) {
      acc[key] = answerText;
    }
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
        {prompt && <p className="fb-prompt">{prompt}</p>}

        <p className="fb-paragraph">
          {renderParagraphWithInputs(paragraph)}
        </p>

        <Buttons
          checked={checked}
          inputs={inputs}
          onCheck={handleCheck}
          onReset={handleReset}
          isChecking={isChecking}
        />
        <FeedbackPanel aiResult={aiResult} error={error} />
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
        // Check if this item has an image
        const imageUrl = item.image_key ? images[item.image_key] : null;

        return (
          <div key={`${item.number}-${idx}`} className="fb-row">
            {/* Display image if available */}
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt={`Exercise ${item.number}`} className="fb-image" />
              </div>
            )}

            {/* If there's an image, display only the text. Otherwise, split on underscores for blanks */}
            {imageUrl ? (
              <div className="fb-text-with-input">
                <AudioButton audioKey={item.audio_key} audioIndex={audioIndex} className="inline mr-2" />
                <span>{item.text}</span>
                <input
                  type="text"
                  className="fb-input"
                  value={inputs[idx]}
                  onChange={(e) => handleChange(idx, e.target.value)}
                  disabled={checked}
                  placeholder="___"
                />
              </div>
            ) : (
              <>
                {/* split at the first run of underscores (___ or ____) */}
                {(() => {
                  const parts = item.text.split(/_+/);
                  return (
                    <>
                      <AudioButton audioKey={item.audio_key} audioIndex={audioIndex} className="inline mr-2" />
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
                    </>
                  );
                })()}
              </>
            )}

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
        onCheck={handleCheck}
        onReset={handleReset}
        isChecking={isChecking}
      />
      <FeedbackPanel aiResult={aiResult} error={error} />
    </div>
  );
}

/* ------------------------------------------------
 *  Re-usable buttons block
 * ------------------------------------------------ */
function Buttons({ checked, inputs, onCheck, onReset, isChecking }) {
  const disableCheck =
    inputs.every((input) => !((input || "").trim())) || isChecking;

  return (
    <div className="fb-button-container">
      {!checked ? (
        <button
          className="ai-eval-button"
          onClick={onCheck}
          disabled={disableCheck}
        >
          {isChecking ? "Checking..." : "Check Answer"}
        </button>
      ) : (
        <button className="ai-eval-button ai-reset" onClick={onReset}>
          Try Again
        </button>
      )}
    </div>
  );
}

function FeedbackPanel({ aiResult, error }) {
  if (error) {
    return (
      <div className="ai-feedback-container">
        <p className="ai-feedback-message error">{error}</p>
      </div>
    );
  }

  if (!aiResult) return null;

  const statusClass = aiResult.correct ? "correct" : "incorrect";
  const headline =
    aiResult.feedback_en ||
    (aiResult.correct ? "Great job!" : "Keep practicing!");

  return (
    <div className="ai-feedback-container">
      <p className={`ai-feedback-message ${statusClass}`}>{headline}</p>
      {aiResult.feedback_th && (
        <p className="ai-feedback-th">{aiResult.feedback_th}</p>
      )}
    </div>
  );
}

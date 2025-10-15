import React, { useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import "./evaluateAnswer.css";

export default function SentenceTransformExercise({
  exercise = {},
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
}) {
  const { title = "", prompt = "", items = [] } = exercise || {};
  const { user } = useAuth();
  const userId = userIdProp || user?.id || null;
  const evaluationSourceType = ["bank", "practice"].includes(
    (sourceType || "").toLowerCase()
  )
    ? (sourceType || "").toLowerCase()
    : "practice";
  const resolvedExerciseId = exerciseId ?? exercise?.id ?? null;
  const [answers, setAnswers] = useState(Array(items.length).fill(""));
  const [checked, setChecked] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [error, setError] = useState("");

  const handleChange = (idx, val) => {
    const next = [...answers];
    next[idx] = val;
    setAnswers(next);
    if (error) {
      setError("");
    }
  };

  const passed = (idx) => {
    if (!checked) return null;

    const item = items[idx];
    if (!item) return false;
    const isCorrect = item.correct === "yes";

    // For sentences that are already correct (correct === "yes"),
    // the user might just leave it blank or write the original sentence
    if (isCorrect) {
      // If they left it blank, that's correct too
      if (!answers[idx].trim()) return true;

      // If they wrote something, it should match the original text
      const originalText = item.text.toLowerCase().replace(/\s+/g, " ").trim();
      const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();
      return got === originalText;
    }

    // For sentences that need transformation, check against possible answers
    if (!item.answer) return false;

    // Split answer by comma to handle multiple acceptable answers
    const acceptableAnswers = item.answer.split(',').map(ans =>
      ans.toLowerCase().replace(/\s+/g, " ").trim()
    );
    const got = answers[idx].toLowerCase().replace(/\s+/g, " ").trim();

    return acceptableAnswers.includes(got);
  };

  const handleCheck = async () => {
    if (isChecking) return;
    if (!userId) {
      setError("Please log in to check your answer.");
      return;
    }

    const allowAllBlank = items.every((item) => (item?.correct || "").toLowerCase() === "yes");
    const hasInput = answers.some((input) => (input || "").trim());
    if (!hasInput && !allowAllBlank) {
      setError("Please provide your corrections before checking.");
      return;
    }

    setIsChecking(true);
    setError("");

    const learnerSentences = items.map((item, idx) => ({
      number: item?.number ?? idx + 1,
      original_sentence: item?.text || "",
      user_answer: answers[idx] || "",
      is_already_correct: (item?.correct || "").toLowerCase() === "yes",
    }));

    const expectedSentences = items.map((item, idx) => ({
      number: item?.number ?? idx + 1,
      original_sentence: item?.text || "",
      expected_answer: item?.answer || "",
      is_already_correct: (item?.correct || "").toLowerCase() === "yes",
    }));

    try {
      const result = await evaluateAnswer({
        userId,
        exerciseType: "sentence_transform",
        userAnswer: {
          title,
          prompt,
          sentences: learnerSentences,
        },
        correctAnswer: {
          title,
          prompt,
          sentences: expectedSentences,
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
    setAnswers(Array(items.length).fill(""));
    setChecked(false);
    setAiResult(null);
    setError("");
  };

  return (
    <div className="st-wrap">
      {prompt && <p className="st-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        const isCorrect = item.correct === "yes";
        const imageUrl = item.image_key ? images[item.image_key] : null;

        return (
          <div key={`question-${idx}`} className="st-question">
            {/* Display image if available */}
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt={`Question ${item.number}`} className="fb-image" />
              </div>
            )}
            <p className="st-stem">
              <AudioButton audioKey={item.audio_key} audioIndex={audioIndex} className="inline mr-2" />
              {(item.number ?? idx + 1)}. {item.text}
            </p>
            <div className="st-input-container">
              <input
                type="text"
                value={answers[idx]}
                onChange={(e) => handleChange(idx, e.target.value)}
                disabled={checked}
                placeholder={isCorrect ? "This sentence is correct (leave blank or rewrite)" : "Correct this sentence"}
                className="st-input"
              />

              {checked && (
                <span className={`st-mark ${passed(idx) ? "correct" : "wrong"}`}>
                  {passed(idx) ? "✓" : "✗"}
                </span>
              )}
            </div>

            {checked && !passed(idx) && (
              <p className="st-correct-answer">
                <span className="st-label">Correct answer:</span>{" "}
                {isCorrect ? "(The sentence is already correct)" : item.answer}
              </p>
            )}
          </div>
        );
      })}

      <div className="st-buttons">
        {!checked ? (
          <button
            onClick={handleCheck}
            className="ai-eval-button"
            disabled={isChecking}
          >
            {isChecking ? "Checking..." : "Check Answer"}
          </button>
        ) : (
          <button
            onClick={handleReset}
            className="ai-eval-button ai-reset"
          >
            Try Again
          </button>
        )}
      </div>
      <FeedbackPanel aiResult={aiResult} error={error} />
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

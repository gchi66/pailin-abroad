import React, { useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import "./evaluateAnswer.css";

export default function OpenEndedExercise({
  exercise,
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
}) {
  const { title, prompt, items = [] } = exercise;
  const { user } = useAuth();
  const userId = userIdProp || user?.id || null;
  const evaluationSourceType = ["bank", "practice"].includes(
    (sourceType || "").toLowerCase()
  )
    ? (sourceType || "").toLowerCase()
    : "practice";
  const resolvedExerciseId = exerciseId ?? exercise?.id ?? null;

  // Initialize state for each input for each question
  // Structure: [question1: [input1], question2: [input1, input2], etc]
  const [responses, setResponses] = useState(
    items.map(item => Array((item.inputs || 1)).fill(""))
  );
  const [checked, setChecked] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [error, setError] = useState("");

  const handleChange = (qIdx, inputIdx, val) => {
    const nextResponses = [...responses];
    nextResponses[qIdx][inputIdx] = val;
    setResponses(nextResponses);
    if (error) {
      setError("");
    }
  };

  const passed = (qIdx) => {
    if (!checked) return null;

    const item = items[qIdx];
    const keywords = (item.keywords || "").split(",").map(k => k.trim().toLowerCase()).filter(Boolean);

    // Check if all inputs for this question contain at least one of the keywords
    return responses[qIdx].every(response => {
      const responseLower = response.toLowerCase();
      return keywords.some(keyword => responseLower.includes(keyword));
    });
  };

  const handleCheck = async () => {
    if (isChecking) return;
    if (!userId) {
      setError("Please log in to check your answer.");
      return;
    }
    if (!allAnswered) {
      setError("Please answer every prompt before checking.");
      return;
    }

    setIsChecking(true);
    setError("");

    const learnerResponses = items.map((item, qIdx) => ({
      number: item?.number ?? qIdx + 1,
      question: item?.question || item?.text || "",
      answers: (responses[qIdx] || []).map((value) => value || ""),
    }));

    const expectedResponses = items.map((item, qIdx) => ({
      number: item?.number ?? qIdx + 1,
      question: item?.question || item?.text || "",
      sample_answer: item?.sample_answer || "",
      keywords: item?.keywords || "",
    }));

    try {
      const result = await evaluateAnswer({
        userId,
        exerciseType: "open",
        userAnswer: {
          title,
          prompt,
          responses: learnerResponses,
        },
        correctAnswer: {
          title,
          prompt,
          expected: expectedResponses,
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
    setResponses(items.map(item => Array((item.inputs || 1)).fill("")));
    setChecked(false);
    setAiResult(null);
    setError("");
  };

  // Determine if all questions have valid responses
  const allAnswered = responses.every((questionInputs, qIdx) => {
    const item = items[qIdx] || {};
    const numInputs = item.inputs || 1;
    return questionInputs.filter(Boolean).length === numInputs;
  });

  return (
    <div className="oe-wrap">
      {prompt && <p className="oe-prompt">{prompt}</p>}

      {items.map((item, qIdx) => {
        // Extract keywords for this specific item
        const itemKeywords = (item.keywords || "").split(",").map(k => k.trim()).filter(Boolean);
        const imageUrl = item.image_key ? images[item.image_key] : null;

        return (
          <div key={`question-${qIdx}`} className="oe-question">
            {/* Display image if available */}
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt={`Question ${item.number}`} className="fb-image" />
              </div>
            )}
            <p className="oe-question-text">
              <AudioButton audioKey={item.audio_key} audioIndex={audioIndex} className="inline mr-2" />
              {item.number}. {item.question || item.text}
            </p>

            {/* Render the appropriate number of input fields */}
            {Array.from({ length: item.inputs || 1 }).map((_, inputIdx) => (
              <div key={`input-${qIdx}-${inputIdx}`} className="oe-input-container">
                <textarea
                  rows={3}
                  value={responses[qIdx][inputIdx] || ""}
                  onChange={(e) => handleChange(qIdx, inputIdx, e.target.value)}
                  disabled={checked}
                  className="oe-textarea"
                  placeholder="Type your answer here"
                />
              </div>
            ))}

            {checked && (
              <div className="oe-feedback">
                <span className={`oe-mark ${passed(qIdx) ? "correct" : "wrong"}`}>
                  {passed(qIdx) ? "✓" : "✗"}
                </span>
                {!passed(qIdx) && itemKeywords.length > 0 && (
                  <p className="oe-hint">
                    Remember to use these keywords: {itemKeywords.join(", ")}
                  </p>
                )}
                {item.sample_answer && (
                  <div className="oe-sample-answer">
                    <p><strong>Sample answer:</strong> {item.sample_answer}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      <div className="oe-buttons">
        {!checked ? (
          <button
            className="ai-eval-button"
            onClick={handleCheck}
            disabled={!allAnswered || isChecking}
          >
            {isChecking ? "Checking..." : "Check Answer"}
          </button>
        ) : (
          <button className="ai-eval-button ai-reset" onClick={handleReset}>
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

import React, { useEffect, useMemo, useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import { normalizeAiCorrect } from "./normalizeAiCorrect";
import { InlineStatus, QuestionFeedback } from "./aiFeedback";
import "./evaluateAnswer.css";

const DEFAULT_QUESTION_STATE = {
  answer: "",
  feedback: null,
  correct: null,
  score: null,
  loading: false,
};

const isExampleItem = (item) => {
  if (!item) return false;
  if (typeof item.is_example === "boolean") {
    return item.is_example;
  }
  const number = item.number;
  if (typeof number === "string") {
    return number.trim().toLowerCase() === "example";
  }
  return false;
};

const formatCorrectValue = (value) => {
  if (typeof value !== "string") {
    if (value === true) return "Yes";
    if (value === false) return "No";
    return value || "";
  }
  const normalized = value.trim().toLowerCase();
  if (normalized === "yes") return "Yes";
  if (normalized === "no") return "No";
  if (normalized === "true") return "Yes";
  if (normalized === "false") return "No";
  return value.trim();
};

export default function SentenceTransformExercise({
  exercise = {},
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
  showTitle = true,
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

  const initialQuestions = useMemo(
    () =>
      items.map((item) => {
        if (isExampleItem(item)) {
          return {
            ...DEFAULT_QUESTION_STATE,
            answer: item?.answer || "",
            correct: true,
          };
        }
        return {
          ...DEFAULT_QUESTION_STATE,
        };
      }),
    [items]
  );

  const [questions, setQuestions] = useState(initialQuestions);
  const [isChecking, setIsChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setQuestions(initialQuestions);
    setIsChecking(false);
    setHasChecked(false);
    setError("");
  }, [initialQuestions]);

  const pendingIndexes = useMemo(
    () =>
      questions
        .map((question, idx) => (question.correct === true ? null : idx))
        .filter((idx) => idx !== null),
    [questions]
  );

  const pendingHaveAnswers = pendingIndexes.every((idx) => {
    const question = questions[idx];
    const item = items[idx];
    if (!question) return false;
    const answerText = (question.answer || "").trim();
    if (answerText) return true;
    // Allow already correct sentences to be left blank
    return (item?.correct || "").toLowerCase() === "yes";
  });

  const canCheck =
    pendingIndexes.length > 0 && pendingHaveAnswers && !isChecking;
  const hasIncorrect = questions.some((question) => question.correct === false);

  const handleChange = (idx, value) => {
    setQuestions((prev) =>
      prev.map((question, questionIdx) => {
        if (questionIdx !== idx || question.correct === true || question.loading)
          return question;
        return { ...question, answer: value };
      })
    );
    if (error) {
      setError("");
    }
  };

  const handleCheckAnswers = async () => {
    if (!userId) {
      setError("Please log in to check your answers.");
      return;
    }
    if (!pendingIndexes.length) {
      setHasChecked(true);
      return;
    }
    if (!pendingHaveAnswers) {
      setError("Please respond to each sentence before checking.");
      return;
    }

    setError("");
    setIsChecking(true);

    setQuestions((prev) =>
      prev.map((question, idx) =>
        pendingIndexes.includes(idx)
          ? { ...question, loading: true }
          : question
      )
    );

    await Promise.all(
      pendingIndexes.map(async (idx) => {
        const item = items[idx] || {};
        const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
        const isAlreadyCorrect = (item.correct || "").toLowerCase() === "yes";

        const userAnswer = questionState.answer.trim()
          ? questionState.answer
          : isAlreadyCorrect
          ? item.text || ""
          : "";

        const expectedAnswer = item.answer || item.text || "";

        try {
          const result = await evaluateAnswer({
            userId,
            exerciseType: "sentence_transform",
            userAnswer,
            correctAnswer: expectedAnswer,
            sourceType: evaluationSourceType,
            exerciseId: resolvedExerciseId,
            questionNumber: item.number ?? idx + 1,
            questionPrompt:
              item.text ||
              prompt ||
              title ||
              "Transform the sentence to the correct form.",
          });

          const normalizedCorrect = normalizeAiCorrect(result.correct);
          const scoreValue =
            typeof result.score === "number" ? result.score : null;

          setQuestions((prev) =>
            prev.map((question, questionIdx) => {
              if (questionIdx !== idx) return question;
              return {
                ...question,
                loading: false,
                correct: normalizedCorrect,
                score: scoreValue,
                feedback: {
                  en: result.feedback_en || "",
                  th: result.feedback_th || "",
                },
              };
            })
          );
        } catch (err) {
          setQuestions((prev) =>
            prev.map((question, questionIdx) => {
              if (questionIdx !== idx) return question;
              return {
                ...question,
                loading: false,
                correct: false,
                score: null,
                feedback: {
                  en:
                    err?.message ||
                    "Unable to check this answer right now. Please try again.",
                  th: "",
                },
              };
            })
          );
        }
      })
    );

    setIsChecking(false);
    setHasChecked(true);
  };

  const handleTryAgain = () => {
    setQuestions((prev) =>
      prev.map((question) => {
        if (question.correct === false) {
          return { ...DEFAULT_QUESTION_STATE };
        }
        return { ...question, loading: false };
      })
    );
    setIsChecking(false);
    setHasChecked(false);
    setError("");
  };

  return (
    <div className="st-wrap">
      {title && showTitle && <h3 className="st-title">{title}</h3>}
      {prompt && <p className="st-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
        const exampleItem = isExampleItem(item);

        if (exampleItem) {
          const correctValue = formatCorrectValue(item?.correct);
          const answerValue = item?.answer || "";
          const imageUrl = item?.image_key ? images[item.image_key] : null;

          return (
            <div key={`sentence-${idx}`} className="st-question st-example">
              <p className="st-example-label">Example</p>
              {imageUrl && (
                <div className="fb-image-container">
                  <img
                    src={imageUrl}
                    alt="Example sentence"
                    className="fb-image"
                  />
                </div>
              )}
              <p className="st-stem">
                <AudioButton
                  audioKey={item.audio_key}
                  audioIndex={audioIndex}
                  className="inline mr-2"
                />
                {item?.text}
              </p>
              {correctValue && (
                <p className="st-example-meta">
                  <strong>Correct?</strong> {correctValue}
                </p>
              )}
              {answerValue && (
                <p className="st-example-meta st-example-answer">
                  <strong>Answer:</strong> {answerValue}
                </p>
              )}
            </div>
          );
        }

        const disabled =
          questionState.correct === true || questionState.loading === true;
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const numberLabel = item.number ?? idx + 1;

        return (
          <div key={`sentence-${idx}`} className="st-question">
            {imageUrl && (
              <div className="fb-image-container">
                <img
                  src={imageUrl}
                  alt={`Question ${numberLabel}`}
                  className="fb-image"
                />
              </div>
            )}
            <p className="st-stem">
              <AudioButton
                audioKey={item.audio_key}
                audioIndex={audioIndex}
                className="inline mr-2"
              />
              {numberLabel}. {item.text}
            </p>
            <div className="st-input-wrap">
              <input
                type="text"
                value={questionState.answer}
                onChange={(event) => handleChange(idx, event.target.value)}
                disabled={disabled}
                placeholder="Rewrite this sentence"
                className="st-input"
              />
              <InlineStatus state={questionState} />
            </div>
            <QuestionFeedback state={questionState} />
          </div>
        );
      })}

      {error && <p className="ai-error-message">{error}</p>}

      <div className="st-buttons">
        <button
          onClick={handleCheckAnswers}
          className="ai-eval-button"
          disabled={!canCheck}
        >
          {isChecking ? "Checking..." : "Check Answers"}
        </button>
        {hasChecked && hasIncorrect && (
          <button
            onClick={handleTryAgain}
            className="ai-eval-button ai-reset"
            disabled={isChecking}
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}

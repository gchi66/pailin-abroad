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

export default function FillBlankExercise({
  exercise,
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
  showTitle = true,
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

  const initialQuestions = useMemo(
    () =>
      items.map(() => ({
        ...DEFAULT_QUESTION_STATE,
      })),
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

  const allPendingAnswered = pendingIndexes.every((idx) =>
    (questions[idx]?.answer || "").trim()
  );

  const canCheck =
    pendingIndexes.length > 0 && allPendingAnswered && !isChecking;
  const hasIncorrect = questions.some((question) => question.correct === false);

  const handleAnswerChange = (idx, value) => {
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
    if (!allPendingAnswered) {
      setError("Please complete every blank before checking.");
      return;
    }

    setError("");
    setIsChecking(true);

    // Set loading state for pending questions
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
        const userAnswer = questions[idx]?.answer || "";

        try {
          const result = await evaluateAnswer({
            userId,
            exerciseType: "fill_blank",
            userAnswer,
            correctAnswer: item.answer || "",
            sourceType: evaluationSourceType,
            exerciseId: resolvedExerciseId,
            questionNumber: item.number ?? idx + 1,
            questionPrompt:
              item.text ||
              paragraph ||
              prompt ||
              title ||
              "Fill in the missing text.",
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

  const renderParagraphWithInputs = () => {
    if (!paragraph || typeof paragraph !== "string") {
      return null;
    }

    const parts = paragraph.split(/(\*\*\d+\*\*|_{2,3}\d+_{2,3})/g);

    return parts.map((part, index) => {
      const numberMatch =
        part.match(/\*\*(\d+)\*\*/) || part.match(/_{2,3}(\d+)_{2,3}/);

      if (!numberMatch) {
        return <span key={`text-${index}`}>{part}</span>;
      }

      const numberValue = numberMatch[1];
      const itemIndex = items.findIndex(
        (item) => String(item.number) === String(numberValue)
      );
      const questionIndex = itemIndex !== -1 ? itemIndex : null;

      if (questionIndex === null) {
        return (
          <span key={`inline-missing-${index}`} className="fb-inline">
            <div className="fb-inline-input">
              <input
                type="text"
                className="fb-input"
                value=""
                disabled
                placeholder="___"
              />
            </div>
          </span>
        );
      }

      const questionState = questions[questionIndex] || DEFAULT_QUESTION_STATE;
      const disabled =
        questionState.correct === true || questionState.loading === true;

      return (
        <span key={`inline-${index}`} className="fb-inline">
          <div className="fb-inline-input">
            <input
              type="text"
              className="fb-input"
              value={questionState.answer}
              onChange={(event) =>
                handleAnswerChange(questionIndex, event.target.value)
              }
              disabled={disabled}
              placeholder="___"
            />
            <InlineStatus state={questionState} />
          </div>
          <QuestionFeedback state={questionState} layout="inline" />
        </span>
      );
    });
  };

  const renderRowItems = () =>
    items.map((item, idx) => {
      const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
      const disabled =
        questionState.correct === true || questionState.loading === true;
      const imageUrl = item.image_key ? images[item.image_key] : null;
      const textSegments = (item.text || "").split(/_+/);
      const before = textSegments.shift() || "";
      const after = textSegments.join("___");
      return (
        <div key={`${item.number ?? idx}-${idx}`} className="fb-row">
          {imageUrl && (
            <div className="fb-image-container">
              <img
                src={imageUrl}
                alt={`Exercise ${item.number ?? idx + 1}`}
                className="fb-image"
              />
            </div>
          )}

          <div className="fb-row-content">
            <div className="fb-row-text">
              <AudioButton
                audioKey={item.audio_key}
                audioIndex={audioIndex}
                className="inline mr-2"
              />
              {imageUrl ? (
                <>
                  <span>{item.text}</span>
                  <div className="fb-input-wrap">
                    <input
                      type="text"
                      className="fb-input"
                      value={questionState.answer}
                      onChange={(event) =>
                        handleAnswerChange(idx, event.target.value)
                      }
                      disabled={disabled}
                      placeholder="___"
                    />
                    <InlineStatus state={questionState} />
                  </div>
                </>
              ) : (
                <span>
                  {before}
                  <div className="fb-input-wrap">
                    <input
                      type="text"
                      className="fb-input"
                      value={questionState.answer}
                      onChange={(event) =>
                        handleAnswerChange(idx, event.target.value)
                      }
                      disabled={disabled}
                      placeholder="___"
                    />
                    <InlineStatus state={questionState} />
                  </div>
                  {after}
                </span>
              )}
            </div>

            <QuestionFeedback state={questionState} />
          </div>
        </div>
      );
    });

  return (
    <div className="fb-wrap">
      {title && showTitle && <h3 className="fb-title">{title}</h3>}
      {prompt && <p className="fb-prompt">{prompt}</p>}

      {paragraph ? (
        <p className="fb-paragraph">{renderParagraphWithInputs()}</p>
      ) : (
        renderRowItems()
      )}

      {error && <p className="ai-error-message">{error}</p>}

      <div className="fb-button-container">
        <button
          className="ai-eval-button"
          onClick={handleCheckAnswers}
          disabled={!canCheck}
        >
          {isChecking ? "Checking..." : "Check Answers"}
        </button>

        {hasChecked && hasIncorrect && (
          <button
            className="ai-eval-button ai-reset"
            onClick={handleTryAgain}
            disabled={isChecking}
          >
            Try Again
          </button>
        )}
      </div>
    </div>
  );
}

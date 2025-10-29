import React, { useEffect, useMemo, useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import { normalizeAiCorrect } from "./normalizeAiCorrect";
import { InlineStatus, QuestionFeedback } from "./aiFeedback";
import { copy, pick } from "../../ui-lang/i18n";
import "./evaluateAnswer.css";

const DEFAULT_QUESTION_STATE = {
  answer: "",
  answerParts: [],
  feedback: null,
  correct: null,
  score: null,
  loading: false,
};

const normalizeText = (value) =>
  (typeof value === "string" ? value : "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();

const getInputCount = (item) => {
  const raw = item?.inputs;
  if (typeof raw === "number" && Number.isFinite(raw) && raw > 0) {
    return raw;
  }
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
};

const isExampleItem = (item) => {
  if (!item) return false;
  if (typeof item.is_example === "boolean") {
    return item.is_example;
  }
  if (typeof item.number === "string") {
    return item.number.trim().toLowerCase() === "example";
  }
  return false;
};

export default function OpenEndedExercise({
  exercise,
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
  showTitle = true,
  contentLang = "en",
}) {
  const { title, prompt, items = [] } = exercise || {};
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
        const base = {
          ...DEFAULT_QUESTION_STATE,
          answerParts: Array(getInputCount(item)).fill(""),
        };
        if (isExampleItem(item)) {
          const exampleAnswer =
            item.sample_answer ||
            item.answer ||
            item.expected_answer ||
            item.keywords ||
            "";
          return {
            ...base,
            correct: true,
            loading: false,
            answer: exampleAnswer,
          };
        }
        return base;
      }),
    [items]
  );

  const [questions, setQuestions] = useState(initialQuestions);
  const [isChecking, setIsChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [error, setError] = useState("");
  const checkLabel = pick(copy.lessonContent.checkAnswers, contentLang);
  const checkingLabel = pick(copy.lessonContent.checking, contentLang);

  useEffect(() => {
    setQuestions(initialQuestions);
    setIsChecking(false);
    setHasChecked(false);
    setError("");
  }, [initialQuestions]);

  const questionHasResponse = (question, idx) => {
    if (Array.isArray(question.answerParts) && question.answerParts.length) {
      return question.answerParts.every((part) => part.trim());
    }
    return (question.answer || "").trim();
  };

  const pendingIndexes = useMemo(
    () =>
      questions
        .map((question, idx) =>
          question.correct === true ? null : { idx, question }
        )
        .filter(Boolean),
    [questions]
  );

  const allPendingAnswered = pendingIndexes.every(({ question, idx }) =>
    questionHasResponse(question, idx)
  );

  const canCheck =
    pendingIndexes.length > 0 && allPendingAnswered && !isChecking;
  const hasIncorrect = questions.some((question) => question.correct === false);

  const handleAnswerChange = (qIdx, inputIdx, value) => {
    setQuestions((prev) =>
      prev.map((question, idx) => {
        if (idx !== qIdx || question.correct === true || question.loading)
          return question;

        const desiredLength = getInputCount(items[qIdx]);
        const baseParts = Array.isArray(question.answerParts)
          ? question.answerParts.slice(0, desiredLength)
          : [];
        if (baseParts.length < desiredLength) {
          baseParts.push(...Array(desiredLength - baseParts.length).fill(""));
        }
        const nextParts = [...baseParts];
        nextParts[inputIdx] = value;
        return {
          ...question,
          answerParts: nextParts,
          answer: nextParts.join("\n"),
        };
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
      setError("Please answer every prompt before checking.");
      return;
    }

    setError("");
    setIsChecking(true);

    setQuestions((prev) =>
      prev.map((question) =>
        question.correct === true
          ? question
          : { ...question, loading: true }
      )
    );

    await Promise.all(
      pendingIndexes.map(async ({ idx }) => {
        const item = items[idx] || {};
        const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
        const userAnswer = questionState.answer || "";
        const expectedAnswer =
          item.sample_answer || item.answer || item.expected_answer || "";

        try {
          const result = await evaluateAnswer({
            userId,
            exerciseType: "open",
            userAnswer,
            correctAnswer: expectedAnswer,
            sourceType: evaluationSourceType,
            exerciseId: resolvedExerciseId,
            questionNumber: item.number ?? idx + 1,
            questionPrompt:
              item.question ||
              item.text ||
              prompt ||
              title ||
              "Respond to the prompt.",
            extra: item.keywords
              ? { question_keywords: item.keywords }
              : undefined,
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
      prev.map((question, idx) => {
        if (question.correct === false) {
          return {
            ...DEFAULT_QUESTION_STATE,
            answerParts: Array(getInputCount(items[idx])).fill(""),
          };
        }
        return { ...question, loading: false };
      })
    );
    setIsChecking(false);
    setHasChecked(false);
    setError("");
  };

  const firstQuestionRaw = items[0]?.question || items[0]?.text || "";
  const normalizedPrompt = normalizeText(prompt);
  const normalizedFirstQuestion = normalizeText(firstQuestionRaw);
  const shouldRenderPrompt =
    normalizedPrompt.length > 0 && normalizedPrompt !== normalizedFirstQuestion;

  return (
    <div className="oe-wrap">
      {title && showTitle && <h3 className="oe-title">{title}</h3>}
      {shouldRenderPrompt && <p className="oe-prompt">{prompt}</p>}

      {items.map((item, qIdx) => {
        const hasAudio = Boolean(item.audio_key);

        if (isExampleItem(item)) {
          const imageUrl = item.image_key ? images[item.image_key] : null;
          const exampleAnswer =
            item.sample_answer ||
            item.answer ||
            item.expected_answer ||
            item.keywords ||
            "";
          return (
            <div
              key={`question-${qIdx}`}
              className="oe-question oe-example st-example"
            >
              <p className="st-example-label">Example</p>
              {imageUrl && (
                <div className="fb-image-container">
                  <img
                    src={imageUrl}
                    alt="Example prompt"
                    className="fb-image"
                  />
                </div>
              )}
              {hasAudio && (
                <div className="practice-audio-container">
                  <AudioButton
                    audioKey={item.audio_key}
                    audioIndex={audioIndex}
                    className="practice-audio-button"
                  />
                </div>
              )}
              <p className="oe-question-text">
                {item.question || item.text || ""}
              </p>
              {exampleAnswer && (
                <p className="st-example-meta st-example-answer">
                  <strong>Answer:</strong> {exampleAnswer}
                </p>
              )}
            </div>
          );
        }

        const questionState = questions[qIdx] || DEFAULT_QUESTION_STATE;
        const disabled =
          questionState.correct === true || questionState.loading === true;
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const numberLabel = item.number ?? qIdx + 1;
        const inputCount = getInputCount(item);
        const answerParts =
          questionState.answerParts?.length === inputCount
            ? questionState.answerParts
            : (() => {
                const next = Array(inputCount).fill("");
                if (Array.isArray(questionState.answerParts)) {
                  questionState.answerParts.forEach((part, idx) => {
                    if (idx < inputCount) next[idx] = part;
                  });
                } else if (questionState.answer) {
                  next[0] = questionState.answer;
                }
                return next;
              })();

        return (
          <div key={`question-${qIdx}`} className="oe-question">
            {imageUrl && (
              <div className="fb-image-container">
                <img
                  src={imageUrl}
                  alt={`Question ${numberLabel}`}
                  className="fb-image"
                />
              </div>
            )}

            {hasAudio && (
              <div className="practice-audio-container">
                <AudioButton
                  audioKey={item.audio_key}
                  audioIndex={audioIndex}
                  className="practice-audio-button"
                />
              </div>
            )}

            <p className="oe-question-text">
              {numberLabel}. {item.question || item.text || ""}
            </p>

            {answerParts.map((value, partIdx) => (
              <div className="oe-input-wrap" key={`input-${qIdx}-${partIdx}`}>
                {inputCount > 1 && (
                  <label className="oe-input-label">
                    Part {partIdx + 1} of {inputCount}
                  </label>
                )}
                <textarea
                  rows={3}
                  value={value}
                  onChange={(event) =>
                    handleAnswerChange(qIdx, partIdx, event.target.value)
                  }
                  disabled={disabled}
                  className="oe-textarea"
                  placeholder="Type your answer here"
                />
                {partIdx === 0 && <InlineStatus state={questionState} />}
              </div>
            ))}

            <QuestionFeedback state={questionState} />

            {item.sample_answer && (
              <details className="oe-sample-answer">
                <summary>Sample answer</summary>
                <p>{item.sample_answer}</p>
              </details>
            )}
          </div>
        );
      })}

      {error && <p className="ai-error-message">{error}</p>}

      <div className="oe-buttons">
        <button
          className="ai-eval-button"
          onClick={handleCheckAnswers}
          disabled={!canCheck}
        >
          {isChecking ? checkingLabel : checkLabel}
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

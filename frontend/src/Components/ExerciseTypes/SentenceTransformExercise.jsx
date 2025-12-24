import React, { useEffect, useMemo, useState } from "react";
import AudioButton from "../AudioButton";
import { useAuth } from "../../AuthContext";
import evaluateAnswer from "./evaluateAnswer";
import { normalizeAiCorrect } from "./normalizeAiCorrect";
import { InlineStatus, QuestionFeedback } from "./aiFeedback";
import { copy, pick } from "../../ui-lang/i18n";
import CheckAnswersButton from "./CheckAnswersButton";
import "./evaluateAnswer.css";

const DEFAULT_QUESTION_STATE = {
  answer: "",
  feedback: null,
  correct: null,
  score: null,
  loading: false,
  markedAsCorrect: null, // null, true, or false
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

const hasCorrectTag = (item) => {
  const value = (item?.correct || "").trim().toLowerCase();
  return value === "yes" || value === "no";
};

export default function SentenceTransformExercise({
  exercise = {},
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
  showTitle = true,
  contentLang = "en",
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
          const itemCorrect = (item?.correct || "").toLowerCase();
          return {
            ...DEFAULT_QUESTION_STATE,
            answer: item?.answer || "",
            correct: true,
            markedAsCorrect: itemCorrect === "yes" ? true : itemCorrect === "no" ? false : null,
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
  const checkLabel = pick(copy.lessonContent.checkAnswers, contentLang);
  const checkingLabel = pick(copy.lessonContent.checking, contentLang);
  const rewritePlaceholder =
    contentLang === "th" ? "เขียนประโยคใหม่" : "Rewrite this sentence";
  const alreadyCorrectPlaceholder =
    contentLang === "th" ? "ประโยคนี้ถูกต้องแล้ว" : "Already correct";

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
    // Allow marked as correct to count as answered
    if (hasCorrectTag(item) && question.markedAsCorrect === true) return true;
    // Allow already correct sentences to be left blank
    return hasCorrectTag(item) && (item?.correct || "").toLowerCase() === "yes";
  });

  const hasIncompleteAnswers =
    pendingIndexes.length > 0 && !pendingHaveAnswers;

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

  const handleMarkCorrect = (idx, isCorrect) => {
    setQuestions((prev) =>
      prev.map((question, questionIdx) => {
        if (questionIdx !== idx || question.correct === true || question.loading)
          return question;
        if (!hasCorrectTag(items[idx])) return question;
        return {
          ...question,
          markedAsCorrect: isCorrect,
          answer: isCorrect ? (items[idx]?.text || "") : ""
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
    <div className="fb-wrap st-wrap">
      {title && showTitle && <h3 className="st-title">{title}</h3>}
      {prompt && <p className="st-prompt">{prompt}</p>}

      {items.map((item, idx) => {
        const hasAudio = Boolean(item?.audio_key);
        const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
        const exampleItem = isExampleItem(item);
        const showMarkButtons = hasCorrectTag(item);
        const thaiStem =
          contentLang === "th" && typeof item?.text_th === "string"
            ? item.text_th.trim()
            : "";

        if (exampleItem) {
          const imageUrl = item?.image_key ? images[item.image_key] : null;
          const answerValue =
            questionState.answer || item?.answer || item?.text || "";

          return (
            <React.Fragment key={`sentence-${idx}`}>
            <div className="st-example">
              <div className="fb-row st-question">
                <div className="fb-row-number">
                  <span aria-hidden="true" />
                </div>

                <div className="fb-row-main">
                  {imageUrl && (
                    <div className="fb-image-container">
                      <img
                        src={imageUrl}
                        alt="Example sentence"
                        className="fb-image"
                      />
                    </div>
                  )}

                  <div className="fb-row-content">
                    <p className="st-example-label">Example</p>
                    {hasAudio && (
                      <div className="practice-audio-container">
                        <AudioButton
                          audioKey={item.audio_key}
                          audioIndex={audioIndex}
                          className="practice-audio-button"
                        />
                      </div>
                    )}
                    <div className="st-stem-row">
                      <p className="st-stem">{item?.text}</p>
                      {showMarkButtons && (
                        <div className="st-mark-buttons">
                          <button
                            className={`st-mark-btn ${questionState.markedAsCorrect === true ? 'active' : ''}`}
                            disabled={true}
                            aria-label="Mark as correct"
                            title="This sentence is already correct"
                          >
                            <img
                              src={questionState.markedAsCorrect === true ? "/images/grey-check.webp" : "/images/white-check.webp"}
                              alt="Correct"
                              className="st-mark-icon"
                            />
                          </button>
                          <button
                            className={`st-mark-btn ${questionState.markedAsCorrect === false ? 'active' : ''}`}
                            disabled={true}
                            aria-label="Mark as incorrect"
                            title="This sentence needs to be rewritten"
                          >
                            <img
                              src={questionState.markedAsCorrect === false ? "/images/grey-x.webp" : "/images/white-x.webp"}
                              alt="Incorrect"
                              className="st-mark-icon"
                            />
                          </button>
                        </div>
                      )}
                    </div>
                    {thaiStem && <p className="st-stem-th">{thaiStem}</p>}
                    <div className="fb-input-wrap st-input-wrap">
                      <input
                        type="text"
                        value={answerValue}
                        disabled
                        className="fb-input st-input"
                      />
                      <InlineStatus state={questionState} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            </React.Fragment>
          );
        }

        const disabled =
          questionState.correct === true || questionState.loading === true;
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const numberLabel = item.number ?? idx + 1;

        return (
          <React.Fragment key={`sentence-${idx}`}>
          <div className="fb-row st-question">
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
                      audioKey={item.audio_key}
                      audioIndex={audioIndex}
                      className="practice-audio-button"
                    />
                  </div>
                )}
                <div className="st-stem-row">
                  <p className="st-stem">{item.text}</p>
                  {showMarkButtons && (
                    <div className="st-mark-buttons">
                      <button
                        className={`st-mark-btn ${questionState.markedAsCorrect === true ? 'active' : ''}`}
                        onClick={() => handleMarkCorrect(idx, true)}
                        disabled={disabled}
                        aria-label="Mark as correct"
                        title="This sentence is already correct"
                      >
                        <img
                          src={questionState.markedAsCorrect === true ? "/images/grey-check.webp" : "/images/white-check.webp"}
                          alt="Correct"
                          className="st-mark-icon"
                        />
                      </button>
                      <button
                        className={`st-mark-btn ${questionState.markedAsCorrect === false ? 'active' : ''}`}
                        onClick={() => handleMarkCorrect(idx, false)}
                        disabled={disabled}
                        aria-label="Mark as incorrect"
                        title="This sentence needs to be rewritten"
                      >
                        <img
                          src={questionState.markedAsCorrect === false ? "/images/grey-x.webp" : "/images/white-x.webp"}
                          alt="Incorrect"
                          className="st-mark-icon"
                        />
                      </button>
                    </div>
                  )}
                </div>
                {thaiStem && <p className="st-stem-th">{thaiStem}</p>}
                <div className="fb-input-wrap st-input-wrap">
                  <input
                    type="text"
                    value={questionState.answer}
                    onChange={(event) => handleChange(idx, event.target.value)}
                    disabled={disabled || questionState.markedAsCorrect === true}
                    placeholder={
                      questionState.markedAsCorrect === true
                        ? alreadyCorrectPlaceholder
                        : rewritePlaceholder
                    }
                    className="fb-input st-input"
                  />
                  <InlineStatus state={questionState} />
                </div>
                <QuestionFeedback state={questionState} />
              </div>
            </div>
          </div>
          </React.Fragment>
        );
      })}

      {error && <p className="ai-error-message">{error}</p>}

      <div className="fb-button-container">
        <CheckAnswersButton
          onClick={handleCheckAnswers}
          disabled={!canCheck}
          isChecking={isChecking}
          label={checkLabel}
          checkingLabel={checkingLabel}
          hasIncompleteAnswers={hasIncompleteAnswers}
          contentLang={contentLang}
        />
        {hasChecked && hasIncorrect && (
          <button
            onClick={handleTryAgain}
            className="apply-submit st-try-again"
            type="button"
          >
            TRY AGAIN
          </button>
        )}
      </div>
    </div>
  );
}

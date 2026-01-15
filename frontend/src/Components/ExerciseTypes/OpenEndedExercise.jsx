import React, { useEffect, useMemo, useState } from "react";
import AudioButton from "../AudioButton";
import InlineText from "../InlineText";
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

const isNonEmptyString = (value) =>
  typeof value === "string" && value.trim().length > 0;

const pickFieldByLang = (entity, field, lang) => {
  if (!entity || typeof entity !== "object") return null;

  const base = isNonEmptyString(entity[field]) ? entity[field].trim() : null;
  const en = isNonEmptyString(entity[`${field}_en`])
    ? entity[`${field}_en`].trim()
    : null;
  const th = isNonEmptyString(entity[`${field}_th`])
    ? entity[`${field}_th`].trim()
    : null;

  if (lang === "th") {
    return th ?? base ?? en ?? null;
  }
  if (lang === "en") {
    return en ?? base ?? th ?? null;
  }
  return base ?? en ?? th ?? null;
};

const stripAltTextLines = (value) => {
  if (typeof value !== "string") return "";
  const lines = value.split("\n");
  const filtered = lines.filter((line) => !/^\s*ALT-TEXT\s*:/i.test(line));
  return filtered.join("\n").trim();
};

const resolveQuestionText = (item, lang) => {
  if (!item) return "";
  const keys = ["question", "text", "prompt"];
  for (const key of keys) {
    const value = pickFieldByLang(item, key, lang);
    const cleaned = stripAltTextLines(value);
    if (cleaned) return cleaned;
  }
  return "";
};

const resolvePlaceholder = (item, lang) =>
  pickFieldByLang(item, "placeholder", lang);

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
  const displayTitle =
    pickFieldByLang(exercise, "title", contentLang) || title || "";
  const promptEn =
    pickFieldByLang(exercise, "prompt_en", "en") ||
    pickFieldByLang(exercise, "prompt", "en") ||
    exercise?.prompt_md ||
    prompt ||
    "";
  const promptTh =
    pickFieldByLang(exercise, "prompt_th", "th") ||
    pickFieldByLang(exercise, "prompt", "th") ||
    exercise.prompt_th ||
    exercise.prompt ||
    "";
  const displayPrompt = contentLang === "th" ? promptTh : promptEn;
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
        const evaluationPrompt =
          resolveQuestionText(item, "en") ||
          pickFieldByLang(exercise, "prompt", "en") ||
          pickFieldByLang(exercise, "title", "en") ||
          "Respond to the prompt.";

        try {
          const result = await evaluateAnswer({
            userId,
            exerciseType: "open",
            userAnswer,
            correctAnswer: expectedAnswer,
            sourceType: evaluationSourceType,
            exerciseId: resolvedExerciseId,
            questionNumber: item.number ?? idx + 1,
            questionPrompt: evaluationPrompt,
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

  const firstQuestionEn = resolveQuestionText(items[0], "en");
  const firstQuestionTh = resolveQuestionText(items[0], "th");
  const normalizedPrompt = normalizeText(displayPrompt);
  const normalizedFirstQuestionEn = normalizeText(firstQuestionEn);
  const normalizedFirstQuestionTh = normalizeText(firstQuestionTh);
  const hasPromptTranslation =
    contentLang !== "th" || normalizeText(promptTh);
  const shouldRenderPrompt =
    hasPromptTranslation &&
    normalizedPrompt.length > 0 &&
    normalizedPrompt !== normalizedFirstQuestionEn &&
    normalizedPrompt !== normalizedFirstQuestionTh;

  const defaultPlaceholder =
    contentLang === "th" ? "พิมพ์คำตอบของคุณที่นี่" : "Type your answer here";

  return (
    <div className="fb-wrap oe-wrap">
      {displayTitle && showTitle && (
        <h3 className="oe-title">{displayTitle}</h3>
      )}
      {shouldRenderPrompt && <p className="oe-prompt">{displayPrompt}</p>}

      {items.map((item, qIdx) => {
        const hasAudio = Boolean(item.audio_key);
        const questionEn = resolveQuestionText(item, "en");
        const questionTh = resolveQuestionText(item, "th");
        const displayQuestion =
          contentLang === "th" ? questionEn || questionTh : questionEn || questionTh;
        const questionInlines = item.text_jsonb || null;
        const questionInlinesTh = item.text_jsonb_th || null;

        if (isExampleItem(item)) {
          const imageUrl = item.image_key ? images[item.image_key] : null;
          const exampleAnswer =
            item.sample_answer ||
            item.answer ||
            item.expected_answer ||
            item.keywords ||
            "";

          return (
            <div key={`question-${qIdx}`} className="st-example oe-example">
              <div className="fb-row st-question">
                <div className="fb-row-number">
                  <span aria-hidden="true" />
                </div>

                <div className="fb-row-main">
                  {imageUrl && (
                    <div className="fb-image-container">
                      <img
                        src={imageUrl}
                        alt="Example prompt"
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
                    <InlineText
                      as="p"
                      className="oe-question-text"
                      inlines={questionInlines}
                      text={displayQuestion}
                    />
                    {contentLang === "th" && questionTh && questionEn && (
                      <InlineText
                        as="p"
                        className="oe-question-text"
                        inlines={questionInlinesTh}
                        text={questionTh}
                      />
                    )}
                    {exampleAnswer && (
                      <div className="fb-input-wrap oe-input-wrap">
                        <textarea
                          value={exampleAnswer}
                          className="oe-textarea oe-textarea-example"
                          disabled
                          rows={3}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        }

        const questionState = questions[qIdx] || DEFAULT_QUESTION_STATE;
        const disabled =
          questionState.correct === true || questionState.loading === true;
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const numberLabel = item.number ?? qIdx + 1;
        const inputCount = getInputCount(item);
        const placeholder =
          resolvePlaceholder(item, contentLang) || defaultPlaceholder;
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
          <div key={`question-${qIdx}`} className="fb-row oe-question">
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

                <InlineText
                  as="p"
                  className="oe-question-text"
                  inlines={questionInlines}
                  text={displayQuestion}
                />
                {contentLang === "th" && questionTh && questionEn && (
                  <InlineText
                    as="p"
                    className="oe-question-text"
                    inlines={questionInlinesTh}
                    text={questionTh}
                  />
                )}

                {answerParts.map((value, partIdx) => (
                  <div
                    className="fb-input-wrap oe-input-wrap"
                    key={`input-${qIdx}-${partIdx}`}
                  >
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
                      placeholder={placeholder}
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
            </div>
          </div>
        );
      })}

      {error && <p className="ai-error-message">{error}</p>}

      <div className="fb-button-container">
        <button
          className="apply-submit"
          onClick={handleCheckAnswers}
          disabled={!canCheck}
        >
          {isChecking ? checkingLabel : checkLabel}
        </button>

        {hasChecked && hasIncorrect && (
          <button
            className="apply-submit oe-try-again"
            onClick={handleTryAgain}
            type="button"
          >
            TRY AGAIN
          </button>
        )}
      </div>
    </div>
  );
}

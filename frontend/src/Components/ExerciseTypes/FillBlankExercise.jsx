import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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

const segmentTextWithBlanks = (text = "") => {
  if (typeof text !== "string" || text.length === 0) {
    return [{ type: "text", content: "" }];
  }

  const segments = [];
  let buffer = "";
  let index = 0;

  const flushBuffer = () => {
    if (buffer) {
      segments.push({ type: "text", content: buffer });
      buffer = "";
    }
  };

  while (index < text.length) {
    const char = text[index];

    if (char === "\n") {
      flushBuffer();
      segments.push({ type: "line-break" });
      index += 1;
      continue;
    }

    if (char === "_") {
      flushBuffer();

      let underscoreCount = 0;
      while (
        index + underscoreCount < text.length &&
        text[index + underscoreCount] === "_"
      ) {
        underscoreCount += 1;
      }

      const blankLength = Math.min(underscoreCount, 4);
      segments.push({ type: "blank", length: blankLength });

      index += underscoreCount;
      continue;
    }

    buffer += char;
    index += 1;
  }

  flushBuffer();
  return segments.length ? segments : [{ type: "text", content: "" }];
};

const renderMultiline = (text = "") => {
  if (!text) return null;

  return <span className="fb-text-block">{text}</span>;
};

export default function FillBlankExercise({
  exercise,
  images = {},
  audioIndex = {},
  sourceType = "practice",
  exerciseId,
  userId: userIdProp,
  showTitle = true,
  contentLang = "en",
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
      items.map((item) => ({
        ...DEFAULT_QUESTION_STATE,
        ...(isExampleItem(item)
          ? {
              correct: true,
              loading: false,
              answer: item.answer || "",
            }
          : {}),
      })),
    [items]
  );

  const [questions, setQuestions] = useState(initialQuestions);
  const [isChecking, setIsChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [error, setError] = useState("");
  const rowTextRefs = useRef([]);
  const [wrappedRows, setWrappedRows] = useState([]);

  useEffect(() => {
    setQuestions(initialQuestions);
    setIsChecking(false);
    setHasChecked(false);
    setError("");
  }, [initialQuestions]);

  useLayoutEffect(() => {
    const elements = rowTextRefs.current;
    if (!elements.length) return;

    const computeWrappedRows = () => {
      const next = elements.map((el) => {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        let lineHeight = Number.parseFloat(style.lineHeight);
        if (!Number.isFinite(lineHeight)) {
          const fontSize = Number.parseFloat(style.fontSize) || 16;
          lineHeight = fontSize * 1.2;
        }
        return el.offsetHeight > lineHeight * 1.5;
      });
      setWrappedRows(next);
    };

    computeWrappedRows();
    const observer = new ResizeObserver(computeWrappedRows);
    elements.forEach((el) => {
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [items, contentLang]);

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
  const hasIncompleteAnswers =
    pendingIndexes.length > 0 && !allPendingAnswered;

  const canCheck =
    pendingIndexes.length > 0 && allPendingAnswered && !isChecking;
  const hasIncorrect = questions.some((question) => question.correct === false);
  const checkLabel = pick(copy.lessonContent.checkAnswers, contentLang);
  const checkingLabel = pick(copy.lessonContent.checking, contentLang);

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
                placeholder=""
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
              placeholder=""
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
      const hasAudio = Boolean(item.audio_key);
      const example = isExampleItem(item);

      if (example) {
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const textSegments = segmentTextWithBlanks(item.text || "");
        return (
          <React.Fragment key={`example-${idx}`}>
          <div
            className="fb-row fb-example st-example"
          >
            <p className="st-example-label">Example</p>
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt="Example item" className="fb-image" />
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
              <div className="fb-row-text">
                {textSegments.map((segment, segmentIdx) => {
                  if (segment.type === "text") {
                    return (
                      <React.Fragment key={`example-text-${idx}-${segmentIdx}`}>
                        {renderMultiline(segment.content)}
                      </React.Fragment>
                    );
                  }

                  if (segment.type === "line-break") {
                    return (
                      <span
                        key={`example-break-${idx}-${segmentIdx}`}
                        className="fb-line-break"
                        aria-hidden="true"
                      />
                    );
                  }

                  const blankLength = segment.length || 1;
                  const minWidthCh = 3 + blankLength * 2;
                  return (
                    <span
                      key={`example-blank-${idx}-${segmentIdx}`}
                      className="fb-example-blank"
                      style={{ minWidth: `${minWidthCh}ch` }}
                    />
                  );
                })}
              </div>
              {contentLang === "th" &&
                typeof item.text_th === "string" &&
                item.text_th.trim() && (
                  <div className="fb-row-th fb-row-th--inline">
                    {renderMultiline(item.text_th.trim())}
                  </div>
                )}
              {item.answer && (
                <p className="st-example-meta st-example-answer">
                  <strong>Answer:</strong> {item.answer}
                </p>
              )}
            </div>
          </div>
          </React.Fragment>
        );
      }

      const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
      const disabled =
        questionState.correct === true || questionState.loading === true;
      const imageUrl = item.image_key ? images[item.image_key] : null;
      const textSegments = segmentTextWithBlanks(item.text || "");
      const hasBlank = textSegments.some((segment) => segment.type === "blank");
      const hasMultiline = textSegments.some(
        (segment) =>
          segment.type === "line-break" ||
          (segment.type === "text" && segment.content?.includes("\n"))
      );
      const displayNumber = item.number ?? idx + 1;

      return (
        <React.Fragment key={`${item.number ?? idx}-${idx}`}>
        <div
          className={`fb-row fb-row--fill-blank${hasMultiline ? " fb-row-multiline" : ""}${wrappedRows[idx] ? " fb-row--wrapped" : ""}`}
        >
          <div className="fb-row-number fb-row-number--fill-blank">
            <span>{displayNumber}</span>
          </div>

          <div className="fb-row-main">
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
              {hasAudio && (
                <div className="practice-audio-container">
                  <AudioButton
                    audioKey={item.audio_key}
                    audioIndex={audioIndex}
                    className="practice-audio-button"
                  />
                </div>
              )}
              <div
                className="fb-row-text"
                ref={(el) => {
                  rowTextRefs.current[idx] = el;
                }}
              >
                {(() => {
                  const nodes = [];
                  for (let segmentIdx = 0; segmentIdx < textSegments.length; segmentIdx += 1) {
                    const segment = textSegments[segmentIdx];
                    if (segment.type === "text") {
                      const next = textSegments[segmentIdx + 1];
                      const nextNext = textSegments[segmentIdx + 2];
                      const canInline =
                        next?.type === "blank" &&
                        nextNext?.type === "text" &&
                        !segment.content?.includes("\n") &&
                        !nextNext.content?.includes("\n");
                      const answerLength = (item?.answer || "").trim().length;
                      const isShortAnswer = answerLength > 0 && answerLength <= 8;

                      if (canInline && isShortAnswer) {
                        const blankLength = next.length || 1;
                        const minWidthCh = 3 + blankLength * 2;
                        const inputMinWidthCh = 8;
                        nodes.push(
                          <React.Fragment key={`inline-${idx}-${segmentIdx}`}>
                            <span className="fb-inline-pair">
                              {renderMultiline(segment.content)}
                              <span className="fb-input-wrap fb-input-wrap--short">
                                <input
                                  type="text"
                                  className="fb-input fb-input--short"
                                  value={questionState.answer}
                                  onChange={(event) =>
                                    handleAnswerChange(idx, event.target.value)
                                  }
                                  disabled={disabled}
                                  placeholder=""
                                  style={{
                                    minWidth: `${inputMinWidthCh}ch`,
                                  }}
                                />
                                <InlineStatus state={questionState} />
                              </span>
                            </span>
                            {renderMultiline(nextNext.content)}
                          </React.Fragment>
                        );
                        segmentIdx += 2;
                        continue;
                      }

                      nodes.push(
                        <React.Fragment key={`text-${idx}-${segmentIdx}`}>
                          {renderMultiline(segment.content)}
                        </React.Fragment>
                      );
                      continue;
                    }

                    if (segment.type === "line-break") {
                      nodes.push(
                        <span
                          key={`break-${idx}-${segmentIdx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );
                      continue;
                    }

                    const blankLength = segment.length || 1;
                    const minWidthCh = 3 + blankLength * 2;
                    const answerLength = (item?.answer || "").trim().length;
                    const isShortAnswer = answerLength > 0 && answerLength <= 8;
                    const inputMinWidthCh = isShortAnswer ? 8 : minWidthCh;
                    nodes.push(
                      <div
                        key={`blank-${idx}-${segmentIdx}`}
                        className={`fb-input-wrap${isShortAnswer ? " fb-input-wrap--short" : " fb-input-wrap--long"}`}
                      >
                        <input
                          type="text"
                          className={`fb-input${isShortAnswer ? " fb-input--short" : " fb-input--long"}`}
                          value={questionState.answer}
                          onChange={(event) =>
                            handleAnswerChange(idx, event.target.value)
                          }
                          disabled={disabled}
                          placeholder=""
                          style={{
                            minWidth: `${inputMinWidthCh}ch`,
                          }}
                        />
                        <InlineStatus state={questionState} />
                      </div>
                    );
                  }

                  if (!hasBlank) {
                    const answerLength = (item?.answer || "").trim().length;
                    const isShortAnswer = answerLength > 0 && answerLength <= 8;
                    const inputMinWidthCh = isShortAnswer ? 8 : 12;
                    nodes.push(
                      <div
                        key={`blank-${idx}-fallback`}
                        className={`fb-input-wrap${isShortAnswer ? " fb-input-wrap--short" : " fb-input-wrap--long"}`}
                      >
                        <input
                          type="text"
                          className={`fb-input${isShortAnswer ? " fb-input--short" : " fb-input--long"}`}
                          value={questionState.answer}
                          onChange={(event) =>
                            handleAnswerChange(idx, event.target.value)
                          }
                          disabled={disabled}
                          placeholder=""
                          style={{
                            minWidth: `${inputMinWidthCh}ch`,
                          }}
                        />
                        <InlineStatus state={questionState} />
                      </div>
                    );
                  }
                  return nodes;
                })()}
              </div>

              <QuestionFeedback state={questionState} />
            </div>
          </div>
        </div>
        {contentLang === "th" &&
          typeof item.text_th === "string" &&
          item.text_th.trim() && (
            <div className="fb-row-th">
              {renderMultiline(item.text_th.trim())}
            </div>
          )}
        </React.Fragment>
      );
    });

  return (
    <div className="fb-wrap">
      {/* {title && showTitle && <h3 className="fb-title">{title}</h3>} */}
      {prompt && <p className="fb-prompt">{prompt}</p>}

      {paragraph ? (
        <p className="fb-paragraph">{renderParagraphWithInputs()}</p>
      ) : (
        renderRowItems()
      )}

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
            className="apply-submit fb-try-again"
            type="button"
            onClick={handleTryAgain}
          >
            TRY AGAIN
          </button>
        )}
      </div>
    </div>
  );
}

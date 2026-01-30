import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import AudioButton from "../AudioButton";
import InlineText from "../InlineText";
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
  answersByBlank: {},
};

const isExampleItem = (item) => {
  if (!item) return false;
  if (typeof item.is_example === "boolean") {
    return item.is_example;
  }
  if (typeof item.number === "string") {
    const normalized = item.number.trim().toLowerCase();
    return normalized === "example" || normalized === "ex" || normalized === "ตัวอย่าง";
  }
  return false;
};

const cleanInlineMediaTags = (text) => {
  if (!text || typeof text !== "string") return text;
  return text
    .replace(/\[audio:[^\]]+\]/gi, " ")
    .replace(/\[img:[^\]]+\]/gi, " ")
    .replace(/[^\S\r\n]+/g, " ")
    .replace(/\s*\n\s*/g, "\n");
};

const segmentTextWithBlanks = (text = "") => {
  const cleaned = cleanInlineMediaTags(text);
  if (typeof cleaned !== "string" || cleaned.length === 0) {
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

  while (index < cleaned.length) {
    const char = cleaned[index];

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
        index + underscoreCount < cleaned.length &&
        cleaned[index + underscoreCount] === "_"
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

const buildInlineSegments = (inlines = []) => {
  const segments = [];
  inlines.forEach((span) => {
    const text = cleanInlineMediaTags(span?.text || "");
    if (!text) return;
    let buffer = "";
    let index = 0;

    const flushBuffer = () => {
      if (buffer) {
        segments.push({ type: "text", content: buffer, style: span });
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
        segments.push({ type: "blank", length: underscoreCount });
        index += underscoreCount;
        continue;
      }

      buffer += char;
      index += 1;
    }

    flushBuffer();
  });
  return segments.length ? segments : [{ type: "text", content: "" }];
};

const buildStyledRunsFromInlines = (inlines = []) =>
  (inlines || [])
    .map((span) => ({
      text: cleanInlineMediaTags(span?.text || ""),
      style: span,
    }))
    .filter((run) => run.text);

const THAI_RE = /[\u0E00-\u0E7F]/;
const hasThai = (value) => THAI_RE.test(value || "");

const renderMultiline = (text = "") => {
  if (!text) return null;

  return (
    <span className={`fb-text-block${hasThai(text) ? " fb-text-th" : ""}`}>
      {text}
    </span>
  );
};

const renderStyledText = (content, style) => {
  const textStyle = {
    fontWeight: style?.bold ? "700" : undefined,
    fontStyle: style?.italic ? "italic" : undefined,
    textDecoration: style?.underline ? "underline" : undefined,
    whiteSpace: "pre-line",
  };
  const thaiClass = hasThai(content) ? " fb-text-th" : "";
  return (
    <span style={textStyle} className={`fb-text-block${thaiClass}`}>
      {content}
    </span>
  );
};

const renderTokenWithStyles = (text, cursor, keyPrefix) => {
  if (!text) return null;
  const nodes = [];
  let remaining = text;
  let pieceIndex = 0;

  while (remaining) {
    if (!cursor || cursor.disabled || !cursor.runs?.length) {
      nodes.push(
        <React.Fragment key={`${keyPrefix}-plain-${pieceIndex}`}>
          {renderMultiline(remaining)}
        </React.Fragment>
      );
      break;
    }

    const run = cursor.runs[cursor.index];
    if (!run) {
      cursor.disabled = true;
      nodes.push(
        <React.Fragment key={`${keyPrefix}-plain-${pieceIndex}`}>
          {renderMultiline(remaining)}
        </React.Fragment>
      );
      break;
    }

    const runText = run.text.slice(cursor.offset);
    if (!runText) {
      cursor.index += 1;
      cursor.offset = 0;
      continue;
    }

    if (!remaining.startsWith(runText[0])) {
      cursor.disabled = true;
      nodes.push(
        <React.Fragment key={`${keyPrefix}-plain-${pieceIndex}`}>
          {renderMultiline(remaining)}
        </React.Fragment>
      );
      break;
    }

    const takeLen = Math.min(remaining.length, runText.length);
    const piece = remaining.slice(0, takeLen);
    if (piece !== runText.slice(0, takeLen)) {
      cursor.disabled = true;
      nodes.push(
        <React.Fragment key={`${keyPrefix}-plain-${pieceIndex}`}>
          {renderMultiline(remaining)}
        </React.Fragment>
      );
      break;
    }

    nodes.push(
      <React.Fragment key={`${keyPrefix}-styled-${pieceIndex}`}>
        {renderStyledText(piece, run.style)}
      </React.Fragment>
    );
    remaining = remaining.slice(takeLen);
    cursor.offset += takeLen;
    if (cursor.offset >= run.text.length) {
      cursor.index += 1;
      cursor.offset = 0;
    }
    pieceIndex += 1;
  }

  return nodes;
};

const normalizeWhitespace = (value) =>
  (value || "").toString().replace(/\s+/g, " ").trim();

const renderStemBlocks = ({
  item,
  questionState,
  questionIndex,
  disabled,
  onBlankChange,
  readOnly = false,
}) => {
  const blocks = Array.isArray(item?.stem?.blocks) ? item.stem.blocks : [];
  const blanks = Array.isArray(item?.blanks) ? item.blanks : [];
  const nodes = [];

  const getBlankMeta = (blankId) =>
    blanks.find((blank) => blank.id === blankId) || { min_len: 1 };
  const answersV2 = Array.isArray(item?.answers_v2) ? item.answers_v2 : [];
  const getBlankAnswers = (blankId) => {
    const idx = blanks.findIndex((blank) => blank.id === blankId);
    if (idx === -1) return [];
    return Array.isArray(answersV2[idx]) ? answersV2[idx] : [];
  };

  blocks.forEach((block, blockIdx) => {
    if (block?.type !== "inline" || !Array.isArray(block.tokens)) return;
    block.tokens.forEach((token, tokenIdx) => {
      if (token.type === "text") {
        if (token.style) {
          nodes.push(
            <React.Fragment
              key={`stem-text-${questionIndex}-${blockIdx}-${tokenIdx}`}
            >
              {renderStyledText(token.text, token.style)}
            </React.Fragment>
          );
          return;
        }
        const tokenThaiClass = hasThai(token.text) ? " fb-text-th" : "";
        nodes.push(
          <span
            key={`stem-text-${questionIndex}-${blockIdx}-${tokenIdx}`}
            className={`fb-text-block${tokenThaiClass}`}
          >
            {token.text}
          </span>
        );
        return;
      }
      if (token.type === "line_break") {
        nodes.push(
          <span
            key={`stem-break-${questionIndex}-${blockIdx}-${tokenIdx}`}
            className="fb-line-break"
            aria-hidden="true"
          />
        );
        return;
      }
      if (token.type === "blank") {
        const blankId = token.id;
        const blankMeta = getBlankMeta(blankId);
        const blankLength = blankMeta?.min_len || 1;
        const blankAnswers = getBlankAnswers(blankId);
        const maxAnswerLen = blankAnswers.reduce(
          (maxLen, answer) => Math.max(maxLen, normalizeWhitespace(answer).length),
          0
        );
        const isShortBlank =
          (maxAnswerLen > 0 && maxAnswerLen <= 10) ||
          (maxAnswerLen === 0 && blankLength <= 4);
        const minWidthCh = isShortBlank ? 8 : Math.max(12, 3 + blankLength * 2);

        if (readOnly) {
          nodes.push(
            <span
              key={`stem-blank-${questionIndex}-${blockIdx}-${tokenIdx}`}
              className="fb-example-blank"
              style={{ minWidth: `${minWidthCh}ch` }}
            />
          );
          return;
        }

        nodes.push(
          <span
            key={`stem-input-${questionIndex}-${blockIdx}-${tokenIdx}`}
            className={`fb-input-wrap${isShortBlank ? " fb-input-wrap--short" : " fb-input-wrap--long"}`}
          >
            <input
              type="text"
              className={`fb-input${isShortBlank ? " fb-input--short" : " fb-input--long"}`}
              value={questionState.answersByBlank?.[blankId] || ""}
              onChange={(event) =>
                onBlankChange(questionIndex, blankId, event.target.value, item)
              }
              disabled={disabled}
              placeholder=""
              style={{
                minWidth: `${minWidthCh}ch`,
              }}
            />
            <InlineStatus state={questionState} />
          </span>
        );
      }
    });
  });

  return nodes;
};

const getStemStats = (item) => {
  const blocks = Array.isArray(item?.stem?.blocks) ? item.stem.blocks : [];
  let hasLineBreak = false;
  let blankCount = 0;
  blocks.forEach((block) => {
    if (block?.type !== "inline" || !Array.isArray(block.tokens)) return;
    block.tokens.forEach((token) => {
      if (token.type === "line_break") hasLineBreak = true;
      if (token.type === "blank") blankCount += 1;
    });
  });
  return { hasLineBreak, blankCount };
};

const buildAnswersByBlank = (item) => {
  const blanks = Array.isArray(item?.blanks) ? item.blanks : [];
  const answersV2 = Array.isArray(item?.answers_v2) ? item.answers_v2 : [];
  if (!blanks.length || !answersV2.length) return {};
  return blanks.reduce((acc, blank, idx) => {
    const options = answersV2[idx];
    if (Array.isArray(options) && options.length) {
      acc[blank.id] = options[0];
    }
    return acc;
  }, {});
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
  const {
    title,
    prompt,
    paragraph,
    items: rawItems = [],
    items_th: rawItemsTh = [],
  } = exercise || {};
  const { user } = useAuth();
  const userId = userIdProp || user?.id || null;
  const evaluationSourceType = ["bank", "practice"].includes(
    (sourceType || "").toLowerCase()
  )
    ? (sourceType || "").toLowerCase()
    : "practice";
  const resolvedExerciseId = exerciseId ?? exercise?.id ?? null;
  const promptBlocks = Array.isArray(exercise?.prompt_blocks)
    ? exercise.prompt_blocks
    : null;

  const displayItems = useMemo(() => {
    if (contentLang === "th" && rawItemsTh.length) {
      return rawItemsTh;
    }
    if (
      contentLang !== "th" &&
      Array.isArray(exercise?.items_en) &&
      exercise.items_en.length
    ) {
      return exercise.items_en;
    }
    return rawItems;
  }, [rawItems, rawItemsTh, contentLang, exercise?.items_en]);

  const items = displayItems;

  const initialQuestions = useMemo(
    () =>
      items.map((item) => ({
        ...DEFAULT_QUESTION_STATE,
        ...(isExampleItem(item)
          ? {
              correct: true,
              loading: false,
              answer: item.answer || "",
              answersByBlank: buildAnswersByBlank(item),
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

  const isItemAnswered = (item, questionState) => {
    const blanks = Array.isArray(item?.blanks) ? item.blanks : [];
    if (!blanks.length) {
      return Boolean((questionState?.answer || "").trim());
    }
    const answersByBlank = questionState?.answersByBlank || {};
    return blanks.every((blank) =>
      Boolean((answersByBlank[blank.id] || "").trim())
    );
  };

  const buildUserAnswer = (item, questionState) => {
    const blanks = Array.isArray(item?.blanks) ? item.blanks : [];
    const answersByBlank = questionState?.answersByBlank || {};
    const hasBlankAnswers = blanks.some((blank) =>
      Object.prototype.hasOwnProperty.call(answersByBlank, blank.id)
    );
    if (!blanks.length || !hasBlankAnswers) {
      return questionState?.answer || "";
    }
    const normalized = blanks.map((blank) =>
      normalizeWhitespace(answersByBlank[blank.id])
    );
    if (blanks.length === 1) {
      return normalized[0];
    }
    return normalized.join("; ");
  };

  const allPendingAnswered = pendingIndexes.every((idx) =>
    isItemAnswered(items[idx], questions[idx])
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

  const handleBlankAnswerChange = (idx, blankId, value, item) => {
    setQuestions((prev) =>
      prev.map((question, questionIdx) => {
        if (questionIdx !== idx || question.correct === true || question.loading)
          return question;
        const nextAnswers = {
          ...(question.answersByBlank || {}),
          [blankId]: value,
        };
        const userAnswer = buildUserAnswer(item, {
          ...question,
          answersByBlank: nextAnswers,
        });
        return {
          ...question,
          answersByBlank: nextAnswers,
          answer: userAnswer,
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
        const userAnswer = buildUserAnswer(item, questions[idx]);

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

  const renderPromptBlocks = () => {
    if (!promptBlocks?.length) {
      return prompt ? <p className="fb-prompt">{prompt}</p> : null;
    }
    return (
      <div className="fb-prompt">
        {promptBlocks.map((block, blockIdx) => {
          if (!block || typeof block !== "object") return null;
          if (block.type === "text") {
            return (
              <div key={`prompt-text-${blockIdx}`} className="fb-prompt-block">
                {block.text && <p className="fb-prompt-text">{block.text}</p>}
                {block.text_th && (
                  <p className="fb-prompt-th">{block.text_th}</p>
                )}
              </div>
            );
          }
          if (block.type === "list") {
            const itemsList = Array.isArray(block.items) ? block.items : [];
            return (
              <ul key={`prompt-list-${blockIdx}`} className="fb-prompt-list">
                {itemsList.map((itemText, itemIdx) => (
                  <li key={`prompt-list-${blockIdx}-${itemIdx}`}>{itemText}</li>
                ))}
              </ul>
            );
          }
          if (block.type === "image") {
            const imgSrc = block.image_key ? images[block.image_key] : null;
            if (!imgSrc) return null;
            return (
              <div key={`prompt-image-${blockIdx}`} className="fb-prompt-media">
                <img
                  src={imgSrc}
                  alt={block.alt_text || "Prompt image"}
                  className="fb-image"
                />
              </div>
            );
          }
          if (block.type === "audio") {
            if (!block.audio_key) return null;
            return (
              <div key={`prompt-audio-${blockIdx}`} className="fb-prompt-media">
                <AudioButton
                  audioKey={block.audio_key}
                  audioIndex={audioIndex}
                  className="practice-audio-button"
                />
              </div>
            );
          }
          return null;
        })}
      </div>
    );
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
      const questionState = questions[idx] || DEFAULT_QUESTION_STATE;
      const disabled =
        questionState.correct === true || questionState.loading === true;
      const shouldUseThaiStem =
        contentLang === "th" &&
        Array.isArray(item?.stem?.blocks) &&
        item.stem.blocks.length > 0;

      if (example) {
        if (shouldUseThaiStem) {
          const imageUrl = item.image_key ? images[item.image_key] : null;
          return (
            <React.Fragment key={`example-${idx}`}>
              <div className="fb-row fb-example st-example">
                {imageUrl && (
                  <div className="fb-image-container">
                    <img src={imageUrl} alt="Example item" className="fb-image" />
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
                  <div className="fb-row-text">
                    {renderStemBlocks({
                      item,
                      questionState,
                      questionIndex: idx,
                      disabled: true,
                      onBlankChange: handleBlankAnswerChange,
                      readOnly: true,
                    })}
                  </div>
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
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const textSegments = segmentTextWithBlanks(item.text || "");
        const inlineSegments = Array.isArray(item.text_jsonb)
          ? buildInlineSegments(item.text_jsonb)
          : null;
        const segmentsToRender = inlineSegments || textSegments;
        const hasBilingualAbPrompt =
          contentLang === "th" &&
          typeof item.text === "string" &&
          typeof item.text_th === "string" &&
          item.text_th.trim() &&
          /^\s*A:/m.test(item.text) &&
          /^\s*B:/m.test(item.text);
        return (
          <React.Fragment key={`example-${idx}`}>
          <div
            className="fb-row fb-example st-example"
          >
            {imageUrl && (
              <div className="fb-image-container">
                <img src={imageUrl} alt="Example item" className="fb-image" />
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
              <div className="fb-row-text">
                {hasBilingualAbPrompt
                  ? (() => {
                      const lines = item.text.split("\n");
                      const aLine =
                        lines.find((line) => line.trim().startsWith("A:")) || lines[0];
                      const bLine =
                        lines.find((line) => line.trim().startsWith("B:")) ||
                        lines[lines.length - 1];
                      const thaiLine = item.text_th.trim();
                      const nodes = [];
                      nodes.push(
                        <React.Fragment key={`example-ab-a-${idx}`}>
                          {renderMultiline(aLine)}
                        </React.Fragment>
                      );
                      nodes.push(
                        <span
                          key={`example-ab-a-break-${idx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );
                      nodes.push(
                        <React.Fragment key={`example-ab-th-${idx}`}>
                          {renderMultiline(thaiLine)}
                        </React.Fragment>
                      );
                      nodes.push(
                        <span
                          key={`example-ab-th-break-${idx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );

                      const underscoreMatch = bLine.match(/_{2,}/);
                      if (underscoreMatch) {
                        const before = bLine.slice(0, underscoreMatch.index);
                        const trimmedBefore = before.replace(/\s+$/, "");
                        const hadTrailingSpace = /\s+$/.test(before);
                        if (trimmedBefore) {
                          nodes.push(
                            <React.Fragment key={`example-ab-b-before-${idx}`}>
                              {renderMultiline(trimmedBefore)}
                            </React.Fragment>
                          );
                          if (hadTrailingSpace) {
                            nodes.push(" ");
                          }
                        }
                      } else {
                        nodes.push(
                          <React.Fragment key={`example-ab-b-${idx}`}>
                            {renderMultiline(bLine)}
                          </React.Fragment>
                        );
                        nodes.push(" ");
                      }

                      const blankLength = underscoreMatch
                        ? Math.min(underscoreMatch[0].length, 4)
                        : 1;
                      const minWidthCh = 3 + blankLength * 2;
                      nodes.push(
                        <span
                          key={`example-ab-blank-${idx}`}
                          className="fb-example-blank"
                          style={{ minWidth: `${minWidthCh}ch` }}
                        />
                      );

                      if (underscoreMatch) {
                        const after = bLine.slice(
                          underscoreMatch.index + underscoreMatch[0].length
                        );
                        if (after) {
                          nodes.push(
                            <React.Fragment key={`example-ab-b-after-${idx}`}>
                              {renderMultiline(after)}
                            </React.Fragment>
                          );
                        }
                      }

                      return nodes;
                    })()
                  : segmentsToRender.map((segment, segmentIdx) => {
                  if (segment.type === "text") {
                    return (
                      <React.Fragment key={`example-text-${idx}-${segmentIdx}`}>
                        {segment.style
                          ? renderStyledText(segment.content, segment.style)
                          : renderMultiline(segment.content)}
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
                item.text_th.trim() &&
                !hasBilingualAbPrompt && (
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

      if (shouldUseThaiStem) {
        const displayNumber = item.number ?? idx + 1;
        const imageUrl = item.image_key ? images[item.image_key] : null;
        const stemStats = getStemStats(item);
        const inlineClass = stemStats.hasLineBreak
          ? " fb-row--inline-multiline"
          : stemStats.blankCount === 1
          ? " fb-row--inline-single"
          : "";
        const thaiInlines = item.text_jsonb || null;
        const thaiText = item.text || "";
        return (
          <React.Fragment key={`${item.number ?? idx}-${idx}`}>
            <div className={`fb-row fb-row--fill-blank${inlineClass}`}>
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
                  <div className="fb-row-text">
                    {renderStemBlocks({
                      item,
                      questionState,
                      questionIndex: idx,
                      disabled,
                      onBlankChange: handleBlankAnswerChange,
                    })}
                  </div>
                  <QuestionFeedback state={questionState} />
                </div>
              </div>
            </div>
          </React.Fragment>
        );
      }

      const imageUrl = item.image_key ? images[item.image_key] : null;
      const useSchemaV2 = Array.isArray(item?.stem?.blocks) && item.stem.blocks.length > 0;
      const styledRuns = Array.isArray(item?.text_jsonb)
        ? buildStyledRunsFromInlines(item.text_jsonb)
        : null;
      const hasSingleBlankV2 =
        useSchemaV2 &&
        Array.isArray(item?.blanks) &&
        item.blanks.length === 1;
      const hasLineBreakV2 =
        useSchemaV2 &&
        item.stem.blocks.some((block) =>
          block?.type === "inline" &&
          Array.isArray(block.tokens) &&
          block.tokens.some((token) => token.type === "line_break")
        );
      const isInlineMultilineV2 =
        useSchemaV2 && (hasLineBreakV2 || item?.inline_multiline);
      const isInlineSingleBlank =
        useSchemaV2 &&
        hasSingleBlankV2 &&
        !hasLineBreakV2 &&
        !item.image_key &&
        !item.audio_key;
      const isMobile =
        typeof window !== "undefined" &&
        window.matchMedia &&
        window.matchMedia("(max-width: 480px)").matches;
      const singleBlankMeta = isInlineSingleBlank ? item?.blanks?.[0] : null;
      const singleBlankLength = singleBlankMeta?.min_len || 1;
      const singleBlankAnswers = Array.isArray(item.answers_v2)
        ? item.answers_v2[0] || []
        : [];
      const singleBlankMaxAnswerLen = singleBlankAnswers.reduce(
        (maxLen, answer) =>
          Math.max(maxLen, normalizeWhitespace(answer).length),
        0
      );
      const isShortSingleBlank =
        (singleBlankMaxAnswerLen > 0 && singleBlankMaxAnswerLen <= 10) ||
        (singleBlankMaxAnswerLen === 0 && singleBlankLength <= 4);
      const shouldStackThaiAboveLongBlank =
        isInlineSingleBlank && isMobile && !isShortSingleBlank;
      const textSegments = segmentTextWithBlanks(item.text || "");
      const inlineSegments = Array.isArray(item.text_jsonb)
        ? buildInlineSegments(item.text_jsonb)
        : null;
      const segmentsToRender = inlineSegments || textSegments;
      const hasBilingualAbPrompt =
        contentLang === "th" &&
        typeof item.text === "string" &&
        typeof item.text_th === "string" &&
        item.text_th.trim() &&
        /^\s*A:/m.test(item.text) &&
        /^\s*B:/m.test(item.text);
      const hasBlank = useSchemaV2
        ? Array.isArray(item?.blanks) && item.blanks.length > 0
        : segmentsToRender.some((segment) => segment.type === "blank");
      const hasMultiline = useSchemaV2
        ? item.stem.blocks.some((block) =>
            block?.type === "inline" &&
            Array.isArray(block.tokens) &&
            block.tokens.some((token) => token.type === "line_break")
          )
        : segmentsToRender.some(
            (segment) =>
              segment.type === "line-break" ||
              (segment.type === "text" && segment.content?.includes("\n"))
          );
      const answerLength = (item?.answer || "").trim().length;
      const isShortAnswer =
        !useSchemaV2 &&
        answerLength > 0 &&
        answerLength <= 10;
      const prefersInlineFlow =
        !useSchemaV2 &&
        isShortAnswer &&
        segmentsToRender.some((segment, segmentIdx) => {
          if (segment.type !== "text") return false;
          const next = segmentsToRender[segmentIdx + 1];
          const nextNext = segmentsToRender[segmentIdx + 2];
          return (
            next?.type === "blank" &&
            nextNext?.type === "text" &&
            !segment.content?.includes("\n") &&
            !nextNext.content?.includes("\n")
          );
        });
      const useInlineFlow = prefersInlineFlow && !hasBilingualAbPrompt;
      const questionInlinesTh = item.text_jsonb_th || null;
      const displayNumber = item.number ?? idx + 1;
      const cleanedText = cleanInlineMediaTags(item.text || "").trim();
      const promptHasInlineAnswer =
        Boolean(inlineSegments && cleanedText) && /(^|\n)B:\s*/.test(cleanedText);
      const shouldRenderPromptText = !useSchemaV2 && promptHasInlineAnswer;

      const renderPromptWithAnswer = () => {
        const lines = cleanedText.split("\n");
        const nodes = [];
        lines.forEach((line, lineIdx) => {
          if (lineIdx > 0) {
            nodes.push(
              <span
                key={`prompt-break-${idx}-${lineIdx}`}
                className="fb-line-break"
                aria-hidden="true"
              />
            );
          }
          const match = line.match(/^B:\s*(.*)$/);
          if (match) {
            const suffix = match[1].replace(/_{2,}/g, "").trim();
            const inputMinWidthCh = isShortAnswer ? 8 : 12;
            nodes.push(
              <span key={`prompt-b-${idx}-${lineIdx}`} className="fb-text-block">
                B:&nbsp;
              </span>
            );
            nodes.push(
              <span
                key={`prompt-input-${idx}-${lineIdx}`}
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
              </span>
            );
            if (suffix) {
              nodes.push(
                <span
                  key={`prompt-b-suffix-${idx}-${lineIdx}`}
                  className="fb-text-block"
                >
                  {` ${suffix}`}
                </span>
              );
            }
            return;
          }
          nodes.push(
            <span key={`prompt-text-${idx}-${lineIdx}`} className="fb-text-block">
              {line}
            </span>
          );
        });
        return nodes;
      };

      return (
        <React.Fragment key={`${item.number ?? idx}-${idx}`}>
        <div
          className={`fb-row fb-row--fill-blank${hasMultiline ? " fb-row-multiline" : ""}${wrappedRows[idx] ? " fb-row--wrapped" : ""}${isInlineSingleBlank ? " fb-row--inline-single" : ""}${isInlineMultilineV2 ? " fb-row--inline-multiline" : ""}`}
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
              {shouldRenderPromptText && (
                <div className="fb-row-text">
                  {promptHasInlineAnswer
                    ? renderPromptWithAnswer()
                    : renderMultiline(cleanedText)}
                </div>
              )}
              <div
                className={`fb-row-text${useInlineFlow ? " fb-row-text--inline" : ""}`}
                ref={(el) => {
                  rowTextRefs.current[idx] = el;
                }}
              >
                {useSchemaV2 ? (
                  (() => {
                    const shouldShowThaiLine =
                      contentLang === "th" &&
                      typeof item.text_th === "string" &&
                      item.text_th.trim();
                    const nodes = [];
                    let insertedThaiLine = false;
                    const shouldInsertThaiAfterFirstBreak =
                      shouldShowThaiLine && hasBilingualAbPrompt;
                    const allowInlineThaiInsertion =
                      !isInlineSingleBlank || shouldStackThaiAboveLongBlank;
                    const pushThaiLine = () => {
                      if (
                        shouldInsertThaiAfterFirstBreak ||
                        !allowInlineThaiInsertion ||
                        !shouldShowThaiLine ||
                        insertedThaiLine
                      )
                        return;
                      nodes.push(
                        <span
                          key={`th-break-before-${idx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );
                      nodes.push(
                        <span key={`th-line-${idx}`} className="fb-row-th fb-row-th--inline">
                          <InlineText
                            inlines={questionInlinesTh}
                            text={item.text_th.trim()}
                          />
                        </span>
                      );
                      nodes.push(
                        <span
                          key={`th-break-after-${idx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );
                      insertedThaiLine = true;
                    };

                    const styledCursor = styledRuns?.length
                      ? { runs: styledRuns, index: 0, offset: 0, disabled: false }
                      : null;
                    item.stem.blocks.forEach((block, blockIdx) => {
                      if (block?.type !== "inline" || !Array.isArray(block.tokens)) {
                        return;
                      }
                      block.tokens.forEach((token, tokenIdx) => {
                        if (token.type === "text") {
                          if (styledCursor) {
                            const styledNodes = renderTokenWithStyles(
                              token.text,
                              styledCursor,
                              `v2-text-${idx}-${blockIdx}-${tokenIdx}`
                            );
                            if (styledNodes) {
                              nodes.push(...styledNodes);
                            }
                          } else {
                            nodes.push(
                              <span
                                key={`v2-text-${idx}-${blockIdx}-${tokenIdx}`}
                                className="fb-text-block"
                              >
                                {token.text}
                              </span>
                            );
                          }
                          return;
                        }
                        if (token.type === "line_break") {
                          nodes.push(
                            <span
                              key={`v2-break-${idx}-${blockIdx}-${tokenIdx}`}
                              className="fb-line-break"
                              aria-hidden="true"
                            />
                          );
                          if (shouldInsertThaiAfterFirstBreak && !insertedThaiLine) {
                            nodes.push(
                              <span key={`th-line-${idx}`} className="fb-row-th fb-row-th--inline">
                                <InlineText
                                  inlines={questionInlinesTh}
                                  text={item.text_th.trim()}
                                />
                              </span>
                            );
                            nodes.push(
                              <span
                                key={`th-break-after-${idx}`}
                                className="fb-line-break"
                                aria-hidden="true"
                              />
                            );
                            insertedThaiLine = true;
                          }
                          return;
                        }
                        if (token.type === "blank") {
                          const blankId = token.id;
                          const blankMeta = Array.isArray(item.blanks)
                            ? item.blanks.find((blank) => blank.id === blankId)
                            : null;
                          const blankLength = blankMeta?.min_len || 1;
                          const blankAnswers = Array.isArray(item.answers_v2)
                            ? item.answers_v2[item.blanks.findIndex((blank) => blank.id === blankId)] || []
                            : [];
                          const maxAnswerLen = blankAnswers.reduce(
                            (maxLen, answer) =>
                              Math.max(maxLen, normalizeWhitespace(answer).length),
                            0
                          );
                          const isShortBlank =
                            (maxAnswerLen > 0 && maxAnswerLen <= 10) ||
                            (maxAnswerLen === 0 && blankLength <= 4);
                          const minWidthCh = isShortBlank
                            ? 8
                            : Math.max(12, 3 + blankLength * 2);
                          pushThaiLine();
                          nodes.push(
                            <span
                              key={`v2-blank-${idx}-${blockIdx}-${tokenIdx}`}
                              className={`fb-input-wrap${isShortBlank ? " fb-input-wrap--short" : " fb-input-wrap--long"}`}
                            >
                              <input
                                type="text"
                                className={`fb-input${isShortBlank ? " fb-input--short" : " fb-input--long"}`}
                                value={questionState.answersByBlank?.[blankId] || ""}
                                onChange={(event) =>
                                  handleBlankAnswerChange(idx, blankId, event.target.value, item)
                                }
                                disabled={disabled}
                                placeholder=""
                                style={{
                                  minWidth: `${minWidthCh}ch`,
                                }}
                              />
                              <InlineStatus state={questionState} />
                            </span>
                          );
                        }
                      });
                    });

                    if (
                      isInlineSingleBlank &&
                      shouldShowThaiLine &&
                      !shouldStackThaiAboveLongBlank
                    ) {
                      nodes.push(
                        <span
                          key={`th-break-inline-${idx}`}
                          className="fb-line-break"
                          aria-hidden="true"
                        />
                      );
                      nodes.push(
                        <span key={`th-line-inline-${idx}`} className="fb-row-th fb-row-th--inline">
                          <InlineText
                            inlines={questionInlinesTh}
                            text={item.text_th.trim()}
                          />
                        </span>
                      );
                    }

                    return nodes;
                  })()
                ) : (
                  (() => {
                    const shouldShowThaiLine =
                      contentLang === "th" &&
                      typeof item.text_th === "string" &&
                      item.text_th.trim() &&
                      !hasBilingualAbPrompt;
                  let insertedThaiLine = false;
                  const pushThaiLine = () => {
                    if (!shouldShowThaiLine || insertedThaiLine) return;
                    nodes.push(
                      <span
                        key={`th-break-before-${idx}`}
                        className="fb-line-break"
                        aria-hidden="true"
                      />
                    );
                    nodes.push(
                      <span key={`th-line-${idx}`} className="fb-row-th fb-row-th--inline">
                        <InlineText
                          inlines={questionInlinesTh}
                          text={item.text_th.trim()}
                        />
                      </span>
                    );
                    nodes.push(
                      <span
                        key={`th-break-after-${idx}`}
                        className="fb-line-break"
                        aria-hidden="true"
                      />
                    );
                    insertedThaiLine = true;
                  };

                  if (hasBilingualAbPrompt) {
                    const lines = item.text.split("\n");
                    const aLine =
                      lines.find((line) => line.trim().startsWith("A:")) || lines[0];
                    const bLine =
                      lines.find((line) => line.trim().startsWith("B:")) ||
                      lines[lines.length - 1];
                    const thaiLine = item.text_th.trim();
                    const nodes = [];
                    nodes.push(
                      <React.Fragment key={`ab-a-${idx}`}>
                        {renderMultiline(aLine)}
                      </React.Fragment>
                    );
                    nodes.push(
                      <span
                        key={`ab-a-break-${idx}`}
                        className="fb-line-break"
                        aria-hidden="true"
                      />
                    );
                    nodes.push(
                      <React.Fragment key={`ab-th-${idx}`}>
                        {renderMultiline(thaiLine)}
                      </React.Fragment>
                    );
                    nodes.push(
                      <span
                        key={`ab-th-break-${idx}`}
                        className="fb-line-break"
                        aria-hidden="true"
                      />
                    );

                    const underscoreMatch = bLine.match(/_{2,}/);
                    if (underscoreMatch) {
                      const before = bLine.slice(0, underscoreMatch.index);
                      const trimmedBefore = before.replace(/\s+$/, "");
                      const hadTrailingSpace = /\s+$/.test(before);
                      if (trimmedBefore) {
                        nodes.push(
                          <React.Fragment key={`ab-b-before-${idx}`}>
                            {renderMultiline(trimmedBefore)}
                          </React.Fragment>
                        );
                        if (hadTrailingSpace) {
                          nodes.push(" ");
                        }
                      }
                    } else {
                      nodes.push(
                        <React.Fragment key={`ab-b-${idx}`}>
                          {renderMultiline(bLine)}
                        </React.Fragment>
                      );
                      nodes.push(" ");
                    }

                    const inputMinWidthCh = isShortAnswer ? 8 : 12;
                    nodes.push(
                      <span
                        key={`ab-input-${idx}`}
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
                      </span>
                    );

                    if (underscoreMatch) {
                      const after = bLine.slice(
                        underscoreMatch.index + underscoreMatch[0].length
                      );
                      if (after) {
                        nodes.push(
                          <React.Fragment key={`ab-b-after-${idx}`}>
                            {renderMultiline(after)}
                          </React.Fragment>
                        );
                      }
                    }
                    return nodes;
                  }

                  const nodes = [];
                  for (let segmentIdx = 0; segmentIdx < segmentsToRender.length; segmentIdx += 1) {
                    const segment = segmentsToRender[segmentIdx];
                    if (segment.type === "text") {
                      const next = segmentsToRender[segmentIdx + 1];
                      const nextNext = segmentsToRender[segmentIdx + 2];
                      const canInline =
                        next?.type === "blank" &&
                        nextNext?.type === "text" &&
                        !segment.content?.includes("\n") &&
                        !nextNext.content?.includes("\n");
                      const answerLength = (item?.answer || "").trim().length;
                      const isShortAnswer = answerLength > 0 && answerLength <= 10;
                      const renderText = segment.style
                        ? renderStyledText(segment.content, segment.style)
                        : renderMultiline(segment.content);

                      if (canInline && isShortAnswer) {
                        const blankLength = next.length || 1;
                        const inputMinWidthCh = 8;
                        nodes.push(
                          <span key={`inline-${idx}-${segmentIdx}`} className="fb-inline-flow">
                            {renderText}
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
                            {nextNext?.style
                              ? renderStyledText(nextNext.content, nextNext.style)
                              : renderMultiline(nextNext?.content)}
                          </span>
                        );
                        segmentIdx += 2;
                        continue;
                      }

                      nodes.push(
                        <React.Fragment key={`text-${idx}-${segmentIdx}`}>
                          {renderText}
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
                    const isShortAnswer = answerLength > 0 && answerLength <= 10;
                    const inputMinWidthCh = isShortAnswer ? 8 : minWidthCh;
                    pushThaiLine();
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

                  if (!hasBlank && !promptHasInlineAnswer && !hasBilingualAbPrompt) {
                    const inputMinWidthCh = isShortAnswer ? 8 : 12;
                    pushThaiLine();
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
                })()
                )}
              </div>

              <QuestionFeedback state={questionState} />
            </div>
          </div>
        </div>
        </React.Fragment>
      );
    });

  const langClass = contentLang === "th" ? " fb-lang-th" : "";

  return (
    <div className={`fb-wrap${langClass}`}>
      {/* {title && showTitle && <h3 className="fb-title">{title}</h3>} */}
      {renderPromptBlocks()}

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

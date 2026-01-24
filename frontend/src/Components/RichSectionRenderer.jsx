import React, { useCallback, useEffect, useRef, useState } from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
import AudioButton from "./AudioButton";
import LessonTable from "./LessonTable";
import CollapsibleDetails from "./CollapsibleDetails";

// Helper function to clean audio tags from text - FIXED to handle [audio:...] format
function cleanAudioTags(text) {
  if (!text || typeof text !== 'string') return text;
  // Replace [audio:...] tags with a space, then clean up spacing without collapsing newlines
  return text
    .replace(/\[audio:[^\]]+\]/g, ' ')
    .replace(/[^\S\r\n]+/g, ' ')   // collapse spaces/tabs but keep newlines
    .replace(/\s*\n\s*/g, '\n');   // trim stray spaces around newlines
}

export default function RichSectionRenderer({
  nodes,
  snipIdx,
  phrasesSnipIdx,
  phraseId,
  phraseVariant = 0,
  isPhrasesSection = false,
  uiLang = "en",
  renderQuickPractice,
  images,
  noAccordion = false,
  suppressBaseOffset = false,
  accordionResetKey,
}) {
  const nodesList = Array.isArray(nodes) ? nodes : [];
  const [preloadBySection, setPreloadBySection] = useState({});
  const preloadTimersRef = useRef({});

  const setPreloadForSection = useCallback((sectionKey, value) => {
    setPreloadBySection((prev) => {
      if (prev[sectionKey] === value) return prev;
      return { ...prev, [sectionKey]: value };
    });
  }, []);

  const handleSectionToggle = useCallback(
    (sectionKey, isOpen) => {
      if (preloadTimersRef.current[sectionKey]) {
        clearTimeout(preloadTimersRef.current[sectionKey]);
        delete preloadTimersRef.current[sectionKey];
      }

      if (isOpen) {
        preloadTimersRef.current[sectionKey] = setTimeout(() => {
          setPreloadForSection(sectionKey, true);
        }, 150);
      } else {
        setPreloadForSection(sectionKey, false);
      }
    },
    [setPreloadForSection]
  );

  useEffect(() => {
    Object.values(preloadTimersRef.current).forEach(clearTimeout);
    preloadTimersRef.current = {};
    setPreloadBySection({});
  }, [accordionResetKey]);

  console.log("RichSectionRenderer input nodes:", nodesList.map((n, i) => ({
  index: i,
  kind: n.kind,
  text: n.inlines?.[0]?.text?.substring(0, 30),
  audio_seq: n.audio_seq
})));

  const isSubheaderNode = (node) => {
    if (node?.kind !== "paragraph") return false;
    if (node?.audio_key || node?.audio_seq) return false;
    const textSpans = (node.inlines || []).filter(
      (span) => typeof span?.text === "string" && span.text.trim() !== ""
    );
    return textSpans.length > 0 && textSpans.every((span) => !!span.bold);
  };

  const groupBySubheader = (nodeList) => {
    const groups = [];
    let current = [];
    nodeList.forEach((node) => {
      if (isSubheaderNode(node) && current.length) {
        groups.push(current);
        current = [];
      }
      current.push(node);
    });
    if (current.length) {
      groups.push(current);
    }
    return groups;
  };

const TH_RE = /[\u0E00-\u0E7F]/;
const TH_PUNCT_ONLY_RE = /^[.,!?;:'"(){}[\]<>\/\\\-–—…]+$/;
const SPEAKER_PREFIX_RE = /^\s*((?:[A-Za-z][^:[\n]{0,40}|[\u0E00-\u0E7F][^:[\n]{0,40}):\s*)/;
const INLINE_MARKER_RE = /(\[X\]|\[✓\]|\[-\])/g;
const INLINE_MARKER_COLORS = {
  "[X]": "#FD6969",
  "[✓]": "#3CA0FE",
  "[-]": "#28A265",
};

const isSpeakerLineText = (text) => {
  if (!text) return false;
  const colonIdx = text.indexOf(":");
  const bracketIdx = text.indexOf("[");
  const hasBracketBeforeColon = bracketIdx >= 0 && (colonIdx < 0 || bracketIdx < colonIdx);
  if (hasBracketBeforeColon) return false;
  return SPEAKER_PREFIX_RE.test(text);
};

const isEnglishSpeakerLineText = (text) => {
  if (!isSpeakerLineText(text)) return false;
  const trimmed = text.trimStart();
  return /^[A-Za-z]/.test(trimmed);
};

const speakerLineIsThai = (line) => {
  if (!isSpeakerLineText(line)) return null;
  const match = line.match(SPEAKER_PREFIX_RE);
  if (!match) return null;
  const speaker = match[0].replace(/:\s*$/, "");
  const content = line.slice(match[0].length);
  const speakerHasThai = TH_RE.test(speaker);
  const contentHasThai = TH_RE.test(content);
  if (!speakerHasThai && !contentHasThai) return false;
  return true;
};

  // Helper for rendering inlines with proper spacing AND audio tag removal
  const renderInlines = (inlines, opts = {}) => {
    let thaiColor = opts.thaiColor || null;
    const englishColor = opts.englishColor || null;
    const normalizedInlines = [];
    (inlines || []).forEach((span) => {
      const text = span?.text || "";
      if (text.includes("\n")) {
        const parts = text.split("\n");
        parts.forEach((part, idx) => {
          if (idx > 0) {
            normalizedInlines.push({ ...span, text: "\n" });
          }
          if (part) {
            normalizedInlines.push({ ...span, text: part });
          }
        });
      } else {
        normalizedInlines.push(span);
      }
    });

    const applyThaiSpeakerPrefix = (list) => {
      const updated = [];
      let lineStart = 0;
      let idx = 0;
      while (idx <= list.length) {
        const entry = list[idx];
        const isLineBreak = !entry || entry.text === "\n";
        if (isLineBreak) {
          const lineInlines = list.slice(lineStart, idx);
          const lineText = lineInlines.map((span) => span?.text || "").join("");
          if (speakerLineIsThai(lineText)) {
            const match = lineText.match(SPEAKER_PREFIX_RE);
            if (match) {
              const prefix = match[0];
              let remaining = prefix.length;
              lineInlines.forEach((span) => {
                if (remaining <= 0) {
                  updated.push({ ...span });
                  return;
                }
                const text = span?.text || "";
                if (!text) return;
                if (text.length <= remaining) {
                  updated.push({
                    ...span,
                    text,
                    speakerWeight: opts.speakerPrefixWeight || 500,
                    speakerColor: opts.speakerPrefixColor || "#111",
                  });
                  remaining -= text.length;
                  return;
                }
                const prefixPart = text.slice(0, remaining);
                const restPart = text.slice(remaining);
                updated.push({
                  ...span,
                  text: prefixPart,
                  speakerWeight: opts.speakerPrefixWeight || 500,
                  speakerColor: opts.speakerPrefixColor || "#111",
                });
                if (restPart) {
                  updated.push({ ...span, text: restPart });
                }
                remaining = 0;
              });
              if (entry) {
                updated.push(entry);
              }
              lineStart = idx + 1;
              idx += 1;
              continue;
            }
          }
          updated.push(...lineInlines.map((span) => ({ ...span })));
          if (entry) {
            updated.push(entry);
          }
          lineStart = idx + 1;
        }
        idx += 1;
      }
      return updated;
    };

    const normalizedWithSpeaker =
      opts.speakerPrefixColor && opts.speakerPrefixWeight
        ? applyThaiSpeakerPrefix(normalizedInlines)
        : normalizedInlines;

    let thaiZoneStartIndex = -1;
    const hasLineBreak = normalizedWithSpeaker.some((span) => span?.text === "\n");

    if (hasLineBreak) {
      for (let i = 0; i < normalizedWithSpeaker.length; i += 1) {
        const text = cleanAudioTags(normalizedWithSpeaker[i]?.text || "");
        if (TH_RE.test(text)) {
          thaiZoneStartIndex = i;
          break;
        }
      }
    } else {
      for (let i = 1; i < normalizedWithSpeaker.length; i += 1) {
        const text = cleanAudioTags(normalizedWithSpeaker[i]?.text || "");
        if (!TH_RE.test(text)) continue;
        const prevText = cleanAudioTags(normalizedWithSpeaker[i - 1]?.text || "");
        if (prevText.includes("(") || TH_PUNCT_ONLY_RE.test(prevText)) {
          thaiZoneStartIndex = i - 1;
          break;
        }
      }
    }

    if (thaiZoneStartIndex > 0) {
      const prevText = cleanAudioTags(normalizedWithSpeaker[thaiZoneStartIndex - 1]?.text || "");
      if (TH_PUNCT_ONLY_RE.test(prevText)) {
        thaiZoneStartIndex -= 1;
      }
    }
    const processedInlines = normalizedWithSpeaker.map((span, idx) => {
      const cleanText = cleanAudioTags(span.text);
      let displayText = cleanText;
      const nextSpan = normalizedWithSpeaker[idx + 1];

      // Check if there's NO trailing space in the ORIGINAL text (before cleanAudioTags)
      const originalHadTrailingSpace = typeof span.text === "string" && /[ \t]+$/.test(span.text);

      const styleChangesNext =
        nextSpan &&
        (nextSpan?.underline !== span?.underline ||
          nextSpan?.bold !== span?.bold ||
          nextSpan?.italic !== span?.italic);

      // If style changes AND original had no space, suppress auto-spacing on next span
      const suppressSpaceBefore = styleChangesNext && !originalHadTrailingSpace;

      return { span, cleanText, displayText, suppressSpaceBefore };
    });

    const collapseInlineMarkers = (entries) => {
      const out = [];
      for (let i = 0; i < entries.length; i += 1) {
        const current = entries[i];
        const next = entries[i + 1];
        const next2 = entries[i + 2];
        const currentText = typeof current?.displayText === "string" ? current.displayText : "";
        const nextText = typeof next?.displayText === "string" ? next.displayText : "";
        const next2Text = typeof next2?.displayText === "string" ? next2.displayText : "";

        const isMarkerMiddle = ["X", "✓", "-", "check"].includes(nextText);
        if (currentText === "[" && isMarkerMiddle && next2Text.startsWith("]")) {
          const rest = next2Text.slice(1);
          const mergedText = `[${nextText}]${rest}`;
          out.push({
            ...current,
            cleanText: mergedText,
            displayText: mergedText,
          });
          i += 2;
          continue;
        }

        out.push(current);
      }
      return out;
    };

    const collapsedInlines = collapseInlineMarkers(processedInlines);

    const lineRanges = [];
    let lineStart = 0;
    for (let i = 0; i < collapsedInlines.length; i += 1) {
      if (collapsedInlines[i].displayText === "\n") {
        lineRanges.push({ start: lineStart, end: i - 1 });
        lineStart = i + 1;
      }
    }
    if (lineStart <= collapsedInlines.length - 1) {
      lineRanges.push({ start: lineStart, end: collapsedInlines.length - 1 });
    }

    const lineOverrides = new Map();
    lineRanges.forEach(({ start, end }) => {
      const lineText = collapsedInlines
        .slice(start, end + 1)
        .map((entry) => entry.displayText || "")
        .join("");
      const isThaiLine = speakerLineIsThai(lineText);
      if (isThaiLine === null) return;
      lineOverrides.set(start, { isThai: isThaiLine });
    });
    const hasThaiOverride = [...lineOverrides.values()].some(
      (entry) => entry.isThai === true
    );

    if (!hasLineBreak && thaiZoneStartIndex === -1 && !hasThaiOverride) {
      thaiColor = null;
    }

    return collapsedInlines.map((entry, m) => {
      const { span, displayText } = entry;
      const currentText = typeof displayText === "string" ? displayText : "";

      // Check if we need a space before this span
      let needsSpaceBefore = false;
      if (m > 0) {
        const prevEntry = collapsedInlines[m - 1];
        if (prevEntry.suppressSpaceBefore) {
          needsSpaceBefore = false;
        } else {
          const prevDisplay = prevEntry.displayText;
          const prevText = typeof prevDisplay === "string" ? prevDisplay : "";

          // Add space if previous span doesn't end with whitespace or punctuation
          // and current span doesn't start with whitespace or punctuation
          const prevEndsWithSpaceOrPunct = /[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]$/.test(prevText);
          const currentStartsWithSpaceOrPunct = /^[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]/.test(currentText);

          const prevEndsWithWordChar = /[A-Za-z0-9]$/.test(prevText);
          const currentStartsWithWordChar = /^[A-Za-z0-9]/.test(currentText);
          const hasThaiBoundary = TH_RE.test(prevText) || TH_RE.test(currentText);
          const looksLikeSplitWord = prevEndsWithWordChar && currentStartsWithWordChar;

          needsSpaceBefore =
            !hasThaiBoundary &&
            !looksLikeSplitWord &&
            !prevEndsWithSpaceOrPunct &&
            !currentStartsWithSpaceOrPunct &&
            currentText.trim();
        }
      }


      const commonStyle = {
        fontWeight: span.speakerWeight || (span.bold ? "bold" : undefined),
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        whiteSpace: "pre-line",
        // DON'T render the highlight color - it's just a spacing flag
      };

      const renderTextWithMarkers = (text, keyPrefix, opts = {}) => {
        const thaiContext = opts.thaiContext === true;
        const inThaiZone = opts.inThaiZone === true;
        const strictThaiSplit = opts.strictThaiSplit === true;
        const segments = String(text).split(INLINE_MARKER_RE).filter((part) => part !== "");
        return segments.flatMap((segment, segIdx) => {
          const markerColor = INLINE_MARKER_COLORS[segment];
          if (markerColor) {
            const markerStyle = {
              ...commonStyle,
              color: markerColor,
              fontWeight: 600,
            };
            if (span.link) {
              return (
                <a
                  key={`${keyPrefix}-marker-${segIdx}`}
                  href={span.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={markerStyle}
                >
                  {segment}
                </a>
              );
            }
            return (
              <span key={`${keyPrefix}-marker-${segIdx}`} style={markerStyle}>
                {segment}
              </span>
            );
          }

          const segmentHasThai = !!(thaiColor && (
            strictThaiSplit
              ? TH_RE.test(segment)
              : (inThaiZone || thaiContext || TH_RE.test(segment))
          ));
          const segmentParts = segmentHasThai
            ? segment.split(/([\u0E00-\u0E7F]+|[.,!?;:'"(){}[\]<>\\\/\-–—…]+)/)
            : [segment];
          let segmentOffset = 0;
          const segmentEntries = segmentParts.map((part) => {
            const entry = { part, start: segmentOffset };
            segmentOffset += part.length;
            return entry;
          });

          return segmentEntries
            .filter(({ part }) => part !== "")
            .map(({ part }, idx) => {
              const prev = segmentEntries[idx - 1]?.part || "";
              const next = segmentEntries[idx + 1]?.part || "";
              const isPunctOnly = TH_PUNCT_ONLY_RE.test(part);
              const isNumericOnly = /^\d+(?:[.,]\d+)?$/.test(part);
              const adjacentThai = TH_RE.test(prev) || TH_RE.test(next);
              const partHasThai = strictThaiSplit
                ? (TH_RE.test(part) || ((isPunctOnly || isNumericOnly) && adjacentThai))
                : (inThaiZone ||
                    TH_RE.test(part) ||
                    (segmentHasThai &&
                      (isPunctOnly || isNumericOnly) &&
                      adjacentThai));
              const style = {
                ...commonStyle,
                color:
                  span.speakerColor ||
                  (partHasThai && thaiColor
                    ? thaiColor
                    : (englishColor || undefined)),
                fontWeight:
                  partHasThai && thaiColor
                    ? (span.speakerWeight || (span.bold ? 500 : 400))
                    : commonStyle.fontWeight,
              };

              if (span.link) {
                let href = span.link;
                if (href.startsWith("https://pa.invalid/lesson/")) {
                  href = href.replace("https://pa.invalid", "");
                }
                if (href.startsWith("https://pa.invalid/topic-library/")) {
                  href = href.replace("https://pa.invalid", "");
                }

                const linkStyle = {
                  ...style,
                  color: span.underline ? "#676769" : style.color,
                };

                return (
                  <a
                    key={`${keyPrefix}-frag-${segIdx}-${idx}`}
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={linkStyle}
                  >
                    {part}
                  </a>
                );
              }

              return (
                <span key={`${keyPrefix}-frag-${segIdx}-${idx}`} style={style}>
                  {part}
                </span>
              );
            });
        });
      };

      const prevText = collapsedInlines[m - 1]?.displayText;
      const nextText = collapsedInlines[m + 1]?.displayText;
      const thaiContext = !!(thaiColor && (
        TH_RE.test(currentText) ||
        TH_RE.test(typeof prevText === "string" ? prevText : "") ||
        TH_RE.test(typeof nextText === "string" ? nextText : "")
      ));
      let inThaiZone = thaiZoneStartIndex >= 0 && m >= thaiZoneStartIndex;
      const lineOverride = lineRanges.find(({ start, end }) => m >= start && m <= end);
      if (lineOverride && lineOverrides.has(lineOverride.start)) {
        inThaiZone = lineOverrides.get(lineOverride.start).isThai;
      }
      const fragmentNodes = renderTextWithMarkers(currentText, `frag-${m}`, {
        thaiContext,
        inThaiZone,
        strictThaiSplit: opts.strictThaiSplit,
      });

      return (
        <React.Fragment key={m}>
          {needsSpaceBefore && " "}
          {fragmentNodes}
        </React.Fragment>
      );
    });
  };

  const nodeHasBold = (node) =>
    Array.isArray(node?.inlines) && node.inlines.some((span) => span?.bold);

  const CYAN_HIGHLIGHT = "#00ffff";
  const ACCENT_COLOR = "#7BE6C9";

  // Detect cyan highlights in source text
  const hasCyanHighlight = (node) =>
    Array.isArray(node?.inlines) &&
    node.inlines.some((span) => span?.highlight?.toLowerCase() === CYAN_HIGHLIGHT);

const hasLineBreak = (node) =>
  Array.isArray(node?.inlines) &&
  node.inlines.some((span) => cleanAudioTags(span.text).includes("\n"));

const DEFAULT_INDENT_PER_LEVEL = 1.5; // rem (24px / 16 = 1.5rem)
const DEFAULT_MANUAL_INDENT_REM = 3;   // rem applied to flagged paragraphs
const AUDIO_BUTTON_SIZE = 1.5; // rem
const NON_AUDIO_INDENT_BONUS_LEVELS = 2; // push non-audio indented items to align with audio bullets
const OVERRIDE_INDENT_REM = 6; // force indent=1 to 6rem for alignment

function getIndentConfig() {
  if (typeof window === "undefined") {
    return {
      indentPerLevel: DEFAULT_INDENT_PER_LEVEL,
      manualIndentRem: DEFAULT_MANUAL_INDENT_REM,
      listItemOffset: DEFAULT_INDENT_PER_LEVEL * 3, // matches legacy 4.5rem
      listItemBaseOffset: (DEFAULT_INDENT_PER_LEVEL * 4) / 3, // matches legacy ~2rem
    };
  }

  const rootStyle = getComputedStyle(document.documentElement);
  const indentPerLevel =
    parseFloat(rootStyle.getPropertyValue("--audio-indent-step")) ||
    DEFAULT_INDENT_PER_LEVEL;
  const manualIndentRem =
    parseFloat(rootStyle.getPropertyValue("--audio-manual-indent")) ||
    DEFAULT_MANUAL_INDENT_REM;

  return {
    indentPerLevel,
    manualIndentRem,
    listItemOffset: indentPerLevel * 3, // scale with indent step
    listItemBaseOffset: (indentPerLevel * 4) / 3, // keeps ~2rem baseline on desktop
  };
}

const {
  indentPerLevel: INDENT_PER_LEVEL,
  manualIndentRem: MANUAL_INDENT_REM,
  listItemOffset: LIST_ITEM_OFFSET,
  listItemBaseOffset: LIST_ITEM_BASE_OFFSET,
} = getIndentConfig();

const computeIndentLevel = (node) => {
  if (typeof node?.indent_level === "number" && Number.isFinite(node.indent_level)) {
    return node.indent_level;
  }
  if (typeof node?.indent === "number" && Number.isFinite(node.indent)) {
    return node.indent;
  }
  if (
    typeof node?.indent_first_line_level === "number" &&
    Number.isFinite(node.indent_first_line_level)
  ) {
    return node.indent_first_line_level;
  }
  return 0;
};

const calcIndentRem = (indentLevel) => {
  if (!indentLevel) return 0;
  return indentLevel * INDENT_PER_LEVEL;
};

const listTextStartRem = (indentLevel) => {
  const base = indentLevel ? calcIndentRem(indentLevel) : 0;
  const offset = indentLevel ? LIST_ITEM_OFFSET : LIST_ITEM_BASE_OFFSET;
  return base + offset;
};

  // Helper for rendering individual nodes (NON-HEADING NODES ONLY)
  const renderNode = (node, key, meta = {}, options = {}) => {
    const shouldPreload = options.preloadAudio === true;
    const audioIdentity =
      node?.audio_key ||
      (node?.audio_section != null && node?.audio_seq != null
        ? `${node.audio_section}-${node.audio_seq}`
        : null);
    const nodeKey = audioIdentity ? `${key}-audio-${audioIdentity}` : key;
    if (node.kind === "heading") {
      if (meta.allowHeading) {
        return (
          <p key={nodeKey} className="rich-subheader">
            {renderInlines(node.inlines)}
          </p>
        );
      }
      return null;
    }
    if (isPhrasesSection && Array.isArray(node.inlines) && node.inlines.length) {
      const firstLineText = (node.inlines || [])
        .map((span) => span?.text || "")
        .join("")
        .split("\n")[0];
      const match = isSpeakerLineText(firstLineText)
        ? firstLineText.match(SPEAKER_PREFIX_RE)
        : null;
      if (match) {
        const prefix = match[0];
        const prefixLen = prefix.length;
        let consumed = 0;
        let speakerSpan = null;
        const newInlines = [];

        node.inlines.forEach((span) => {
          if (consumed >= prefixLen) {
            newInlines.push({ ...span });
            return;
          }
          const text = span?.text || "";
          if (!text) {
            return;
          }
          const remaining = prefixLen - consumed;
          if (text.length <= remaining) {
            if (!speakerSpan) {
              speakerSpan = {
                ...span,
                text,
                bold: false,
                speakerWeight: 500,
                speakerColor: "#111",
              };
            } else {
              speakerSpan.text += text;
            }
            consumed += text.length;
            return;
          }

          const prefixPart = text.slice(0, remaining);
          const restPart = text.slice(remaining);
          if (!speakerSpan) {
            speakerSpan = {
              ...span,
              text: prefixPart,
              bold: false,
              speakerWeight: 500,
              speakerColor: "#111",
            };
          } else {
            speakerSpan.text += prefixPart;
          }
          consumed += remaining;
          if (restPart) {
            newInlines.push({ ...span, text: restPart });
          }
        });

        if (speakerSpan) {
          node = {
            ...node,
            inlines: [speakerSpan, ...newInlines],
          };
          node = { ...node, _isSpeakerLine: true };
        }
      }
    }
    const phraseThaiOpts = isPhrasesSection
      ? {
          thaiColor: "#8C8D93",
          englishColor: "#1e1e1e",
          speakerPrefixColor: "#111",
          speakerPrefixWeight: 500,
          strictThaiSplit: true,
        }
      : undefined;
    const audioThaiOpts = isPhrasesSection
      ? phraseThaiOpts
      : { thaiColor: "#8C8D93" };
    if (isPhrasesSection) {
      const rawText = (node.inlines || []).map((s) => s.text || "").join("");
      if (rawText.toLowerCase().includes("link xx")) {
        return null;
      }
    }

  const indentLevel = computeIndentLevel(node);
  const baseIndentRem = indentLevel * INDENT_PER_LEVEL;
  const visualIndentRem = baseIndentRem;

  if (node.kind === "image") {
    const src =
      node.image_url ||
      (node.image_key && images ? images[node.image_key] : null) ||
      (node.image_key ? `/api/images/${encodeURIComponent(node.image_key)}` : null);
    if (!src) {
      return null;
    }
    return (
      <RichImage
        key={key}
        src={src}
        altText={node.alt_text}
      />
    );
  }

  if (node.kind === "paragraph"){
    console.log("Processing paragraph node:", {
      kind: node.kind,
      audio_key: node.audio_key,
      audio_seq: node.audio_seq,
        text: node.inlines?.[0]?.text?.substring(0, 50)
      });

      // Check for audio_key first, then fallback to audio_seq
      const hasAudio = node.audio_key || node.audio_seq;
      const showDivider = isPhrasesSection && meta.showDivider;
      const boldPhrase = isPhrasesSection && meta.boldPhrase;
      const hasBold = nodeHasBold(node);
      const hasAccent = (!isPhrasesSection && hasCyanHighlight(node)) || node?.is_response;
      const textSpans = (node.inlines || []).filter(
        (span) => typeof span?.text === "string" && span.text.trim() !== ""
      );
      const allTextBold = textSpans.length > 0 && textSpans.every((span) => !!span.bold);
      const isSubheader = !hasAudio && allTextBold;
      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <div key={nodeKey} className="phrases-audio-block">
            {showDivider && <div className="phrases-divider" aria-hidden="true" />}
            <p
              className={`audio-bullet${hasAccent ? " rich-accent" : ""}`}
              style={{
                marginLeft: visualIndentRem ? `${visualIndentRem}rem` : undefined,
                display: "flex",
                alignItems: multiline ? "flex-start" : "center",
                marginTop: isPhrasesSection ? "1rem" : undefined,
                marginBottom: isPhrasesSection ? 0 : (hasBold ? 0 : "0.5rem"),
                borderLeft: hasAccent ? `0.25rem solid ${ACCENT_COLOR}` : undefined,
                paddingLeft: hasAccent ? "1rem" : undefined,
              }}
            >
              <AudioButton
                audioKey={node.audio_key}
                node={node}
                audioIndex={snipIdx}
                phrasesSnipIdx={phrasesSnipIdx}
                phraseId={phraseId}
                phraseVariant={phraseVariant}
                preload={shouldPreload}
                size={AUDIO_BUTTON_SIZE}
                className="select-none"
              />
              <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
                {renderInlines(node.inlines, audioThaiOpts)}
              </span>
            </p>
          </div>
        );
      }

      const isIndented = indentLevel > 0 || node?.is_indented === true;
      const shouldSuppressBaseOffset = suppressBaseOffset && !indentLevel && !hasAudio;
      const baseOffsetRem =
        shouldSuppressBaseOffset || !isIndented ? 0 : LIST_ITEM_BASE_OFFSET;
      const paragraphMarginLeft = shouldSuppressBaseOffset
        ? undefined
        : (indentLevel
            ? `${listTextStartRem(indentLevel)}rem`
            : `${baseOffsetRem}rem`);
      return (
        <p
          key={nodeKey}
          className={`${isSubheader ? "rich-subheader" : ""}${hasAccent ? " rich-accent" : ""}`}
          style={{
            marginLeft: hasAudio
              ? (visualIndentRem ? `${visualIndentRem}rem` : undefined)
              : paragraphMarginLeft,
            marginTop: isPhrasesSection && meta.speakerSpacing ? "0.3rem" : undefined,
            marginBottom: isSubheader ? "1rem" : (hasBold ? 0 : undefined),
            borderLeft: hasAccent ? `0.25rem solid ${ACCENT_COLOR}` : undefined,
            paddingLeft: hasAccent ? "1rem" : undefined,
          }}
        >
          {renderInlines(node.inlines, phraseThaiOpts)}
        </p>
      );
    }

    if (node.kind === "list_item") {
      console.log("Processing list_item node:", {
        kind: node.kind,
        audio_key: node.audio_key,
        audio_seq: node.audio_seq,
        text: node.inlines?.[0]?.text?.substring(0, 50)
      });

      // Check for audio_key first, then fallback to audio_seq
      const hasAudio = node.audio_key || node.audio_seq;
      const hasBold = nodeHasBold(node);
    if (hasAudio) {
      const showDivider = isPhrasesSection && meta.showDivider;
      const boldPhrase = isPhrasesSection && meta.boldPhrase;
      const multiline = hasLineBreak(node);
      return (
        <div key={nodeKey} className="phrases-audio-block">
          {showDivider && <div className="phrases-divider" aria-hidden="true" />}
          <li
              className="audio-bullet"
              style={{
                marginLeft: baseIndentRem
                  ? `${baseIndentRem + LIST_ITEM_OFFSET}rem`
                  : `${LIST_ITEM_BASE_OFFSET}rem`,
                display: "flex",
                alignItems: multiline ? "flex-start" : "flex-start",
                marginTop: isPhrasesSection ? "1rem" : undefined,
                marginBottom: isPhrasesSection ? 0 : (hasBold ? 0 : "0.5rem"),
              }}
            >
            <AudioButton
              audioKey={node.audio_key}
              node={node}
              audioIndex={snipIdx}
              phrasesSnipIdx={phrasesSnipIdx}
              phraseId={phraseId}
              phraseVariant={phraseVariant}
              preload={shouldPreload}
              size={AUDIO_BUTTON_SIZE}
              className="select-none"
            />
            <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
              {renderInlines(node.inlines, audioThaiOpts)}
            </span>
          </li>
        </div>
      );
    }
    return (
          <li
            key={nodeKey}
            style={{
              marginLeft: indentLevel
                ? `${listTextStartRem(indentLevel) + 3}rem`
                : undefined,
              marginTop: isPhrasesSection && meta.speakerSpacing ? "0.3rem" : undefined,
              marginBottom: nodeHasBold(node) ? 0 : undefined,
            }}
          >
            {renderInlines(node.inlines, phraseThaiOpts)}
          </li>
      );
    }
    if (node.kind === "misc_item") {
      console.log("Processing misc_item node:", {
        kind: node.kind,
        audio_key: node.audio_key,
        audio_seq: node.audio_seq,
        text: node.inlines?.[0]?.text?.substring(0, 50)
      });

      // Check for audio_key first, then fallback to audio_seq
      const hasAudio = node.audio_key || node.audio_seq;
      const hasBold = nodeHasBold(node);
      if (hasAudio) {
        const showDivider = isPhrasesSection && meta.showDivider;
        const boldPhrase = isPhrasesSection && meta.boldPhrase;
        const multiline = hasLineBreak(node);
        return (
          <div key={nodeKey} className="phrases-audio-block">
            {showDivider && <div className="phrases-divider" aria-hidden="true" />}
            <div
              className="audio-bullet"
              style={{
                marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
                display: "flex",
                alignItems: multiline ? "flex-start" : "center",
                marginTop: isPhrasesSection ? "1rem" : undefined,
                marginBottom: isPhrasesSection ? 0 : (hasBold ? 0 : "0.5rem"),
              }}
            >
            <AudioButton
              audioKey={node.audio_key}
              node={node}
              audioIndex={snipIdx}
              phrasesSnipIdx={phrasesSnipIdx}
              phraseId={phraseId}
              phraseVariant={phraseVariant}
              preload={shouldPreload}
              size={AUDIO_BUTTON_SIZE}
              className="select-none"
            />
            <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
              {renderInlines(node.inlines, audioThaiOpts)}
            </span>
          </div>
          </div>
      );
    }
      return (
        <div
          key={nodeKey}
          style={{
            marginLeft: indentLevel
              ? `${listTextStartRem(indentLevel) + 3}rem`
              : undefined,
            marginTop: isPhrasesSection && meta.speakerSpacing ? "0.3rem" : undefined,
            marginBottom: nodeHasBold(node) ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines, phraseThaiOpts)}
        </div>
      );
    }

  if (node.kind === "numbered_item") {
    // This should be handled by renderNodesWithNumberedLists
    return null;
  }

  if (node.kind === "spacer") {
    return <div key={nodeKey} className="para-spacer" aria-hidden="true" />;
  }

  if (node.kind === "table") {
    const tableVisibility = typeof node.table_visibility === "string"
      ? node.table_visibility
      : (
        typeof node.table_label === "string" && /-M:?\s*$/i.test(node.table_label)
          ? "mobile"
          : "all"
      );

    return (
      <LessonTable
        key={nodeKey}
        data={{
            cells: node.cells,
            indent: node.indent,
          }}
          snipIdx={snipIdx}
          phrasesSnipIdx={phrasesSnipIdx}
          phraseId={phraseId}
          phraseVariant={phraseVariant}
          tableVisibility={tableVisibility}
        />
      );
    }

    // Handle Quick Practice exercises
    if (node.kind === "quick_practice_exercise" && renderQuickPractice) {
      return (
        <div key={nodeKey} className="quick-practice-inline">
          {renderQuickPractice(node.exercise)}
        </div>
      );
    }

    return null;
  };

  const renderNumberedListItem = (node, key, groupIndent, options = {}) => {
    const shouldPreload = options.preloadAudio === true;
    const hasAudio = node.audio_key || node.audio_seq;
    const hasBold = nodeHasBold(node);
    const multiline = hasLineBreak(node);
    const baseIndent = computeIndentLevel(node);
    const extraIndent = baseIndent - groupIndent;
    const extraIndentRem = extraIndent * INDENT_PER_LEVEL;
    const phraseThaiOpts = isPhrasesSection
      ? { thaiColor: "#8C8D93", englishColor: "#1e1e1e" }
      : undefined;
    const audioThaiOpts = isPhrasesSection
      ? phraseThaiOpts
      : { thaiColor: "#8C8D93" };

    const audioIdentity =
      node?.audio_key ||
      (node?.audio_section != null && node?.audio_seq != null
        ? `${node.audio_section}-${node.audio_seq}`
        : null);
    const nodeKey = audioIdentity ? `${key}-audio-${audioIdentity}` : key;

    if (hasAudio) {
      return (
        <li
          key={nodeKey}
          className="audio-bullet"
          style={{
            marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
            display: "flex",
            alignItems: multiline ? "flex-start" : "flex-start",
            marginBottom: hasBold ? 0 : "0.5rem",
          }}
        >
          <AudioButton
            audioKey={node.audio_key}
            node={node}
            audioIndex={snipIdx}
            phrasesSnipIdx={phrasesSnipIdx}
            phraseId={phraseId}
            phraseVariant={phraseVariant}
            preload={shouldPreload}
            size={AUDIO_BUTTON_SIZE}
            className="select-none"
          />
          <span>{renderInlines(node.inlines, audioThaiOpts)}</span>
        </li>
      );
    }

    return (
      <li
        key={nodeKey}
        style={{
          marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
          marginBottom: hasBold ? 0 : undefined,
        }}
      >
        {renderInlines(node.inlines, phraseThaiOpts)}
      </li>
    );
  };

  const renderNodesWithNumberedLists = (nodeList, options = {}) => {
    const elements = [];
    const countsByIndent = new Map();
    let phrasesAudioSeen = 0;
    let speakerSeenAfterAudio = 0;
    const allowHeadings = options.allowHeadings === true;

    const resetCounters = () => {
      countsByIndent.clear();
      speakerSeenAfterAudio = 0;
    };

    const renderNumberedItemWithCounter = (node, key) => {
      const indent = computeIndentLevel(node);
      const current = countsByIndent.has(indent) ? countsByIndent.get(indent) : 1;
      countsByIndent.set(indent, current + 1);
      const listIndentRem = indent * INDENT_PER_LEVEL;
      return (
        <ol
          key={key}
          className="rich-numbered-list"
          style={{ marginLeft: listIndentRem ? `${listIndentRem}rem` : undefined }}
          start={current}
        >
          {renderNumberedListItem(node, `${key}-item`, indent, options)}
        </ol>
      );
    };

    nodeList.forEach((node, idx) => {
      if (node.kind === "heading" || isSubheaderNode(node)) {
        resetCounters();
        elements.push(renderNode(node, idx, { allowHeading: allowHeadings }, options));
        return;
      }
      if (node.kind === "numbered_item") {
        elements.push(renderNumberedItemWithCounter(node, `numbered-${idx}`));
        return;
      }
      let meta = {};
      if (isPhrasesSection && (node.audio_key || node.audio_seq)) {
        phrasesAudioSeen += 1;
        speakerSeenAfterAudio = 0;
        meta = {
          boldPhrase: phrasesAudioSeen === 1,
          showDivider: phrasesAudioSeen === 2,
        };
      }
      const isEnglishSpeakerLine =
        isPhrasesSection &&
        Array.isArray(node.inlines) &&
        isEnglishSpeakerLineText(node.inlines[0]?.text || "");
      if (isEnglishSpeakerLine) {
        speakerSeenAfterAudio += 1;
        if (speakerSeenAfterAudio > 1) {
          meta.speakerSpacing = true;
        }
      }
      if (isPhrasesSection && phrasesAudioSeen === 1 && node.kind === "paragraph") {
        meta.keepThaiBlack = true;
      }
      elements.push(
        renderNode(node, idx, allowHeadings ? { ...meta, allowHeading: true } : meta, options)
      );
    });

    return elements;
  };

  const renderZebraGroups = (nodeList, startIndex = 0, options = {}) => {
    const groups = groupBySubheader(nodeList);
    return groups.map((group, idx) => (
      <div
        key={`zebra-group-${startIndex + idx}`}
        className={`rich-zebra rich-zebra-${(startIndex + idx) % 2}`}
      >
        {renderNodesWithNumberedLists(group, options)}
      </div>
    ));
  };

  // Group nodes by heading (for accordion/dropdown)
  const sections = [];
  let current = null;

  nodesList.forEach((node, idx) => {
    if (node.kind === "heading") {
      // Clean the heading text by trimming whitespace and tabs
      const headingText = node.inlines
        .map((s) => s.text)
        .join("")
        .replace(/\s+/g, " ")
        .trim()

      // Create a unique key for this heading based on text and position
      const headingKey = `${headingText}-${idx}`;

      // Close current section and start new one
      if (current) sections.push(current);
      current = {
        heading: node,
        body: [],
        key: headingKey
      };
    } else if (current) {
      current.body.push(node);
    } else {
      // Handle nodes before any heading
      if (!current) {
        current = {
          heading: null,
          body: [node],
          key: `no-heading-${idx}`
        };
      }
    }
  });

  // Add the final section
  if (current) {
    sections.push(current);
  }

  // If we have sections with headings, render as accordion
  const hasHeadings = sections.some(sec => sec.heading);
  const firstAccordionIndex = hasHeadings
    ? sections.findIndex((sec) => sec.heading)
    : -1;

  useEffect(() => {
    if (noAccordion || !hasHeadings || firstAccordionIndex < 0) return;
    const defaultKey = `${accordionResetKey ?? "section"}-${firstAccordionIndex}`;
    handleSectionToggle(defaultKey, true);
  }, [accordionResetKey, firstAccordionIndex, handleSectionToggle, hasHeadings, noAccordion]);

  if (nodesList.length === 0) return null;

  if (noAccordion) {
    return (
      <div className="markdown-section">
        <div className="markdown-content">
          {renderZebraGroups(nodesList, 0, { allowHeadings: true })}
        </div>
      </div>
    );
  }

  if (hasHeadings) {
    const getCleanHeadingText = (headingNode) => {
      if (!headingNode) return "";
      return headingNode.inlines
        .map((s) => s.text)
        .join("")
        .trim()
        .replace(/^\t+/, "");
    };

    const isLessonFocusHeading = (headingNode) => {
      const cleanHeadingText = getCleanHeadingText(headingNode);
      const normalizedHeading = cleanHeadingText.trim().toLowerCase();
      const lessonFocusMarkers = [
        "lesson focus",
        "จุดเน้นบทเรียน",
        "หัวข้อสำคัญของบทเรียน",
        "โฟกัสบทเรียน",
        "ประเด็นหลักของบทเรียน",
      ];
      return lessonFocusMarkers.some((marker) =>
        normalizedHeading.includes(marker)
      );
    };

    return (
      <div className="markdown-section">
        {sections.map((sec, i) => {
          // If section has no heading, render content directly
          if (!sec.heading) {
            console.log("Rendering no-heading section:", sec.key, "with", sec.body.length, "items");
            const nextSection = sections[i + 1];
            const shouldHideSpacer = isLessonFocusHeading(nextSection?.heading);
            const trimTrailingSpacers = (nodes) => {
              const trimmed = [...nodes];
              while (trimmed.length && trimmed[trimmed.length - 1]?.kind === "spacer") {
                trimmed.pop();
              }
              return trimmed;
            };
            let filteredBody = sec.body;
            if (shouldHideSpacer) {
              filteredBody = filteredBody.filter((node) => node.kind !== "spacer");
            } else if (nextSection?.heading) {
              filteredBody = trimTrailingSpacers(filteredBody);
            }

            if (!filteredBody.length) {
              return null;
            }
            return (
              <div key={sec.key} className="markdown-content no-heading">
                {renderNodesWithNumberedLists(filteredBody)}
              </div>
            );
          }

          // Clean the heading text for display
          const cleanHeadingText = getCleanHeadingText(sec.heading);

          console.log("Rendering accordion section:", cleanHeadingText);
          const isLessonFocus = isLessonFocusHeading(sec.heading);
          const sectionBody = sec.body?.[0]?.kind === "spacer" ? sec.body.slice(1) : sec.body;

          // Render as accordion section
          const sectionKey = `${accordionResetKey ?? "section"}-${i}`;
          const shouldPreload = preloadBySection[sectionKey] === true;
          return (
            <CollapsibleDetails
              key={sectionKey}
              className={`markdown-item${isLessonFocus ? " markdown-item-focus" : ""}`}
              defaultOpen={i === firstAccordionIndex}
              resetKey={accordionResetKey}
              summaryContent={cleanHeadingText}
              onToggle={(isOpen) => handleSectionToggle(sectionKey, isOpen)}
            >
              <div className="markdown-content">
                {renderZebraGroups(sectionBody, 0, { preloadAudio: shouldPreload })}
              </div>
            </CollapsibleDetails>
          );
        })}
      </div>
    );
  }

  // Fallback: render all nodes directly (no accordion)
  return (
    <div className="markdown-section">
      <div className="markdown-content">
        {renderZebraGroups(nodesList, 0)}
      </div>
    </div>
  );
}
function RichImage({ src, altText }) {
  const [showAlt, setShowAlt] = useState(false);

  const handleContextMenu = (e) => {
    e.preventDefault();
    if (!altText) return;
    setShowAlt((prev) => !prev);
  };

  return (
    <div
      style={{
        margin: "1.5rem 0",
        textAlign: "center",
      }}
      onContextMenu={handleContextMenu}
    >
      <img
        src={src}
        alt={altText || "Lesson image"}
        style={{
          maxWidth: "min(100%, 550px)",
          height: "auto",
          borderRadius: "0.5rem",
          cursor: altText ? "context-menu" : "default",
        }}
      />
      {showAlt && altText && (
        <p
          style={{
            fontSize: "0.9rem",
            color: "#4b5563",
            marginTop: "0.5rem",
            fontStyle: "italic",
          }}
        >
          {altText}
        </p>
      )}
    </div>
  );
}

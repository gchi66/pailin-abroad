import React, { useState } from "react";
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
  renderQuickPractice
}) {
  if (!Array.isArray(nodes) || nodes.length === 0) return null;

  console.log("RichSectionRenderer input nodes:", nodes.map((n, i) => ({
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
const SPEAKER_PREFIX_RE = /^\s*((?:[A-Za-z][^:\[\n]{0,40}|[\u0E00-\u0E7F][^:\[\n]{0,40}):\s*)/;

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

  // Helper for rendering inlines with proper spacing AND audio tag removal
  const renderInlines = (inlines, opts = {}) => {
    const thaiColor = opts.thaiColor || null;
    const processedInlines = inlines.map((span, idx) => {
      const cleanText = cleanAudioTags(span.text);
      let displayText = cleanText;
      const nextSpan = inlines[idx + 1];

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

    return processedInlines.map((entry, m) => {
      const { span, displayText } = entry;
      const currentText = typeof displayText === "string" ? displayText : "";

      // Check if we need a space before this span
      let needsSpaceBefore = false;
      if (m > 0) {
        const prevEntry = processedInlines[m - 1];
        if (prevEntry.suppressSpaceBefore) {
          needsSpaceBefore = false;
        } else {
          const prevDisplay = prevEntry.displayText;
          const prevText = typeof prevDisplay === "string" ? prevDisplay : "";

          // Add space if previous span doesn't end with whitespace or punctuation
          // and current span doesn't start with whitespace or punctuation
          const prevEndsWithSpaceOrPunct = /[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()\[\]{}]$/.test(prevText);
          const currentStartsWithSpaceOrPunct = /^[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()\[\]{}]/.test(currentText);

          needsSpaceBefore =
            !prevEndsWithSpaceOrPunct && !currentStartsWithSpaceOrPunct && currentText.trim();
        }
      }


      const commonStyle = {
        fontWeight: span.speakerWeight || (span.bold ? "bold" : undefined),
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        whiteSpace: "pre-line",
        // DON'T render the highlight color - it's just a spacing flag
      };

      const parts = thaiColor && TH_RE.test(currentText)
        ? currentText.split(/([\u0E00-\u0E7F]+)/)
        : [currentText];

      const fragmentNodes = parts
        .filter((part) => part !== "")
        .map((part, idx) => {
          const isThai = TH_RE.test(part);
          const style = {
            ...commonStyle,
            color: span.speakerColor || (isThai && thaiColor ? thaiColor : undefined),
            fontWeight:
              isThai && thaiColor
                ? (span.speakerWeight || (span.bold ? 500 : 400))
                : commonStyle.fontWeight,
          };

          if (span.link) {
            // Rewrite sentinel → internal lesson path
            let href = span.link;
            if (href.startsWith("https://pa.invalid/lesson/")) {
              href = href.replace("https://pa.invalid", "");
            }

            return (
              <a
                key={`frag-${m}-${idx}`}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={style}
              >
                {part}
              </a>
            );
          }

          return (
            <span key={`frag-${m}-${idx}`} style={style}>
              {part}
            </span>
          );
        });

      return (
        <React.Fragment key={m}>
          {needsSpaceBefore && " "}
          {fragmentNodes}
        </React.Fragment>
      );
    });
  };

  const getNodeText = (node) =>
    (node?.inlines || [])
      .map((span) => span?.text || "")
      .join("")
      .trim();

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

const paragraphTextStartRem = (indentLevel) => {
  const base = indentLevel ? calcIndentRem(indentLevel) : 0;
  // mimic the space the audio button consumes + gap (use base offset for consistency)
  const audioLikeOffset = LIST_ITEM_BASE_OFFSET;
  return base + audioLikeOffset;
};

  // Helper for rendering individual nodes (NON-HEADING NODES ONLY)
  const renderNode = (node, key, meta = {}) => {
    // Skip heading nodes - they should only be used for accordion structure
    if (node.kind === "heading") {
      return null;
    }
    if (isPhrasesSection && Array.isArray(node.inlines) && node.inlines[0]?.text) {
      const firstText = node.inlines[0].text;
      const match = isSpeakerLineText(firstText) ? firstText.match(SPEAKER_PREFIX_RE) : null;
      if (match) {
        const prefix = match[0];
        const rest = firstText.slice(prefix.length);
        const firstSpan = { ...node.inlines[0] };
        const speakerSpan = {
          ...firstSpan,
          text: prefix,
          bold: false,
          speakerWeight: 500,
          speakerColor: "#111",
        };
        if (rest) {
          const restSpan = { ...firstSpan, text: rest };
          node = {
            ...node,
            inlines: [speakerSpan, restSpan, ...node.inlines.slice(1).map((s) => ({ ...s }))],
          };
        } else {
          node = {
            ...node,
            inlines: [speakerSpan, ...node.inlines.slice(1).map((s) => ({ ...s }))],
          };
        }
        node = { ...node, _isSpeakerLine: true };
      }
    }
    const phraseThaiOpts = isPhrasesSection ? { thaiColor: "#8C8D93" } : undefined;
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
      const hasAccent = hasCyanHighlight(node);
      const textSpans = (node.inlines || []).filter(
        (span) => typeof span?.text === "string" && span.text.trim() !== ""
      );
      const allTextBold = textSpans.length > 0 && textSpans.every((span) => !!span.bold);
      const isSubheader = !hasAudio && allTextBold;
      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <div key={key} className="phrases-audio-block">
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
                size={AUDIO_BUTTON_SIZE}
                className="select-none"
              />
              <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
                {renderInlines(node.inlines, { thaiColor: "#8C8D93" })}
              </span>
            </p>
          </div>
        );
      }

      return (
        <p
          key={key}
          className={`${isSubheader ? "rich-subheader" : ""}${hasAccent ? " rich-accent" : ""}`}
          style={{
            marginLeft: hasAudio
              ? (visualIndentRem ? `${visualIndentRem}rem` : undefined)
              : (indentLevel
                  ? `${listTextStartRem(indentLevel)}rem`
                  : `${LIST_ITEM_BASE_OFFSET}rem`),
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
        <div key={key} className="phrases-audio-block">
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
              size={AUDIO_BUTTON_SIZE}
              className="select-none"
            />
            <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
              {renderInlines(node.inlines, { thaiColor: "#8C8D93" })}
            </span>
          </li>
        </div>
      );
    }
    return (
          <li
            key={key}
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
          <div key={key} className="phrases-audio-block">
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
              size={AUDIO_BUTTON_SIZE}
              className="select-none"
            />
            <span className={boldPhrase ? "phrases-phrase-text" : undefined}>
              {renderInlines(node.inlines, { thaiColor: "#8C8D93" })}
            </span>
          </div>
          </div>
      );
    }
      return (
        <div
          key={key}
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
    return <div key={key} className="para-spacer" aria-hidden="true" />;
  }

  if (node.kind === "table") {
    return (
      <LessonTable
        key={key}
        data={{
            cells: node.cells,
            indent: node.indent,
          }}
          snipIdx={snipIdx}
          phrasesSnipIdx={phrasesSnipIdx}
          phraseId={phraseId}
          phraseVariant={phraseVariant}
        />
      );
    }

    // Handle Quick Practice exercises
    if (node.kind === "quick_practice_exercise" && renderQuickPractice) {
      return (
        <div key={key} className="quick-practice-inline">
          {renderQuickPractice(node.exercise)}
        </div>
      );
    }

    return null;
  };

  const renderNumberedListItem = (node, key, groupIndent) => {
    const hasAudio = node.audio_key || node.audio_seq;
    const hasBold = nodeHasBold(node);
    const multiline = hasLineBreak(node);
    const baseIndent = computeIndentLevel(node);
    const extraIndent = baseIndent - groupIndent;
    const extraIndentRem = extraIndent * INDENT_PER_LEVEL;
    const phraseThaiOpts = isPhrasesSection ? { thaiColor: "#8C8D93" } : undefined;

    if (hasAudio) {
      return (
        <li
          key={key}
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
            size={AUDIO_BUTTON_SIZE}
            className="select-none"
          />
          <span>{renderInlines(node.inlines, { thaiColor: "#8C8D93" })}</span>
        </li>
      );
    }

    return (
      <li
        key={key}
        style={{
          marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
          marginBottom: hasBold ? 0 : undefined,
        }}
      >
        {renderInlines(node.inlines, phraseThaiOpts)}
      </li>
    );
  };

  const renderNumberedGroup = (items, keyPrefix) => {
    if (!items.length) return null;
    const groupIndent = computeIndentLevel(items[0]);
    const listIndentRem = groupIndent * INDENT_PER_LEVEL;

    return (
      <ol
        key={keyPrefix}
        className="rich-numbered-list"
        style={{
          marginLeft: listIndentRem ? `${listIndentRem}rem` : undefined,
        }}
      >
        {items.map((item, idx) =>
          renderNumberedListItem(item, `${keyPrefix}-item-${idx}`, groupIndent)
        )}
      </ol>
    );
  };

  const renderNodesWithNumberedLists = (nodeList) => {
    const elements = [];
    const countsByIndent = new Map();
    let phrasesAudioSeen = 0;
    let speakerSeenAfterAudio = 0;

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
          {renderNumberedListItem(node, `${key}-item`, indent)}
        </ol>
      );
    };

    nodeList.forEach((node, idx) => {
      if (node.kind === "heading" || isSubheaderNode(node)) {
        resetCounters();
        elements.push(renderNode(node, idx));
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
      elements.push(renderNode(node, idx, meta));
    });

    return elements;
  };

  const renderZebraGroups = (nodeList, startIndex = 0) => {
    const groups = groupBySubheader(nodeList);
    return groups.map((group, idx) => (
      <div
        key={`zebra-group-${startIndex + idx}`}
        className={`rich-zebra rich-zebra-${(startIndex + idx) % 2}`}
      >
        {renderNodesWithNumberedLists(group)}
      </div>
    ));
  };

  // Group nodes by heading (for accordion/dropdown)
  const sections = [];
  let current = null;

  nodes.forEach((node, idx) => {
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
      return (
        normalizedHeading.includes("lesson focus") ||
        normalizedHeading.includes("จุดเน้นบทเรียน")
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
            const filteredBody = shouldHideSpacer
              ? sec.body.filter((node) => node.kind !== "spacer")
              : sec.body;

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

          // Render as accordion section
          return (
            <CollapsibleDetails
              key={i}
              className={`markdown-item${isLessonFocus ? " markdown-item-focus" : ""}`}
              defaultOpen={i === 0}
              summaryContent={cleanHeadingText}
            >
              <div className="markdown-content">
                {renderZebraGroups(sec.body, 0)}
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
        {renderZebraGroups(nodes, 0)}
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
          maxWidth: "100%",
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

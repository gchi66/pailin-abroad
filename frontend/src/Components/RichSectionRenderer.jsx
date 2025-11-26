import React from "react";
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

  // Helper for rendering inlines with proper spacing AND audio tag removal
  const renderInlines = (inlines) => {
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
        fontWeight: span.bold ? "bold" : undefined,
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        whiteSpace: "pre-line",
        // DON'T render the highlight color - it's just a spacing flag
      };

      let element;
      if (span.link) {
        // Rewrite sentinel → internal lesson path
        let href = span.link;
        if (href.startsWith("https://pa.invalid/lesson/")) {
          href = href.replace("https://pa.invalid", "");
        }

        element = (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            style={commonStyle}
          >
            {displayText}
          </a>
        );
      } else {
        element = <span style={commonStyle}>{displayText}</span>;
      }

      return (
        <React.Fragment key={m}>
          {needsSpaceBefore && " "}
          {element}
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

  // NEW: Check if any inline in the node has yellow highlight (#ffff00)
  const hasYellowHighlight = (node) =>
    Array.isArray(node?.inlines) &&
    node.inlines.some((span) => span?.highlight?.toLowerCase() === '#ffff00');

const hasLineBreak = (node) =>
  Array.isArray(node?.inlines) &&
  node.inlines.some((span) => cleanAudioTags(span.text).includes("\n"));

const INDENT_PER_LEVEL = 1.5; // rem (24px / 16 = 1.5rem)
const MANUAL_INDENT_REM = 3;   // rem applied to flagged paragraphs
const AUDIO_BUTTON_SIZE = 1.5; // rem

const computeIndent = (node) =>
  typeof node?.indent === "number" && Number.isFinite(node.indent)
    ? node.indent
    : 0;

// Helper for rendering individual nodes (NON-HEADING NODES ONLY)
const renderNode = (node, key) => {
  // Skip heading nodes - they should only be used for accordion structure
  if (node.kind === "heading") {
    return null;
  }

  const indentValue = computeIndent(node);
  const baseIndentRem = indentValue * INDENT_PER_LEVEL;
  const manualIndentRem =
    node.kind === "paragraph" && node.is_indented ? MANUAL_INDENT_REM : 0;
  const paragraphIndentRem = baseIndentRem + manualIndentRem;

  if (node.kind === "paragraph"){
    console.log("Processing paragraph node:", {
      kind: node.kind,
      audio_key: node.audio_key,
      audio_seq: node.audio_seq,
        text: node.inlines?.[0]?.text?.substring(0, 50)
      });

      // Check for audio_key first, then fallback to audio_seq
      const hasAudio = node.audio_key || node.audio_seq;
      const hasBold = nodeHasBold(node);
      const hasSpacing = hasYellowHighlight(node); // NEW: Check for yellow highlight

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <p
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: paragraphIndentRem ? `${paragraphIndentRem}rem` : undefined,
              display: "flex",
              alignItems: multiline ? "flex-start" : "center",
              marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : "0.5rem"), // Use spacing if flagged
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
            <span>{renderInlines(node.inlines)}</span>
          </p>
        );
      }

      return (
        <p
          key={key}
          style={{
            marginLeft: paragraphIndentRem ? `${paragraphIndentRem}rem` : undefined,
            marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : undefined), // Use spacing if flagged
          }}
        >
          {renderInlines(node.inlines)}
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
      const hasSpacing = hasYellowHighlight(node); // NEW: Check for yellow highlight

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <li
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: baseIndentRem ? `${baseIndentRem + 4.5}rem` : "2rem", // Extra indent for list bullet
              display: "flex",
              alignItems: multiline ? "flex-start" : "flex-start",
              marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : "0.5rem"), // Use spacing if flagged
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
            <span>{renderInlines(node.inlines)}</span>
          </li>
        );
      }
      return (
        <li
          key={key}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: hasSpacing ? "2rem" : (nodeHasBold(node) ? 0 : undefined), // Use spacing if flagged
          }}
        >
          {renderInlines(node.inlines)}
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
      const hasSpacing = hasYellowHighlight(node); // NEW: Check for yellow highlight

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <div
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
              display: "flex",
              alignItems: multiline ? "flex-start" : "center",
              marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : "0.5rem"), // Use spacing if flagged
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
            <span>{renderInlines(node.inlines)}</span>
          </div>
        );
      }
      return (
        <div
          key={key}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: hasSpacing ? "2rem" : (nodeHasBold(node) ? 0 : undefined), // Use spacing if flagged
          }}
        >
          {renderInlines(node.inlines)}
        </div>
      );
    }

    if (node.kind === "numbered_item") {
      // This should be handled by renderNodesWithNumberedLists
      return null;
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
    const hasSpacing = hasYellowHighlight(node);
    const multiline = hasLineBreak(node);
    const baseIndent = computeIndent(node);
    const extraIndent = baseIndent - groupIndent;
    const extraIndentRem = extraIndent * INDENT_PER_LEVEL;

    if (hasAudio) {
      return (
        <li
          key={key}
          className="audio-bullet"
          style={{
            marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
            display: "flex",
            alignItems: multiline ? "flex-start" : "flex-start",
            marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : "0.5rem"),
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
          <span>{renderInlines(node.inlines)}</span>
        </li>
      );
    }

    return (
      <li
        key={key}
        style={{
          marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
          marginBottom: hasSpacing ? "2rem" : (hasBold ? 0 : undefined),
        }}
      >
        {renderInlines(node.inlines)}
      </li>
    );
  };

  const renderNumberedGroup = (items, keyPrefix) => {
    if (!items.length) return null;
    const groupIndent = computeIndent(items[0]);
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
    let i = 0;
    let groupIndex = 0;

    while (i < nodeList.length) {
      const node = nodeList[i];
      if (node.kind === "numbered_item") {
        const group = [];
        while (i < nodeList.length && nodeList[i].kind === "numbered_item") {
          group.push(nodeList[i]);
          i++;
        }
        elements.push(renderNumberedGroup(group, `numbered-group-${groupIndex++}`));
      } else {
        elements.push(renderNode(node, i));
        i++;
      }
    }

    return elements;
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
    return (
      <div className="markdown-section">
        {sections.map((sec, i) => {
          // If section has no heading, render content directly
          if (!sec.heading) {
            console.log("Rendering no-heading section:", sec.key, "with", sec.body.length, "items");
            return (
              <div key={sec.key} className="markdown-content no-heading">
                {renderNodesWithNumberedLists(sec.body)}
              </div>
            );
          }

          // Clean the heading text for display
          const cleanHeadingText = sec.heading.inlines
            .map((s) => s.text)
            .join("")
            .trim()
            .replace(/^\t+/, ""); // Remove leading tabs

          console.log("Rendering accordion section:", cleanHeadingText);
          const normalizedHeading = cleanHeadingText.trim().toLowerCase();
          const isLessonFocus =
            normalizedHeading.includes("lesson focus") ||
            normalizedHeading.includes("จุดเน้นบทเรียน");

          // Render as accordion section
          return (
            <CollapsibleDetails
              key={i}
              className={`markdown-item${isLessonFocus ? " markdown-item-focus" : ""}`}
              defaultOpen={i === 0}
              summaryContent={cleanHeadingText}
            >
              <div className="markdown-content">
                {renderNodesWithNumberedLists(sec.body)}
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
        {renderNodesWithNumberedLists(nodes)}
      </div>
    </div>
  );
}

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
    return inlines.map((span, m) => {
      const cleanText = cleanAudioTags(span.text);

      // Check if we need a space before this span
      let needsSpaceBefore = false;
      if (m > 0) {
        const prevSpan = inlines[m - 1];
        const prevText = cleanAudioTags(prevSpan.text);

        // Add space if previous span doesn't end with whitespace or punctuation
        // and current span doesn't start with whitespace or punctuation
        const prevEndsWithSpaceOrPunct = /[\s.,!?;:']$/.test(prevText);
        const currentStartsWithSpaceOrPunct = /^[\s.,!?;:']/.test(cleanText);

        needsSpaceBefore = !prevEndsWithSpaceOrPunct && !currentStartsWithSpaceOrPunct && cleanText.trim();
      }


      const commonStyle = {
        fontWeight: span.bold ? "bold" : undefined,
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        whiteSpace: "pre-line",
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
            {cleanText}
          </a>
        );
      } else {
        element = <span style={commonStyle}>{cleanText}</span>;
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

  const containsAudioTag = (node) => /\[audio:[^\]]+\]/i.test(getNodeText(node));

  const hasLineBreak = (node) =>
    Array.isArray(node?.inlines) &&
    node.inlines.some((span) => cleanAudioTags(span.text).includes("\n"));

  const looksLikeDialogue = (node) => /^[A-Z][a-z]+:\s/.test(getNodeText(node));

  const computeIndent = (node, defaultIndent = 0) =>
    typeof defaultIndent === "number" && Number.isFinite(defaultIndent)
      ? defaultIndent
      : node?.indent || 0;

  const shouldInheritIndent = (previousNode, currentNode) => {
    if (!previousNode || !currentNode) return false;
    if (currentNode.kind === "list_item") return false;
    if (!looksLikeDialogue(currentNode)) return false;

    // Check if previous node was an audio list item (start of dialogue)
    const previousIsAudioList =
      previousNode.kind === "list_item" && containsAudioTag(previousNode);

    // Check if previous node was a dialogue continuation (any non-list-item with dialogue format)
    const previousIsDialogueContinuation =
      (previousNode.kind === "paragraph" ||
      previousNode.kind === "misc_item" ||
      previousNode.kind === "numbered_item") &&
      looksLikeDialogue(previousNode);

    if (!previousIsAudioList && !previousIsDialogueContinuation) return false;

    return true;
  };

  const INDENT_PER_LEVEL = 1.5; // rem (24px / 16 = 1.5rem)
  const AUDIO_BUTTON_SIZE = 1.5; // rem
  const AUDIO_BUTTON_GAP = 0.5; // rem - gap between button and text
  const AUDIO_TEXT_OFFSET = AUDIO_BUTTON_SIZE + AUDIO_BUTTON_GAP; // 2rem total

  // Helper for rendering individual nodes (NON-HEADING NODES ONLY)
  const renderNode = (node, key, previousNode = null) => {
    // Skip heading nodes - they should only be used for accordion structure
    if (node.kind === "heading") {
      return null;
    }

    const inheritIndent = shouldInheritIndent(previousNode, node);
    const indentValue = inheritIndent
      ? computeIndent(node, previousNode?.indent)
      : computeIndent(node, node?.indent);
    const baseIndentRem = indentValue * INDENT_PER_LEVEL;

    // Continuation lines align with text after audio button
    const textIndentRem = inheritIndent
      ? baseIndentRem + AUDIO_TEXT_OFFSET
      : baseIndentRem;

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

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <p
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: `${baseIndentRem}rem`,
              display: "flex",
              alignItems: multiline ? "flex-start" : "center",
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
            <span>{renderInlines(node.inlines)}</span>
          </p>
        );
      }

      return (
        <p
          key={key}
          style={{
            marginLeft: `${textIndentRem}rem`,
            marginBottom: hasBold ? 0 : undefined,
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

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <li
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: `${baseIndentRem}rem`,
              display: "flex",
              alignItems: multiline ? "flex-start" : "center",
              marginBottom: hasBold ? 0 : undefined,
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
            marginLeft: `${textIndentRem}rem`,
            marginBottom: nodeHasBold(node) ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines)}
        </li>
      );
    }
    if (node.kind === "numbered_item" || node.kind === "misc_item") {
      console.log("Processing numbered/misc_item node:", {
        kind: node.kind,
        audio_key: node.audio_key,
        audio_seq: node.audio_seq,
        text: node.inlines?.[0]?.text?.substring(0, 50)
      });

      // Check for audio_key first, then fallback to audio_seq
      const hasAudio = node.audio_key || node.audio_seq;
      const hasBold = nodeHasBold(node);

      if (hasAudio) {
        const multiline = hasLineBreak(node);
        return (
          <div
            key={key}
            className="audio-bullet"
            style={{
              marginLeft: `${baseIndentRem}rem`,
              display: "flex",
              alignItems: multiline ? "flex-start" : "center",
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
            <span>{renderInlines(node.inlines)}</span>
          </div>
        );
      }
      // Render as a div, not <li>, to avoid default bullet styling
      return (
        <div
          key={key}
          style={{
            marginLeft: `${textIndentRem}rem`,
            marginBottom: nodeHasBold(node) ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines)}
        </div>
      );
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
                {sec.body.map((node, k) =>
                  renderNode(node, k, sec.body[k - 1] || null)
                )}
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
                {sec.body.map((node, k) =>
                  renderNode(node, k, sec.body[k - 1] || null)
                )}
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
        {nodes.map((node, i) => renderNode(node, i, nodes[i - 1] || null))}
      </div>
    </div>
  );
}

import React from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
import LessonTable from "./LessonTable";

// Helper function to clean audio tags from text - FIXED to handle [audio:...] format
function cleanAudioTags(text) {
  if (!text || typeof text !== 'string') return text;
  // Replace [audio:...] tags with a space, then clean up multiple spaces
  return text
    .replace(/\[audio:[^\]]+\]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export default function TopicRichSectionRenderer({
  nodes,
  uiLang = "en"
}) {
  if (!Array.isArray(nodes) || nodes.length === 0) return null;

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

  const containsAudioTag = (node) => /\[audio:[^\]]+\]/i.test(getNodeText(node));
  const looksLikeDialogue = (node) => /^[A-Z][a-z]+:\s/.test(getNodeText(node));

  const computeIndent = (node, defaultIndent = 0) =>
    typeof defaultIndent === "number" && Number.isFinite(defaultIndent)
      ? defaultIndent
      : node?.indent || 0;

  const shouldInheritIndent = (previousNode, currentNode) => {
    if (!previousNode || !currentNode) return false;
    if (currentNode.kind === "list_item") return false;
    if (!looksLikeDialogue(currentNode)) return false;

    const previousIsAudioList =
      previousNode.kind === "list_item" && containsAudioTag(previousNode);

    if (!previousIsAudioList) return false;

    return true;
  };

  const AUDIO_TEXT_OFFSET = 28;

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
    const baseIndentPx = indentValue * 24;
    const textIndentPx = baseIndentPx + (inheritIndent ? AUDIO_TEXT_OFFSET : 0);

    if (node.kind === "paragraph") {
      return (
        <p key={key} style={{ marginLeft: textIndentPx }}>
          {renderInlines(node.inlines)}
        </p>
      );
    }

    if (node.kind === "list_item") {
      return (
        <li key={key} style={{ marginLeft: baseIndentPx }}>
          {renderInlines(node.inlines)}
        </li>
      );
    }

    if (node.kind === "numbered_item" || node.kind === "misc_item") {
      // Render as a div, not <li>, to avoid default bullet styling
      return (
        <div key={key} style={{ marginLeft: textIndentPx }}>
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
        />
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

          const normalizedHeading = cleanHeadingText.trim().toLowerCase();
          const isLessonFocus =
            normalizedHeading.includes("lesson focus") ||
            normalizedHeading.includes("จุดเน้นบทเรียน");

          // Render as accordion section
          return (
            <details
              key={sec.key}
              className={`markdown-item${isLessonFocus ? " markdown-item-focus" : ""}`}
              open={i === 0}
            >
              <summary className="markdown-summary">
                {cleanHeadingText}
              </summary>
              <div className="markdown-content">
                {sec.body.map((node, k) =>
                  renderNode(node, k, sec.body[k - 1] || null)
                )}
              </div>
            </details>
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

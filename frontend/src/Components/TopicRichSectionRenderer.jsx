import React from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
import LessonTable from "./LessonTable";
import CollapsibleDetails from "./CollapsibleDetails";

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

const computeIndent = (node) =>
  typeof node?.indent === "number" && Number.isFinite(node.indent)
    ? node.indent
    : 0;

const nodeHasBold = (node) =>
  Array.isArray(node?.inlines) && node.inlines.some((span) => span?.bold);

const INDENT_PER_LEVEL = 1.5; // rem

// Helper for rendering individual nodes (NON-HEADING NODES ONLY)
const renderNode = (node, key) => {
  // Skip heading nodes - they should only be used for accordion structure
  if (node.kind === "heading") {
    return null;
  }

  const indentValue = computeIndent(node);
  const baseIndentRem = indentValue * INDENT_PER_LEVEL;
  const hasBold = nodeHasBold(node);

  if (node.kind === "paragraph") {
      return (
        <p
          key={key}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: hasBold ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines)}
        </p>
      );
    }

    if (node.kind === "list_item") {
      return (
        <li
          key={key}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: hasBold ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines)}
        </li>
      );
    }

    if (node.kind === "misc_item") {
      return (
        <div
          key={key}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: hasBold ? 0 : undefined,
          }}
        >
          {renderInlines(node.inlines)}
        </div>
      );
    }

    if (node.kind === "numbered_item") {
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
        />
      );
    }

    return null;
  };

  const renderNumberedListItem = (node, key, groupIndent) => {
    const hasBold = nodeHasBold(node);
    const baseIndent = computeIndent(node);
    const extraIndent = baseIndent - groupIndent;
    const extraIndentRem = extraIndent * INDENT_PER_LEVEL;

    return (
      <li
        key={key}
        style={{
          marginLeft: extraIndentRem ? `${extraIndentRem}rem` : undefined,
          marginBottom: hasBold ? 0 : undefined,
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

import React, { useState } from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
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

export default function TopicRichSectionRenderer({
  nodes,
  uiLang = "en"
}) {
  if (!Array.isArray(nodes) || nodes.length === 0) return null;

  const INLINE_MARKER_RE = /(\[X\]|\[✓\]|\[-\])/g;
  const INLINE_MARKER_COLORS = {
    "[X]": "#FD6969",
    "[✓]": "#3CA0FE",
    "[-]": "#28A265",
  };

  // Helper for rendering inlines with proper spacing AND audio tag removal
  const renderInlines = (inlines) => {
    const processedInlines = inlines.map((span, idx) => {
      const cleanText = cleanAudioTags(span.text);
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

      return { span, cleanText, suppressSpaceBefore };
    });

    return processedInlines.map((entry, m) => {
      const { span, cleanText } = entry;
      const currentText = typeof cleanText === "string" ? cleanText : "";

      // Check if we need a space before this span
      let needsSpaceBefore = false;
      if (m > 0) {
        const prevEntry = processedInlines[m - 1];
        if (prevEntry.suppressSpaceBefore) {
          needsSpaceBefore = false;
        } else {
          const prevText = typeof prevEntry.cleanText === "string" ? prevEntry.cleanText : "";

          // Add space if previous span doesn't end with whitespace or punctuation
          // and current span doesn't start with whitespace or punctuation
          const prevEndsWithSpaceOrPunct = /[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]$/.test(prevText);
          const currentStartsWithSpaceOrPunct = /^[\s.,!?;:'\u2019\u2018\u201c\u201d\u2026\u2014\u2013\-()[\]{}]/.test(currentText);

          needsSpaceBefore =
            !prevEndsWithSpaceOrPunct && !currentStartsWithSpaceOrPunct && currentText.trim();
        }
      }

      const commonStyle = {
        fontWeight: span.bold ? "bold" : undefined,
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        whiteSpace: "pre-line",
      };

      const renderTextWithMarkers = (text, keyPrefix) => {
        const segments = String(text).split(INLINE_MARKER_RE).filter((part) => part !== "");
        return segments.map((segment, segIdx) => {
          const markerColor = INLINE_MARKER_COLORS[segment];
          const style = markerColor
            ? { ...commonStyle, color: markerColor, fontWeight: 600 }
            : commonStyle;

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
                key={`${keyPrefix}-${segIdx}`}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                style={linkStyle}
              >
                {segment}
              </a>
            );
          }

          return (
            <span key={`${keyPrefix}-${segIdx}`} style={style}>
              {segment}
            </span>
          );
        });
      };

      return (
        <React.Fragment key={m}>
          {needsSpaceBefore && " "}
          {renderTextWithMarkers(cleanText, `frag-${m}`)}
        </React.Fragment>
      );
    });
  };

const computeIndent = (node) =>
  typeof node?.indent === "number" && Number.isFinite(node.indent)
    ? node.indent
    : 0;

const nodeHasBold = (node) =>
  Array.isArray(node?.inlines) && node.inlines.some((span) => span?.bold);

const isSubheaderNode = (node) => {
  if (node?.is_subheader) return true;
  if (node?.kind !== "paragraph") return false;
  const textSpans = (node.inlines || []).filter(
    (span) => typeof span?.text === "string" && span.text.trim() !== ""
  );
  return textSpans.length > 0 && textSpans.every((span) => !!span.bold);
};

const INDENT_PER_LEVEL = 1.5; // rem

// Helper for rendering individual nodes (NON-HEADING NODES ONLY)
const renderNode = (node, key) => {
  // Skip non-subheader heading nodes - they should only be used for accordion structure
  if (node.kind === "heading" && !node.is_subheader) {
    return null;
  }

  if (node.kind === "image") {
    const src =
      node.image_url ||
      (node.image_key ? `/api/images/${encodeURIComponent(node.image_key)}` : null);
    if (!src) {
      return null;
    }
    return (
      <TopicRichImage
        key={key}
        src={src}
        altText={node.alt_text}
      />
    );
  }

  const indentValue = computeIndent(node);
  const baseIndentRem = indentValue * INDENT_PER_LEVEL;
  const hasBold = nodeHasBold(node);

  if (node.kind === "heading" && node.is_subheader) {
    return (
      <p
        key={key}
        className="rich-subheader"
        style={{
          marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
          marginBottom: "1rem",
        }}
      >
        {renderInlines(node.inlines)}
      </p>
    );
  }

  if (node.kind === "paragraph") {
      const textSpans = (node.inlines || []).filter(
        (span) => typeof span?.text === "string" && span.text.trim() !== ""
      );
      const allTextBold = textSpans.length > 0 && textSpans.every((span) => !!span.bold);
      const isSubheader = allTextBold;
      return (
        <p
          key={key}
          className={isSubheader ? "rich-subheader" : undefined}
          style={{
            marginLeft: baseIndentRem ? `${baseIndentRem}rem` : undefined,
            marginBottom: isSubheader ? "1rem" : (hasBold ? 0 : undefined),
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

    if (node.kind === "spacer") {
      return <div key={key} className="para-spacer" aria-hidden="true" />;
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
      if (node.kind === "heading" || isSubheaderNode(node)) {
        elements.push(renderNode(node, i));
        i++;
        continue;
      }
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
    if (node.kind === "heading" && !node.is_subheader) {
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
          const lessonFocusMarkers = [
            "lesson focus",
            "จุดเน้นบทเรียน",
            "หัวข้อสำคัญของบทเรียน",
            "โฟกัสบทเรียน",
            "ประเด็นหลักของบทเรียน",
          ];
          const isLessonFocus = lessonFocusMarkers.some((marker) =>
            normalizedHeading.includes(marker)
          );

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
function TopicRichImage({ src, altText }) {
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

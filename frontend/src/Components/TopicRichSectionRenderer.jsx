import React, { useMemo, useState } from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
import LessonTable from "./LessonTable";
import CollapsibleDetails from "./CollapsibleDetails";
import supabaseClient from "../supabaseClient";

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
  const nodesList = Array.isArray(nodes) ? nodes : [];

  const topicImageUrls = useMemo(() => {
    const map = new Map();
    nodesList.forEach((node) => {
      if (node?.kind !== "image") return;
      if (node.image_url) {
        map.set(node.image_key, node.image_url);
        return;
      }
      const key = typeof node.image_key === "string" ? node.image_key.trim() : "";
      if (!key || map.has(key)) return;
      const normalized = key.includes(".") ? key : `${key}.webp`;
      const { data } = supabaseClient.storage.from("lesson-images").getPublicUrl(normalized);
      if (data?.publicUrl) {
        map.set(key, data.publicUrl);
      }
    });
    return map;
  }, [nodesList]);

  if (nodesList.length === 0) return null;

  const TH_RE = /[\u0E00-\u0E7F]/;
  const INLINE_MARKER_RE = /(\[X\]|\[✓\]|\[-\])/g;
  const INLINE_MARKER_COLORS = {
    "[X]": "#FD6969",
    "[✓]": "#3CA0FE",
    "[-]": "#28A265",
  };
  const HEX_COLOR_RE = /^#[0-9a-f]{6}$/;

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

    const collapseInlineMarkers = (entries) => {
      const out = [];
      for (let i = 0; i < entries.length; i += 1) {
        const current = entries[i];
        const next = entries[i + 1];
        const next2 = entries[i + 2];
        const currentText = typeof current?.cleanText === "string" ? current.cleanText : "";
        const nextText = typeof next?.cleanText === "string" ? next.cleanText : "";
        const next2Text = typeof next2?.cleanText === "string" ? next2.cleanText : "";

        const isMarkerMiddle = ["X", "✓", "-", "check"].includes(nextText);
        if (currentText === "[" && isMarkerMiddle && next2Text.startsWith("]")) {
          const rest = next2Text.slice(1);
          const mergedText = `[${nextText}]${rest}`;
          out.push({
            ...current,
            cleanText: mergedText,
          });
          i += 2;
          continue;
        }

        out.push(current);
      }
      return out;
    };

    const collapsedInlines = collapseInlineMarkers(processedInlines);

    return collapsedInlines.map((entry, m) => {
      const { span, cleanText } = entry;
      const currentText = typeof cleanText === "string" ? cleanText : "";

      // Check if we need a space before this span
      let needsSpaceBefore = false;
      if (m > 0) {
        const prevEntry = collapsedInlines[m - 1];
        if (prevEntry.suppressSpaceBefore) {
          needsSpaceBefore = false;
        } else {
          const prevText = typeof prevEntry.cleanText === "string" ? prevEntry.cleanText : "";

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

      const normalizedColor =
        typeof span?.color === "string" ? span.color.trim().toLowerCase() : "";
      const colorStyle = HEX_COLOR_RE.test(normalizedColor) ? normalizedColor : undefined;

      const commonStyle = {
        fontWeight: span.bold ? "bold" : undefined,
        fontStyle: span.italic ? "italic" : undefined,
        textDecoration: span.underline ? "underline" : undefined,
        color: colorStyle,
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

const DEFAULT_INDENT_PER_LEVEL = 1.5; // rem (24px / 16 = 1.5rem)
const DEFAULT_MANUAL_INDENT_REM = 3;   // rem applied to flagged paragraphs

function getIndentConfig() {
  if (typeof window === "undefined") {
    return {
      indentPerLevel: DEFAULT_INDENT_PER_LEVEL,
      manualIndentRem: DEFAULT_MANUAL_INDENT_REM,
      listItemOffset: DEFAULT_INDENT_PER_LEVEL * 3,
      listItemBaseOffset: (DEFAULT_INDENT_PER_LEVEL * 4) / 3,
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
    listItemOffset: indentPerLevel * 3,
    listItemBaseOffset: (indentPerLevel * 4) / 3,
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

// Helper for rendering individual nodes (NON-HEADING NODES ONLY)
const renderNode = (node, key) => {
  // Skip non-subheader heading nodes - they should only be used for accordion structure
  if (node.kind === "heading" && !node.is_subheader) {
    return null;
  }

  if (node.kind === "image") {
    const key = typeof node.image_key === "string" ? node.image_key.trim() : "";
    const src =
      node.image_url ||
      (key ? topicImageUrls.get(key) : null) ||
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

  const indentLevel = computeIndentLevel(node);
  const baseIndentRem = indentLevel * INDENT_PER_LEVEL;
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
      const isIndented = indentLevel > 0 || node?.is_indented === true;
      const paragraphMarginLeft = indentLevel
        ? `${listTextStartRem(indentLevel)}rem`
        : (isIndented ? `${MANUAL_INDENT_REM}rem` : undefined);
      return (
        <p
          key={key}
          className={isSubheader ? "rich-subheader" : undefined}
          style={{
            marginLeft: paragraphMarginLeft,
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
            marginLeft: indentLevel
              ? `${listTextStartRem(indentLevel) + 3}rem`
              : undefined,
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
            marginLeft: indentLevel
              ? `${listTextStartRem(indentLevel) + 3}rem`
              : undefined,
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
      const tableVisibility = typeof node.table_visibility === "string"
        ? node.table_visibility
        : (
          typeof node.table_label === "string" && /-M:?\s*$/i.test(node.table_label)
            ? "mobile"
            : null
        );
      return (
        <LessonTable
          key={key}
          data={{
            cells: node.cells,
            indent: node.indent,
          }}
          tableVisibility={tableVisibility}
        />
      );
    }

    if (node.kind === "spacer") {
      return <div key={key} className="para-spacer" aria-hidden="true" />;
    }

    return null;
  };

  const renderNumberedListItem = (node, key) => {
    const hasBold = nodeHasBold(node);
    return (
      <li
        key={key}
        style={{
          marginBottom: hasBold ? 0 : undefined,
        }}
      >
        {renderInlines(node.inlines)}
      </li>
    );
  };

  const renderNodesWithNumberedLists = (nodeList) => {
    const elements = [];
    const countsByIndent = new Map();

    const resetCounters = () => {
      countsByIndent.clear();
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
          {renderNumberedListItem(node, `${key}-item`)}
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
      elements.push(renderNode(node, idx));
    });

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

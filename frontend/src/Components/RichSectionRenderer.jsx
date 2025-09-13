import React from "react";
import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import "../Styles/LessonTable.css";
import AudioBullet from "./AudioBullet";
import LessonTable from "./LessonTable";

// Renders a node array from content_jsonb (headings, paragraphs, lists, etc.)
export default function RichSectionRenderer({
  nodes,
  snipIdx,
  uiLang = "en",
  renderQuickPractice
}) {
  if (!Array.isArray(nodes) || nodes.length === 0) return null;

  // Helper for rendering inlines
  const renderInlines = (inlines) =>
    inlines.map((span, m) => (
      <span
        key={m}
        style={{
          fontWeight: span.bold ? "bold" : undefined,
          fontStyle: span.italic ? "italic" : undefined,
          textDecoration: span.underline ? "underline" : undefined,
        }}
      >
        {span.text}
      </span>
    ));

  // Helper for rendering individual nodes (NON-HEADING NODES ONLY)
  const renderNode = (node, key) => {
    if (node.kind === "paragraph") {
      return (
        <p key={key} style={{ marginLeft: (node.indent || 0) * 24 }}>
          {renderInlines(node.inlines)}
        </p>
      );
    }

    if (node.kind === "list_item") {
      if (node.audio_seq) {
        return (
          <AudioBullet
            key={key}
            node={node}
            indent={node.indent}
            snipIdx={snipIdx}
            renderInlines={renderInlines}
          />
        );
      }
      return (
        <li key={key} style={{ marginLeft: (node.indent || 0) * 24 }}>
          {renderInlines(node.inlines)}
        </li>
      );
    }
    if (node.kind === "numbered_item" || node.kind === "misc_item") {
      if (node.audio_seq) {
        return (
          <AudioBullet
            key={key}
            node={node}
            indent={node.indent}
            snipIdx={snipIdx}
            renderInlines={renderInlines}
          />
        );
      }
      // Render as a div, not <li>, to avoid default bullet styling
      return (
        <div key={key} style={{ marginLeft: (node.indent || 0) * 24 }}>
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

    // REMOVED: heading rendering logic - headings should only be rendered as accordion headers

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
  // const seenHeadings = new Set();

  nodes.forEach((node, idx) => {
    if (node.kind === "heading") {
      // Clean the heading text by trimming whitespace and tabs
      const headingText = node.inlines
        .map((s) => s.text)
        .join("")
        .replace(/\s+/g, " ")
        .trim()

      console.log(`Found heading at index ${idx}:`, headingText, "Node:", node);

      // Create a unique key for this heading based on text and position
      const headingKey = `${headingText}-${idx}`;

      // Skip only if we've seen this exact heading recently (within last 3 nodes)
      // const recentHeadings = Array.from(seenHeadings).slice(-3);
      // if (recentHeadings.includes(headingText)) {
      //   return;
      // }

      // seenHeadings.add(headingText);

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

  // Debug: Log sections to see what's being created
  console.log("Sections created:", sections.map(s => ({
    heading: s.heading ? s.heading.inlines.map(i => i.text).join("").trim() : "no-heading",
    bodyCount: s.body.length,
    key: s.key,
    body: s.body.map(b => ({ kind: b.kind, text: b.inlines?.[0]?.text?.substring(0, 30) }))
  })));

  // If we have sections with headings, render as accordion
  const hasHeadings = sections.some(sec => sec.heading);
  console.log("HasHeadings:", hasHeadings, "Total sections:", sections.length);

  if (hasHeadings) {
    return (
      <div className="markdown-section">
        {sections.map((sec, i) => {
          // If section has no heading, render content directly
          if (!sec.heading) {
            console.log("Rendering no-heading section:", sec.key, "with", sec.body.length, "items");
            return (
              <div key={sec.key} className="markdown-content no-heading">
                {sec.body.map((node, k) => renderNode(node, k))}
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
          // Render as accordion section
          return (
            <details key={sec.key} className="markdown-item" open={i === 0}>
              <summary className="markdown-summary">
                {cleanHeadingText}
              </summary>
              <div className="markdown-content">
                {sec.body.map((node, k) => renderNode(node, k))}
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
        {nodes.map((node, i) => renderNode(node, i))}
      </div>
    </div>
  );
}

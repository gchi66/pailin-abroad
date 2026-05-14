import React from "react";

// Lightweight inline renderer (keeps style spacing and drops [audio:...] tags)
function cleanAudioTags(text) {
  if (!text || typeof text !== "string") return text;
  return text
    .replace(/\[audio:[^\]]+\]/g, " ")
    .replace(/\[img:[^\]]+\]/g, " ")
    .replace(/[^\S\r\n]+/g, " ")
    .replace(/\s*\n\s*/g, "\n");
}

function renderTextWithBlankLines(text, keyPrefix = "blank") {
  if (!text) return null;

  const segments = String(text).split(/(_{2,})/g);
  return segments.map((segment, idx) => {
    if (!segment) return null;
    if (/^_{2,}$/.test(segment)) {
      const blankLength = Math.min(segment.length, 4);
      const widthCh = Math.max(2.5, blankLength * 0.95);
      return (
        <span
          key={`${keyPrefix}-${idx}`}
          aria-hidden="true"
          style={{
            display: "inline-block",
            verticalAlign: "baseline",
            width: `${widthCh}ch`,
            minWidth: "2.5ch",
            borderBottom: "0.08em solid currentColor",
            lineHeight: 1,
            transform: "translateY(0.2em)",
          }}
        />
      );
    }
    return <React.Fragment key={`${keyPrefix}-${idx}`}>{segment}</React.Fragment>;
  });
}

export function renderInlines(inlines = []) {
  return inlines.map((span, idx) => {
    const text = cleanAudioTags(span?.text || "");
    const style = {
      fontWeight: span?.bold ? "700" : undefined,
      fontStyle: span?.italic ? "italic" : undefined,
      textDecoration: span?.underline ? "underline" : undefined,
      whiteSpace: "pre-line",
    };
    return (
      <React.Fragment key={idx}>
        {idx > 0 && !/^[\s.,!?;:'"()[\]\-]/.test(text) ? " " : ""}
        <span style={style}>{renderTextWithBlankLines(text, `inline-${idx}`)}</span>
      </React.Fragment>
    );
  });
}

export default function InlineText({ inlines, text, as = "span", className }) {
  const Tag = as;
  if (Array.isArray(inlines) && inlines.length) {
    return <Tag className={className}>{renderInlines(inlines)}</Tag>;
  }
  if (text) {
    return (
      <Tag className={className} style={{ whiteSpace: "pre-line" }}>
        {renderTextWithBlankLines(text, "plain")}
      </Tag>
    );
  }
  return null;
}

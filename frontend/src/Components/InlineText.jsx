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
        <span style={style}>{text}</span>
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
    return <Tag className={className}>{text}</Tag>;
  }
  return null;
}

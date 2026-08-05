import React from "react";

const styleFor = (style = {}) => ({
  fontWeight: style.bold ? 700 : undefined,
  fontStyle: style.italic ? "italic" : undefined,
  textDecoration: style.underline ? "underline" : undefined,
  backgroundColor: style.highlight || undefined,
  color: style.color || undefined,
});

export const hasOrderedPracticeContent = (content) =>
  content?.version === 1 &&
  Array.isArray(content.blocks) &&
  content.blocks.length > 0;

export default function OrderedPracticeContent({
  content,
  as: Tag = "span",
  className,
}) {
  if (!hasOrderedPracticeContent(content)) return null;

  return (
    <Tag className={className} style={{ whiteSpace: "pre-wrap" }}>
      {content.blocks.map((block, blockIndex) => (
        <React.Fragment key={`ordered-block-${blockIndex}`}>
          {blockIndex > 0 ? "\n" : null}
          {(block?.tokens || []).map((token, tokenIndex) => {
            const key = `ordered-token-${blockIndex}-${tokenIndex}`;
            if (token?.type === "line_break") return <br key={key} />;
            if (token?.type !== "text") return null;
            const node = (
              <span style={styleFor(token.style)}>{token.text}</span>
            );
            return token.style?.link ? (
              <a key={key} href={token.style.link}>{node}</a>
            ) : (
              <React.Fragment key={key}>{node}</React.Fragment>
            );
          })}
        </React.Fragment>
      ))}
    </Tag>
  );
}

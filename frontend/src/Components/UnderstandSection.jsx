import React from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/UnderstandSection.css";

/**
 * Splits a single markdown string into an array of {title, bodyMarkdown}
 * using H2/H3/etc. headings as boundaries.
 */
function splitByHeadings(md) {
  const lines = md.split("\n");
  const parts = [];
  let current = { title: "Overview", body: [] };   // fallback section

  lines.forEach((line) => {
    const headingMatch = line.match(/^(#{2,6})\s+(.*)/);   // ## Heading
    if (headingMatch) {
      // push the previous chunk before starting a new one
      if (current.body.length) parts.push(current);
      current = { title: headingMatch[2].trim(), body: [] };
    } else {
      current.body.push(line);
    }
  });
  if (current.body.length) parts.push(current);
  return parts;
}

export default function UnderstandSection({ markdown = "" }) {
  const sections = splitByHeadings(markdown);

  return (
    <div className="understand-wrap">
      {sections.map(({ title, body }, idx) => (
        <details key={idx} className="understand-item" open={idx === 0}>
          <summary className="understand-summary">{title}</summary>
          <ReactMarkdown>
            {body.join("\n")}
          </ReactMarkdown>
        </details>
      ))}
    </div>
  );
}

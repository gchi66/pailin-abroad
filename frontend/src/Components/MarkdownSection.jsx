import React from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/MarkdownSection.css";

/**
 * Splits markdown into collapsible sections based on ## headings
 */
function splitByHeadings(markdown) {
  const sections = [];
  let currentSection = null;

  markdown.split('\n').forEach(line => {
    if (line.startsWith('## ')) {
      if (currentSection) sections.push(currentSection);
      currentSection = {
        title: line.slice(3).trim(),
        body: []
      };
    } else if (currentSection) {
      currentSection.body.push(line);
    }
  });

  if (currentSection) sections.push(currentSection);
  return sections;
}

export default function MarkdownSection({
  markdown = "",
  defaultOpenFirst = true
}) {
  const sections = splitByHeadings(markdown);

  return (
    <div className="markdown-section">
      {sections.map(({ title, body }, idx) => (
        <details
          key={idx}
          className="markdown-item"
          open={defaultOpenFirst && idx === 0}
        >
          <summary className="markdown-summary">
            {title || "More Information"}
          </summary>
          <div className="markdown-content">
            <ReactMarkdown>
              {body.join('\n').trim()}
            </ReactMarkdown>
          </div>
        </details>
      ))}
    </div>
  );
}

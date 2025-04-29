import React from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/UnderstandSection.css";

function splitByHeadings(markdown) {
  const sections = [];
  let currentSection = null;

  // Split by double newlines to preserve paragraphs
  const paragraphs = markdown.split(/\n\s*\n/);

  paragraphs.forEach(paragraph => {
    if (paragraph.startsWith('## ')) {
      if (currentSection) sections.push(currentSection);
      currentSection = {
        title: paragraph.replace('## ', '').trim(),
        body: []
      };
    } else if (currentSection) {
      // Preserve all Markdown formatting in body
      currentSection.body.push(paragraph);
    }
  });

  if (currentSection) sections.push(currentSection);
  return sections;
}

export default function UnderstandSection({ markdown = "" }) {
  const sections = splitByHeadings(markdown);

  return (
    <div className="understand-wrap">
      {sections.map(({ title, body }, idx) => (
        <details key={idx} className="understand-item" open={idx === 0}>
          <summary className="understand-summary">{title}</summary>
          <div className="markdown-content">
            {body.map((paragraph, i) => (
              <ReactMarkdown key={i}>
                {paragraph}
              </ReactMarkdown>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}

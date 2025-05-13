import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw   from "rehype-raw";   // ⬅︎ allow raw HTML (tables) in markdown
import remarkGfm   from "remark-gfm";   // ⬅︎ lists, strikethrough, tables, etc.
import "../Styles/MarkdownSection.css";

/* ------------------------------------------------------------
   Split markdown into collapsible “cards” by `##` sub‑headings
------------------------------------------------------------ */
function splitByHeadings(markdown) {
  const sections = [];
  let current = null;

  markdown.split("\n").forEach((line) => {
    if (line.startsWith("## ")) {
      if (current) sections.push(current);
      current = { title: line.slice(3).trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    }
  });

  if (current) sections.push(current);
  return sections;
}

/* ------------------------------------------------------------
   Collapsible Markdown section
------------------------------------------------------------ */
export default function MarkdownSection({
  markdown = "",
  defaultOpenFirst = true,
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
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}   /* GitHub‑flavoured markdown */
              rehypePlugins={[rehypeRaw]}   /* enable raw HTML tables    */
              components={{
                /* Custom table wrapper for styling / responsiveness */
                table: ({ node, ...props }) => (
                  <div className="lesson-table-wrapper">
                    <table className="lesson-table" {...props} />
                  </div>
                ),
              }}
            >
              {body.join("\n").trim()}
            </ReactMarkdown>
          </div>
        </details>
      ))}
    </div>
  );
}

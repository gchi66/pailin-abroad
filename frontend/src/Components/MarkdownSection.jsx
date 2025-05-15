import React from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";   // allow raw HTML (tables) in markdown
import remarkGfm from "remark-gfm";   // lists, strikethrough, tables, etc.
import "../Styles/MarkdownSection.css";

/* ------------------------------------------------------------
   Utility: split a markdown string by second‑level headings
------------------------------------------------------------ */
function splitByHeadings(markdown) {
  const sections = [];
  let current = null;

  // If no markdown or empty string, return an empty array
  if (!markdown || markdown.trim() === '') {
    return sections;
  }

  markdown.split("\n").forEach((line) => {
    if (line.startsWith("## ")) {
      if (current) sections.push(current);
      current = { title: line.slice(3).trim(), body: [] };
    } else if (current) {
      current.body.push(line);
    } else {
      // Handle content before any heading
      if (!current) {
        current = { title: "Overview", body: [line] };
      }
    }
  });

  if (current) sections.push(current);

  // If no sections were created but we have content, create a default section
  if (sections.length === 0 && markdown.trim() !== '') {
    sections.push({
      title: "Content",
      body: markdown.split("\n")
    });
  }

  return sections;
}

/* ------------------------------------------------------------
   Presentational component
------------------------------------------------------------ */
export default function MarkdownSection({
  markdown = "",
  defaultOpenFirst = true,
  extraSections = [],          // [{ key?, title, body (JSX or string) }, …]
  sectionType = "",            // Add this parameter to know the current section type
}) {
  // 1. split the incoming markdown by `##` headings
  const sections = splitByHeadings(markdown);

  // 2. Only add extra sections (like Quick Practice) if this is exactly the understand section
  let allSections = [...sections];

  // Only add extraSections if we're in the "understand" section (exact match)
  if (sectionType === "understand" && extraSections.length > 0) {
    extraSections.forEach((ex) =>
      allSections.push({
        key: ex.key ?? `extra-${sections.length}`,
        title: ex.title || "Extra",
        body: ex.body,
        preRendered: true,       // flag so we don't send through MD parser
      })
    );
  }

  return (
    <div className="markdown-section">
      {allSections.length > 0 ? (
        allSections.map(({ key, title, body, preRendered }, idx) => (
          <details
            key={key ?? idx}
            className="markdown-item"
            open={defaultOpenFirst && idx === 0}
          >
            <summary className="markdown-summary">
              {title || "More Information"}
            </summary>

            <div className="markdown-content">
              {preRendered ? (
                /* Already JSX (e.g. a Quick Practice component) */
                body
              ) : (
                /* Regular markdown gets piped through ReactMarkdown */
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}   // GitHub‑flavoured markdown
                  rehypePlugins={[rehypeRaw]}   // enable raw HTML (tables)
                  components={{
                    /* Custom table wrapper for styling / responsiveness */
                    table: ({ node, ...props }) => (
                      <div className="lesson-table-wrapper">
                        <table className="lesson-table" {...props} />
                      </div>
                    ),
                  }}
                >
                  {Array.isArray(body) ? body.join("\n").trim() : body}
                </ReactMarkdown>
              )}
            </div>
          </details>
        ))
      ) : (
        <div className="markdown-content empty-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
          >
            {markdown}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}

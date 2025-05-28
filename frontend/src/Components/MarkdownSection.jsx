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
  extraSections = [],
  sectionType = "",
}) {
  // 1. split the incoming markdown by `##` headings
  const sections = splitByHeadings(markdown);

  // 2. Insert extra sections at marker positions for "understand"
  let allSections = [...sections];
  if (sectionType === "understand" && extraSections.length > 0) {
    allSections = insertExtraSections(sections, extraSections);
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

/* ------------------------------------------------------------
   Utility: insert extra sections based on markers
------------------------------------------------------------ */
function insertExtraSections(sections, extraSections) {
  if (!extraSections || extraSections.length === 0) return sections;

  let newSections = [];

  sections.forEach((sec) => {
    let body = Array.isArray(sec.body) ? sec.body.join("\n") : sec.body;
    let workingBody = body;
    let lastTitle = sec.title;

    // Create a copy of extraSections to avoid mutating the original
    let availableExtras = [...extraSections];

    // Insert all extras whose marker is found in this section, in order
    while (true) {
      // Find the first extra whose marker is in the body
      const idx = availableExtras.findIndex((ex) => workingBody.includes(ex.marker));
      if (idx === -1) break;

      const ex = availableExtras[idx];
      const [before, after] = workingBody.split(ex.marker, 2);

      // Add the part before the marker as a section (if not empty)
      if (before && before.trim()) {
        newSections.push({
          ...sec,
          body: before,
          title: lastTitle,
        });
        lastTitle = sec.title + " (cont.)";
      }

      // Add the extra section
      newSections.push(ex);

      // Continue with the part after the marker
      workingBody = after;

      // Remove this extra from our working copy so it's not used again
      availableExtras.splice(idx, 1);
    }

    // Add any remaining body as a section
    if (workingBody && workingBody.trim()) {
      newSections.push({
        ...sec,
        body: workingBody,
        title: lastTitle,
      });
    }
  });

  return newSections;
}

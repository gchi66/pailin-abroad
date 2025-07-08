import "../Styles/LessonContent.css";
import "../Styles/MarkdownSection.css";
import AudioBullet from "./AudioBullet";

// Renders a node array from content_jsonb (headings, paragraphs, lists, etc.)
export default function RichSectionRenderer({ nodes, snipIdx }) {

  if (!Array.isArray(nodes) || nodes.length === 0) return null;

  // Group nodes by heading (for accordion/dropdown), filter out consecutive duplicate headings
  const sections = [];
  let current = null;
  let lastHeadingText = null;
  nodes.forEach((node, idx) => {
    if (node.kind === "heading") {
      const headingText = node.inlines.map((s) => s.text).join("").trim();
      if (headingText === lastHeadingText) {
        // skip duplicate consecutive heading
        return;
      }
      lastHeadingText = headingText;
      if (current) sections.push(current);
      current = { heading: node, body: [] };
    } else if (current) {
      current.body.push(node);
    }
  });
  // Only push the last section if it has content or is not a duplicate
  if (current && (current.body.length > 0 || sections.length === 0 || (current.heading && current.heading.inlines.map((s) => s.text).join("").trim() !== lastHeadingText))) {
    sections.push(current);
  }

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

  return (
    <div className="markdown-section">
      {sections.length > 0 ? (
        sections.map((sec, i) => (
          <details key={i} className="markdown-item" open={i === 0}>
            <summary className="markdown-summary">
              {sec.heading.inlines.map((span, j) => (
                <span
                  key={j}
                  style={{
                    fontWeight: span.bold ? "bold" : undefined,
                    fontStyle: span.italic ? "italic" : undefined,
                    textDecoration: span.underline ? "underline" : undefined,
                  }}
                >
                  {span.text}
                </span>
              ))}
            </summary>
            <div className="markdown-content">
              {sec.body.map((node, k) => {
                if (node.kind === "paragraph") {
                  return (
                    <p key={k} style={{ marginLeft: node.indent * 24 }}>
                      {renderInlines(node.inlines)}
                    </p>
                  );
                } else if (node.kind === "list_item") {
                  if (node.audio_seq) {
                    return (
                      <AudioBullet
                        key={k}
                        node={node}
                        indent={node.indent}
                        snipIdx={snipIdx}
                        renderInlines={renderInlines}
                      />
                    );
                  }
                  return (
                    <li key={k} style={{ marginLeft: node.indent * 24 }}>
                      {renderInlines(node.inlines)}
                    </li>
                  );
                }
                return null;
              })}
            </div>
          </details>
        ))
      ) : (
        // fallback: render all as paragraphs
        nodes.map((node, i) => (
          <p key={i} style={{ marginLeft: node.indent * 24 }}>
            {renderInlines(node.inlines)}
          </p>
        ))
      )}
    </div>
  );
}

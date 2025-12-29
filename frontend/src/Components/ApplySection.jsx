import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ApplySection.css";
import { copy, pick } from "../ui-lang/i18n";

/**
 * Renders the “Apply” section of a lesson.
 * Props
 *   content   – markdown string for the exercise prompt
 *   response  – markdown string for the optional response
 *   uiLang    – "en" | "th" (for later localisation, optional)
 */
export default function ApplySection({ content = "", response = "", uiLang = "en" }) {
  const [text, setText] = useState("");
  const [showResponse, setShowResponse] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Apply input →", text);   // placeholder for future logic
    setShowResponse(true);
  };

  return (
    <section className="apply-section">
      <div className="apply-prompt">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>

      <form className="apply-form" onSubmit={handleSubmit}>
        <textarea
          className="apply-input"
          rows={2}
          placeholder={
            uiLang === "th"
              ? "พิมพ์คำตอบของคุณที่นี่…"
              : "Type your response here…"
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <button type="submit" className="apply-submit">
          {pick(copy.lessonContent.applySubmit, uiLang)}
        </button>
      </form>

      {showResponse && response ? (
        <div className="apply-response">
          <ReactMarkdown>{response}</ReactMarkdown>
        </div>
      ) : null}
    </section>
  );
}

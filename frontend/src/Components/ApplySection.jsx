import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import "../Styles/ApplySection.css";

/**
 * Renders the “Apply” section of a lesson.
 * Props
 *   content   – markdown string for the exercise prompt
 *   uiLang    – "en" | "th" (for later localisation, optional)
 */
export default function ApplySection({ content = "", uiLang = "en" }) {
  const [text, setText] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Apply input →", text);   // placeholder for future logic
    setText("");                          // clear box for now
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
          {uiLang === "th" ? "ส่งคำตอบ" : "Submit"}
        </button>
      </form>
    </section>
  );
}

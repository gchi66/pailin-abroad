import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import RichSectionRenderer from "./RichSectionRenderer";
import "../Styles/ApplySection.css";
import { copy, pick } from "../ui-lang/i18n";

/**
 * Renders the “Apply” section of a lesson.
 * Props
 *   content   – markdown string for the exercise prompt
 *   response  – markdown string for the optional response
 *   contentLang – "en" | "th"
 */
export default function ApplySection({
  content = "",
  response = "",
  contentLang = "en",
  contentNodes = [],
  responseNodes = [],
}) {
  const [text, setText] = useState("");
  const [showResponse, setShowResponse] = useState(false);
  const hasPromptNodes = Array.isArray(contentNodes) && contentNodes.length > 0;
  const hasResponseNodes = Array.isArray(responseNodes) && responseNodes.length > 0;
  const hasResponse = Boolean((response && response.trim()) || hasResponseNodes);

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Apply input →", text);   // placeholder for future logic
    setShowResponse(true);
  };

  return (
    <section className="apply-section">
      <div className="apply-prompt apply-rich">
        {hasPromptNodes ? (
          <RichSectionRenderer
            nodes={contentNodes}
            uiLang={contentLang}
            noAccordion
            suppressBaseOffset
          />
        ) : (
          <ReactMarkdown>{content}</ReactMarkdown>
        )}
      </div>

      <form className="apply-form" onSubmit={handleSubmit}>
        <div className="apply-note">
          {pick(copy.lessonContent.applyNote, contentLang)}
        </div>
        <textarea
          className="apply-input"
          rows={2}
          placeholder={
            contentLang === "th"
              ? "พิมพ์คำตอบของคุณที่นี่…"
              : "Type your response here…"
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={showResponse}
        />

        {!showResponse ? (
          <button type="submit" className="apply-submit apply-submit--apply">
            {pick(copy.lessonContent.applySubmit, contentLang)}
          </button>
        ) : null}
      </form>

      {showResponse && hasResponse ? (
        <div className="apply-response apply-rich">
          {hasResponseNodes ? (
            <RichSectionRenderer
              nodes={responseNodes}
              uiLang={contentLang}
              noAccordion
              suppressBaseOffset
            />
          ) : (
            <ReactMarkdown>{response}</ReactMarkdown>
          )}
          <div className="apply-response-note">
            {pick(copy.lessonContent.applyResponseNote, contentLang)}
          </div>
        </div>
      ) : null}
    </section>
  );
}

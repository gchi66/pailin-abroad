import React from "react";
import ReactMarkdown from "react-markdown";
import LanguageToggle from "./LanguageToggle";
import "../Styles/LessonContent.css";
import ComprehensionQuiz from "./ComprehensionQuiz";

export default function LessonContent({
  sections = [],
  questions = [],
  transcript = [],
  activeId,
  uiLang = "en",
  setUiLang,
}) {
  // 1) Comprehension view
  if (activeId === "comprehension") {
    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">COMPREHENSION QUESTIONS</span>
          </div>
          <div className="lc-head-right">
            <LanguageToggle language={uiLang} setLanguage={setUiLang} />
          </div>
        </header>
        <ComprehensionQuiz questions={questions} uiLang={uiLang} />
      </article>
    );
  }

  // 2) Transcript view
  if (activeId === "transcript") {
    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">TRANSCRIPT</span>
          </div>
          <div className="lc-head-right">
            <LanguageToggle language={uiLang} setLanguage={setUiLang} />
          </div>
        </header>
        <ul className="transcript-list">
          {transcript.map((line) => (
            <li key={line.id}>
              <strong>{line.speaker}:</strong>{" "}
              <span>
                {uiLang === "th" && line.line_text_th
                  ? line.line_text_th
                  : line.line_text}
              </span>
            </li>
          ))}
        </ul>
      </article>
    );
  }

  // 3) Regular lesson section
  const section = sections.find((s) => s.id === activeId);
  if (!section) {
    return <article className="lc-card">Select a section</article>;
  }

  const contentText =
    uiLang === "th" && section.content_th
      ? section.content_th
      : section.content;

  return (
    <article className="lc-card">
      <header className="lc-head">
        <div className="lc-head-left">
          <span className="lc-head-title">
            {section.type.replace("_", " ").toUpperCase()}
          </span>
          {section.title_th && (
            <span className="lc-head-title-th">{section.title_th}</span>
          )}
        </div>

        <div className="lc-head-right">
          <LanguageToggle language={uiLang} setLanguage={setUiLang} />
        </div>
      </header>

      <div className="lc-body">
        <ReactMarkdown>{contentText}</ReactMarkdown>
      </div>
    </article>
  );
}

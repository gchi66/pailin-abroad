import React from "react";
import ReactMarkdown from "react-markdown";
import LanguageToggle from "./LanguageToggle";
import ComprehensionQuiz from "./ComprehensionQuiz";
import ApplySection from "./ApplySection";
import MarkdownSection from "./MarkdownSection";
import PracticeSection from "./PracticeSection";

import "../Styles/LessonContent.css";

export default function LessonContent({
  sections = [],
  questions = [],
  transcript = [],
  practiceExercises = [],
  lessonPhrases = [],
  activeId,
  uiLang = "en",
  setUiLang,
}) {
  /* ===============================================================
     1) COMPREHENSION VIEW
  =============================================================== */
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

  /* ===============================================================
     2) TRANSCRIPT VIEW
  =============================================================== */
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

  /* ===============================================================
     3) PRACTICE PAGE
  =============================================================== */
  if (activeId === "practice") {
    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">PRACTICE</span>
          </div>
          <div className="lc-head-right">
            <LanguageToggle language={uiLang} setLanguage={setUiLang} />
          </div>
        </header>

        <PracticeSection exercises={practiceExercises} uiLang={uiLang} />
      </article>
    );
  }

  /* ===============================================================
     4) PHRASES & VERBS VIEW
  =============================================================== */
  if (activeId === "phrases_verbs" && lessonPhrases.length > 0) {
    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">PHRASES & VERBS</span>
          </div>
          <div className="lc-head-right">
            <LanguageToggle language={uiLang} setLanguage={setUiLang} />
          </div>
        </header>
        <div className="lc-body">
          <ul className="phrases-verbs-list">
            {lessonPhrases.map((item, idx) => (
              <li key={item.id || idx}>
                <strong>{item.phrase}</strong>
                {item.translation && (
                  <span> &mdash; {item.translation}</span>
                )}
                {item.notes && (
                  <div className="phrase-notes" style={{ fontSize: "0.95em", color: "#666" }}>
                    {item.notes}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      </article>
    );
  }

  /* ===============================================================
     5) REGULAR LESSON SECTIONS (markdown or apply)
  =============================================================== */
  const section = sections.find((s) => s.id === activeId);
  if (!section) {
    return <article className="lc-card">Select a section</article>;
  }

  /* choose Thai or English copy */
  const contentText =
    uiLang === "th" && section.content_th
      ? section.content_th
      : section.content;

  /* ------------------ APPLY SECTION ------------------ */
  if (section.type === "apply") {
    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">APPLY</span>
          </div>
          <div className="lc-head-right">
            <LanguageToggle language={uiLang} setLanguage={setUiLang} />
          </div>
        </header>

        <ApplySection content={contentText} uiLang={uiLang} />
      </article>
    );
  }

  /* ------------------ COLLAPSIBLE MARKDOWN SECTION ------------------ */
  if (
    ["understand", "extra_tip", "culture_note", "common_mistake"].includes(
      section.type
    )
  ) {
    // Only build extraSections for "understand"
    let extraSections = [];
    if (section.type === "understand") {
      const quickExercises = practiceExercises.filter(
        (ex) =>
          (ex.title || "").toLowerCase().startsWith("quick practice") &&
          ex.sort_order
      );
      extraSections = quickExercises.map((ex, idx) => ({
        key: `quick-practice-${idx}`,
        title: ex.title || "Quick Practice",
        body: (
          <PracticeSection
            exercises={[ex]}
            uiLang={uiLang}
            hideQuick={false}
            wrapInDetails={false}
          />
        ),
        preRendered: true,
        marker: `[[QUICK_PRACTICE_${idx + 1}]]`,
      }));
    }

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
        <MarkdownSection
          markdown={contentText}
          defaultOpenFirst={section.type === "understand"}
          extraSections={extraSections}
          sectionType={section.type}
        />
      </article>
    );
  }

  /* ------------------ DEFAULT MARKDOWN SECTION -------- */
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

import React from "react";
import ReactMarkdown from "react-markdown";
import LanguageToggle from "./LanguageToggle";
import ComprehensionQuiz from "./ComprehensionQuiz";
import ApplySection from "./ApplySection";
import MarkdownSection from "./MarkdownSection";
import PracticeSection from "./PracticeSection";
import RichSectionRenderer from "./RichSectionRenderer";

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
  snipIdx = {},
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
  if (activeId === "phrases_verbs") {
    // Only include phrases with non-empty content_md or content
    const filteredPhrases = lessonPhrases.filter(
      (item) =>
        (item.content_md && item.content_md.trim() !== "") ||
        (item.content && item.content.trim() !== "")
    );

    if (filteredPhrases.length === 0) {
      // Hide the PHRASES & VERBS view entirely if there are no phrases/verbs
      return null;
    }

    const phrasesMarkdown = filteredPhrases
      .map(
        (item) =>
          `## ${item.phrase}\n${item.content_md ? item.content_md.trim() : item.content ? item.content.trim() : ""}`
      )
      .join("\n\n");

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
        <MarkdownSection
          markdown={phrasesMarkdown}
          defaultOpenFirst={false}
          sectionType="phrases_verbs"
        />
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
   /* choose markdown or plaintext*/
  const contentText =
    section.content_md && section.content_md.trim() !== ""
      ? section.content_md
      : (uiLang === "th" && section.content_th
          ? section.content_th
          : section.content);

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

    // --- RICH CONTENT RENDERING ---
    if (Array.isArray(section.content_jsonb) && section.content_jsonb.length > 0) {
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
          <RichSectionRenderer nodes={section.content_jsonb} snipIdx={snipIdx} />
          {/* Render extraSections (e.g., quick practice) below rich content if present */}
          {extraSections.length > 0 && (
            <div className="extra-sections">
              {extraSections.map((ex) => (
                <div key={ex.key}>{ex.body}</div>
              ))}
            </div>
          )}
        </article>
      );
    }
    // --- FALLBACK TO MARKDOWN ---
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

      <MarkdownSection
        markdown={contentText}
        defaultOpenFirst={true}      // open immediately (no accordion needed)
        sectionType={section.type}   // keeps future-proof options
      />
    </article>
  );
}

import React from "react";
import ReactMarkdown from "react-markdown";
import LessonLanguageToggle from "./LessonLanguageToggle";
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
  snipIdx = {},
  contentLang = "en",
  setContentLang,
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
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
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
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
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
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </header>

        <PracticeSection exercises={practiceExercises} uiLang={uiLang} />
      </article>
    );
  }

/* ===============================================================
   4) PHRASES & VERBS VIEW (rich)
=============================================================== */
if (activeId === "phrases_verbs") {
  // Prefer reading from the "sections" shape if available; otherwise use lessonPhrases
  const phrasesSection = Array.isArray(sections)
    ? sections.find((s) => s?.type === "phrases_verbs")
    : null;

  const rawItems = (phrasesSection?.items ?? lessonPhrases ?? []).filter(Boolean);

  // Keep only items that actually have something to render
  const items = rawItems.filter((item) =>
    (Array.isArray(item.content_jsonb) && item.content_jsonb.length > 0) ||
    (item.content_md && item.content_md.trim() !== "") ||
    (item.content && item.content.trim() !== "")
  );

  if (items.length === 0) return null;

  return (
    <article className="lc-card">
      <header className="lc-head">
        <div className="lc-head-left">
          <span className="lc-head-title">PHRASES & VERBS</span>
        </div>
        <div className="lc-head-right">
          <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
        </div>
      </header>

      <div className="markdown-section">
        {items.map((item, idx) => {
            const hasRich = Array.isArray(item.content_jsonb) && item.content_jsonb.length > 0;
            const md = item.content_md?.trim?.() || item.content?.trim?.() || "";

            // Show phrase_th if contentLang is 'th', otherwise phrase
            const phraseLabel = contentLang === "th"
              ? item.phrase_th || item.phrase || "Phrase"
              : item.phrase || "Phrase";

            return (
              <details key={idx} className="markdown-item" open={idx === 0}>
                <summary className="markdown-summary">
                  {phraseLabel}
                  {/* Optional: add a ▶ play button later by mapping (section,seq)->snipIdx */}
                </summary>

                <div className="markdown-content">
                  {hasRich ? (
                    <RichSectionRenderer
                      nodes={item.content_jsonb}
                      snipIdx={snipIdx}
                      uiLang={uiLang}
                    />
                  ) : md ? (
                    <MarkdownSection
                      markdown={md}
                      defaultOpenFirst={false}
                      sectionType="phrases_verbs_item"
                    />
                  ) : null}
                </div>
              </details>
            );
        })}
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
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
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
    // --- RICH CONTENT RENDERING ---
    if (Array.isArray(section.content_jsonb) && section.content_jsonb.length > 0) {
      // Get quick practice exercises for "understand" sections only
      let quickExercises = [];
      if (section.type === "understand") {
        quickExercises = practiceExercises.filter(
          (ex) =>
            (ex.title || "").toLowerCase().startsWith("quick practice") &&
            ex.sort_order
        );
      }

      // Process content to insert Quick Practice exercises inline
      const processedContent = [];
      let quickPracticeIndex = 0;

      for (let i = 0; i < section.content_jsonb.length; i++) {
        const node = section.content_jsonb[i];

        // Check if this is a Quick Practice heading
        const isQuickPracticeHeading =
          node.kind === 'heading' &&
          node.inlines?.some(inline =>
            inline.text?.toLowerCase().includes('quick practice'));

        if (isQuickPracticeHeading && quickPracticeIndex < quickExercises.length) {
          // Add the heading
          processedContent.push(node);

          // Add the corresponding practice exercise right after the heading
          processedContent.push({
            kind: 'quick_practice_exercise',
            exercise: quickExercises[quickPracticeIndex],
            key: `quick-practice-${quickPracticeIndex}`
          });

          quickPracticeIndex++;
        } else {
          // Skip any content that appears to be exercise data
          const isExerciseContent =
            node.type === 'exercise' ||
            node.title?.toLowerCase().includes('quick practice') ||
            (node.kind === 'paragraph' &&
             node.inlines?.some(inline =>
               inline.text?.includes('TYPE:') ||
               inline.text?.includes('STEM:') ||
               inline.text?.includes('ANSWER:') ||
               inline.text?.includes('QUESTION:')
             ));

          if (!isExerciseContent) {
            processedContent.push(node);
          }
        }
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
              <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
            </div>
          </header>
          <RichSectionRenderer
            nodes={processedContent}
            snipIdx={snipIdx}
            uiLang={uiLang}
            renderQuickPractice={(exercise) => (
              <PracticeSection
                exercises={[exercise]}
                uiLang={uiLang}
                hideQuick={false}
                wrapInDetails={false}
              />
            )}
          />
        </article>
      );
    }

    // --- FALLBACK TO MARKDOWN ---
    // Only build extraSections for "understand" when using markdown fallback
    let extraSections = [];
    if (section.type === "understand") {
      const quickExercises = practiceExercises.filter(
        (ex) =>
          (ex.title || "").toLowerCase().startsWith("quick practice") &&
          ex.sort_order
      );
      extraSections = quickExercises.map((ex, idx) => ({
        key: `quick-practice-${idx}`,
        title: ex.title || "Quick Practice 1",
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
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
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
          <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
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

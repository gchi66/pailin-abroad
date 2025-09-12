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
     HELPER: Section header by contentLang
  =============================================================== */
  const getSectionHeader = (section, fallbackText) => {
    if (contentLang === "th") {
      return (
        section.title_th?.trim() ||
        section.text?.th?.trim() ||
        section.header_th?.trim() ||
        fallbackText
      );
    } else {
      return (
        section.title?.trim() ||
        section.text?.en?.trim() ||
        section.header_en?.trim() ||
        fallbackText
      );
    }
  };

  /* ===============================================================
     HELPER: choose nodes by language; for TH, swap heading inlines to text_th
  =============================================================== */
  const selectNodesForLang = (nodesEN = [], nodesTH = [], lang = "en") => {
    // prefer TH nodes if present; else fall back to EN nodes
    const base =
      lang === "th" && Array.isArray(nodesTH) && nodesTH.length > 0
        ? nodesTH
        : Array.isArray(nodesEN)
        ? nodesEN
        : [];

    if (lang !== "th") return base;

    // helpers to split combined EN+TH strings
    const takeThai = (s = "") => {
      const m = s.match(/[\u0E00-\u0E7F].*$/); // first Thai char to end
      return m ? m[0].trim() : "";
    };

    return base.map((node) => {
      if (!node || node.kind !== "heading" || !Array.isArray(node.inlines)) {
        return node;
      }

      // 1) if node has a localized text map, prefer that
      const thFromNode = node.text?.th?.trim?.();
      if (thFromNode) {
        return {
          ...node,
          inlines: node.inlines.map((inl, idx) => ({
            ...inl,
            // put TH on the first inline; blank the rest to avoid duplicating
            text: idx === 0 ? thFromNode : "",
          })),
        };
      }

      // 2) otherwise, try to extract Thai from the existing combined inline text(s)
      return {
        ...node,
        inlines: node.inlines.map((inl, idx) => {
          const src = inl?.text || "";
          const th = takeThai(src);
          return { ...inl, text: idx === 0 ? th : "" };
        }),
      };
    });
  };

  /* ===============================================================
     1) COMPREHENSION VIEW
  =============================================================== */
  if (activeId === "comprehension") {
    const comprehensionSection = sections.find((s) => s.type === "comprehension");
    const headerText = comprehensionSection
      ? getSectionHeader(comprehensionSection, "COMPREHENSION QUESTIONS")
      : "COMPREHENSION QUESTIONS";

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
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
    const transcriptSection = sections.find((s) => s.type === "transcript");
    const headerText = transcriptSection
      ? getSectionHeader(transcriptSection, "TRANSCRIPT")
      : "TRANSCRIPT";

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
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
                {uiLang === "th" && line.line_text_th ? line.line_text_th : line.line_text}
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
    const practiceSection = sections.find((s) => s.type === "practice");
    const headerText = practiceSection ? getSectionHeader(practiceSection, "PRACTICE") : "PRACTICE";

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
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
     4) PHRASES & VERBS VIEW (rich) - with working audio
  =============================================================== */
  if (activeId === "phrases_verbs") {
    const phrasesSection = Array.isArray(sections)
      ? sections.find((s) => s?.type === "phrases_verbs")
      : null;

    const rawItems = (phrasesSection?.items ?? lessonPhrases ?? []).filter(Boolean);

    // keep items that have something to render in either lang
    const items = rawItems.filter(
      (item) =>
        (Array.isArray(item.content_jsonb) && item.content_jsonb.length > 0) ||
        (Array.isArray(item.content_jsonb_th) && item.content_jsonb_th.length > 0) ||
        (item.content_md && item.content_md.trim() !== "") ||
        (item.content && item.content.trim() !== "")
    );

    if (items.length === 0) return null;

    const headerText = phrasesSection
      ? getSectionHeader(phrasesSection, "PHRASES & VERBS")
      : "PHRASES & VERBS";

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
          </div>
          <div className="lc-head-right">
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </header>

        <div className="markdown-section">
          {items.map((item, idx) => {
            const nodesToRender = selectNodesForLang(
              item.content_jsonb,
              item.content_jsonb_th,
              contentLang
            );
            const hasRich = nodesToRender.length > 0;
            const md = item.content_md?.trim?.() || item.content?.trim?.() || "";

            const phraseLabel =
              contentLang === "th"
                ? item.phrase_th?.trim() || item.phrase || "Phrase"
                : item.phrase || "Phrase";

            return (
              <details key={idx} className="markdown-item" open={idx === 0}>
                <summary className="markdown-summary">
                  {phraseLabel}
                  {snipIdx?.["phrases_verbs"] &&
                    Object.keys(snipIdx["phrases_verbs"]).length > 0 && (
                      <span className="audio-indicator"> ▶</span>
                    )}
                </summary>

                <div className="markdown-content">
                  {hasRich ? (
                    <RichSectionRenderer
                      nodes={nodesToRender}
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

  // choose Thai or English copy for plain/markdown content
  const contentText =
    section.content_md && section.content_md.trim() !== ""
      ? section.content_md
      : uiLang === "th" && section.content_th
      ? section.content_th
      : section.content;

  /* ------------------ APPLY SECTION ------------------ */
  if (section.type === "apply") {
    const headerText = getSectionHeader(section, "APPLY");

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
          </div>
          <div className="lc-head-right">
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </header>

        <ApplySection content={contentText} uiLang={uiLang} />
      </article>
    );
  }

  /* ------------------ COLLAPSIBLE RICH/MARKDOWN SECTION ------------------ */
  const hasRichEN = Array.isArray(section.content_jsonb) && section.content_jsonb.length > 0;
  const hasRichTH =
    Array.isArray(section.content_jsonb_th) && section.content_jsonb_th.length > 0;

  if (hasRichEN || hasRichTH) {
    const baseNodes = selectNodesForLang(
      section.content_jsonb,
      section.content_jsonb_th,
      contentLang
    );

    // Get quick practice exercises for "understand" sections only
    let quickExercises = [];
    if (section.type === "understand") {
      quickExercises = practiceExercises.filter(
        (ex) => (ex.title || "").toLowerCase().startsWith("quick practice") && ex.sort_order
      );
    }

    // Process content to insert Quick Practice exercises inline
    const processedContent = [];
    let quickPracticeIndex = 0;

    for (let i = 0; i < baseNodes.length; i++) {
      const node = baseNodes[i];

      // Check if this is a Quick Practice heading
      const isQuickPracticeHeading =
        node.kind === "heading" &&
        node.inlines?.some((inline) => inline.text?.toLowerCase().includes("quick practice"));

      if (isQuickPracticeHeading && quickPracticeIndex < quickExercises.length) {
        processedContent.push(node);
        processedContent.push({
          kind: "quick_practice_exercise",
          exercise: quickExercises[quickPracticeIndex],
          key: `quick-practice-${quickPracticeIndex}`,
        });
        quickPracticeIndex++;
      } else {
        // Skip any content that appears to be exercise data
        const isExerciseContent =
          node.type === "exercise" ||
          node.title?.toLowerCase().includes("quick practice") ||
          (node.kind === "paragraph" &&
            node.inlines?.some((inline) =>
              ["TYPE:", "STEM:", "ANSWER:", "QUESTION:"].some((kw) => inline.text?.includes(kw))
            ));
        if (!isExerciseContent) {
          processedContent.push(node);
        }
      }
    }

    const defaultHeaderText = section.type.replace("_", " ").toUpperCase();
    const headerText = getSectionHeader(section, defaultHeaderText);

    return (
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
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

  /* ------------------ DEFAULT MARKDOWN SECTION -------- */
  const defaultHeaderText = section.type.replace("_", " ").toUpperCase();
  const headerText = getSectionHeader(section, defaultHeaderText);

  return (
    <article className="lc-card">
      <header className="lc-head">
        <div className="lc-head-left">
          <span className="lc-head-title">{headerText}</span>
        </div>
        <div className="lc-head-right">
          <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
        </div>
      </header>

      <MarkdownSection
        markdown={contentText}
        defaultOpenFirst={true}
        sectionType={section.type}
      />
    </article>
  );
}

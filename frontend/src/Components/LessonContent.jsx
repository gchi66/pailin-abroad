import React, { useCallback, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import LessonLanguageToggle from "./LessonLanguageToggle";
import ComprehensionQuiz from "./ComprehensionQuiz";
import ApplySection from "./ApplySection";
import MarkdownSection from "./MarkdownSection";
import PracticeSection from "./PracticeSection";
import RichSectionRenderer from "./RichSectionRenderer";
import CollapsibleDetails from "./CollapsibleDetails";

import "../Styles/LessonContent.css";
import { copy, pick } from "../ui-lang/i18n";

export default function LessonContent({
  sections = [],
  questions = [],
  transcript = [],
  practiceExercises = [],
  lessonPhrases = [],
  activeId,
  sectionMenu = [],
  uiLang = "en",
  snipIdx = {},
  phrasesSnipIdx = {},
  contentLang = "en",
  setContentLang,
  images = {},
  isLocked = false,
  registerStickyHeaders,
  onSelectSection,
}) {
  const fallbacks = copy.lessonPage.sectionFallbacks;
  const lockedCopy = copy.lessonPage.locked;
  const getFallbackHeader = (sectionType, defaultText) => {
    const fb =
      fallbacks?.[sectionType] ||
      (sectionType === "phrases_verbs" ? fallbacks?.phrasesVerbs : null) ||
      (sectionType === "extra_tip" ? fallbacks?.extraTip : null) ||
      (sectionType === "common_mistake" ? fallbacks?.commonMistake : null) ||
      (sectionType === "understand" ? fallbacks?.understand : null) ||
      (sectionType === "culture_note" ? fallbacks?.cultureNote : null);
    return fb ? pick(fb, contentLang) : defaultText;
  };
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
    const base =
      lang === "th" && Array.isArray(nodesTH) && nodesTH.length > 0
        ? nodesTH
        : Array.isArray(nodesEN)
        ? nodesEN
        : [];

    // Always normalize headings when Thai mode is active
    if (lang === "th") {
      return base.map((node) => {
        if (!node || node.kind !== "heading") return node;

        const thText =
          node.text?.th?.trim?.() ||
          node.text_th?.trim?.() ||
          node.header_th?.trim?.() ||
          "";

        // Replace inline text even if TH text already exists
        if (thText) {
          return {
            ...node,
            inlines: [
              {
                ...(node.inlines?.[0] || {}),
                text: thText,
              },
            ],
          };
        }

        return node;
      });
    }

    return base;
  };

  const handleBackToTop = () => {
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const BackToTopButton = () => (
    <div className="lesson-back-to-top-wrapper">
      <button
        type="button"
        className="lesson-back-to-top"
        onClick={handleBackToTop}
      >
        <span className="lesson-back-to-top-label">BACK TO TOP</span>
        <span aria-hidden="true" className="lesson-back-to-top-arrow">
          ▸
        </span>
      </button>
    </div>
  );

  const SectionNav = () => {
    if (!Array.isArray(sectionMenu) || !sectionMenu.length) return null;
    const idx = sectionMenu.findIndex((item) => item.id === activeId);
    if (idx === -1) return null;
    const prev = idx > 0 ? sectionMenu[idx - 1] : null;
    const next = idx < sectionMenu.length - 1 ? sectionMenu[idx + 1] : null;
    if (!prev && !next) return null;

    const handleSelect = (id) => {
      if (typeof onSelectSection === "function") {
        onSelectSection(id);
      }
    };

    return (
      <nav className="lc-section-nav" aria-label="Section navigation">
        <div className="lc-section-nav-item lc-section-nav-prev">
          {prev ? (
            <button
              type="button"
              className="lc-section-nav-btn"
              onClick={() => handleSelect(prev.id)}
            >
              <span aria-hidden="true">←</span>
              <span className="lc-section-nav-label">{prev.label}</span>
            </button>
          ) : (
            <span aria-hidden="true" />
          )}
        </div>
        <div className="lc-section-nav-item lc-section-nav-next">
          {next ? (
            <button
              type="button"
              className="lc-section-nav-btn"
              onClick={() => handleSelect(next.id)}
            >
              <span className="lc-section-nav-label">{next.label}</span>
              <span aria-hidden="true">→</span>
            </button>
          ) : (
            <span aria-hidden="true" />
          )}
        </div>
      </nav>
    );
  };

  const shellRef = useRef(null);

  useEffect(() => {
    if (typeof registerStickyHeaders !== "function") return undefined;
    const container = shellRef.current;
    const heads = container
      ? Array.from(container.querySelectorAll(".lc-head"))
      : [];
    const headerNode =
      typeof document !== "undefined"
        ? document.querySelector('[data-sticky-head-id="lesson-header"]')
        : null;
    const nodes = headerNode ? [headerNode, ...heads] : heads;

    registerStickyHeaders(nodes);
    return () => {
      registerStickyHeaders([]);
    };
  }, [
    registerStickyHeaders,
    sections,
    questions,
    transcript,
    practiceExercises,
    lessonPhrases,
    activeId,
    isLocked,
  ]);

  const renderWithBackToTop = (contentNode) => {
    if (!React.isValidElement(contentNode)) return contentNode;
    const cardWithNav = React.cloneElement(
      contentNode,
      {},
      <>
        {contentNode.props.children}
        <SectionNav />
      </>
    );

    return (
      <div className="lesson-content-shell" ref={shellRef}>
        {cardWithNav}
        <BackToTopButton />
      </div>
    );
  };


  /* ===============================================================
     LOCKED LESSON CHECK
  =============================================================== */
  if (isLocked) {
    return (
      <div className="lesson-locked-container" ref={shellRef}>
        <div className="lesson-content-blurred">
          <div className="lesson-locked-placeholder">
            <h3>{pick(lockedCopy.previewTitle, uiLang)}</h3>
            <p>{pick(lockedCopy.previewBody, uiLang)}</p>
          </div>
        </div>
        <div className="lesson-locked-overlay">
          <div className="lesson-locked-message">
            <img
              src="/images/lock.webp"
              alt="Locked"
              className="lesson-locked-icon"
            />
            <h2>{pick(lockedCopy.overlayTitle, uiLang)}</h2>
            <p>{pick(lockedCopy.overlayBody, uiLang)}</p>
            <div className="lesson-locked-cta-buttons">
              <Link to="/signup" className="lesson-locked-signup-btn">
                {pick(lockedCopy.ctaSignUp, uiLang)}
              </Link>
              <Link to="/membership" className="lesson-locked-member-btn">
                {pick(lockedCopy.ctaBecomeMember, uiLang)}
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ===============================================================
     1) COMPREHENSION VIEW
  =============================================================== */
  if (activeId === "comprehension") {
    const comprehensionSection = sections.find((s) => s.type === "comprehension");
    const headerText = comprehensionSection
      ? getSectionHeader(comprehensionSection, pick(fallbacks.comprehension, contentLang))
      : pick(fallbacks.comprehension, contentLang);

    return renderWithBackToTop(
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
          </div>
          <div className="lc-head-right">
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </header>

        <ComprehensionQuiz questions={questions} uiLang={uiLang} images={images} />
      </article>
    );
  }

  /* ===============================================================
     2) TRANSCRIPT VIEW
  =============================================================== */
  if (activeId === "transcript") {
    const transcriptSection = sections.find((s) => s.type === "transcript");
    const headerText = transcriptSection
      ? getSectionHeader(transcriptSection, pick(fallbacks.transcript, contentLang))
      : pick(fallbacks.transcript, contentLang);

    return renderWithBackToTop(
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
          {transcript.map((line) => {
            const englishLine = (line.line_text || "").trim();
            const thaiLine = (line.line_text_th || "").trim();
            const speaker = (line.speaker || "").trim();
            const speakerTh = (line.speaker_th || "").trim();

            return (
              <li key={line.id} className="transcript-item">
                <div className="transcript-line-group">
                  {englishLine.length > 0 && (
                    <div className="transcript-line transcript-line-en">
                      {speaker && (
                        <span className="transcript-speaker">
                          {speaker}:
                        </span>
                      )}
                      <span className="transcript-text">{englishLine}</span>
                    </div>
                  )}
                  {contentLang === "th" && thaiLine.length > 0 && (
                    <div className="transcript-line transcript-line-th">
                      {speakerTh && (
                        <span className="transcript-speaker">
                          {speakerTh}:
                        </span>
                      )}
                      <span className="transcript-text">{thaiLine}</span>
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </article>
    );
  }

  /* ===============================================================
     3) PRACTICE PAGE
  =============================================================== */
  if (activeId === "practice") {
    const practiceSection = sections.find((s) => s.type === "practice");
    const headerText = practiceSection
      ? getSectionHeader(practiceSection, pick(fallbacks.practice, contentLang))
      : pick(fallbacks.practice, contentLang);

    return renderWithBackToTop(
      <article className="lc-card">
        <header className="lc-head">
          <div className="lc-head-left">
            <span className="lc-head-title">{headerText}</span>
          </div>
          <div className="lc-head-right">
            <LessonLanguageToggle contentLang={contentLang} setContentLang={setContentLang} />
          </div>
        </header>

        <PracticeSection
          exercises={practiceExercises.filter((ex) => !ex?.isQuickPractice)}
          uiLang={uiLang}
          images={images}
          audioIndex={snipIdx}
          contentLang={contentLang}
        />
      </article>
    );
  }

  /* ===============================================================
     4) PHRASES & VERBS VIEW
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
      ? getSectionHeader(phrasesSection, pick(fallbacks.phrasesVerbs, contentLang))
      : pick(fallbacks.phrasesVerbs, contentLang);

    return renderWithBackToTop(
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
            // Use the same logic as regular sections - don't use selectNodesForLang
            const hasRichEN = Array.isArray(item.content_jsonb) && item.content_jsonb.length > 0;
            const hasRichTH = Array.isArray(item.content_jsonb_th) && item.content_jsonb_th.length > 0;

            let nodesToRender = [];

            if (hasRichEN || hasRichTH) {
              // For Thai content, prefer the merged TH nodes if available, otherwise use EN
              if (contentLang === "th" && hasRichTH) {
                nodesToRender = item.content_jsonb_th;
              } else if (hasRichEN) {
                nodesToRender = item.content_jsonb;
              } else if (hasRichTH) {
                // Fallback to TH if EN is not available
                nodesToRender = item.content_jsonb_th;
              }
            }

            const hasRich = nodesToRender.length > 0;
            const md = item.content_md?.trim?.() || item.content?.trim?.() || "";

            const phraseLabel = (() => {
              const enPhrase = item.phrase?.trim();
              const thPhrase = item.phrase_th?.trim();
              // Keep headers in English, falling back to other data when necessary
              return enPhrase || thPhrase || "Phrase";
            })();

            return (
              <CollapsibleDetails
                key={idx}
                className="markdown-item"
                defaultOpen={idx === 0}
                summaryContent={
                  <>
                    {phraseLabel}
                    {phrasesSnipIdx?.idx?.[item.id] &&
                      Object.keys(phrasesSnipIdx.idx[item.id]).length > 0 && (
                        <span className="audio-indicator"> </span>
                      )}
                  </>
                }
              >
                <div className="markdown-content">
                  {hasRich ? (
                    <RichSectionRenderer
                      nodes={nodesToRender}
                      snipIdx={snipIdx}
                      phrasesSnipIdx={phrasesSnipIdx}
                      phraseId={item.id}
                      phraseVariant={item.variant || 0}
                      isPhrasesSection={true}
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
              </CollapsibleDetails>
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
    const headerText = getSectionHeader(section, getFallbackHeader("apply", "APPLY"));

    return renderWithBackToTop(
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
    console.log("Debug selectNodesForLang input:", {
      contentLang,
      hasRichEN,
      hasRichTH,
      section_type: section.type,
      content_jsonb_length: section.content_jsonb?.length || 0,
      content_jsonb_th_length: section.content_jsonb_th?.length || 0,
      first_few_en_nodes: section.content_jsonb?.slice(0, 3).map(n => ({ kind: n.kind, text: n.inlines?.[0]?.text?.substring(0, 30) })),
      first_few_th_nodes: section.content_jsonb_th?.slice(0, 3).map(n => ({ kind: n.kind, text: n.inlines?.[0]?.text?.substring(0, 30) }))
    });

    const baseNodes = selectNodesForLang(
      section.content_jsonb,
      section.content_jsonb_th,
      contentLang
    );

    console.log("baseNodes after selectNodesForLang:", baseNodes.slice(0, 10).map((n, i) => ({
      index: i,
      kind: n.kind,
      text: n.inlines?.[0]?.text?.substring(0, 50),
      full_node: i === 8 ? n : undefined
    })));

    // Get quick practice exercises for "understand" sections only
    let quickExercises = [];
    if (section.type === "understand") {
      quickExercises = practiceExercises.filter((ex) => {
        if (!ex || !ex.sort_order) return false;
        if (ex.isQuickPractice) return true;
        const title_th = ex.title_th || "";
        return title_th.includes("แบบฝึกหัด");
      });
    }

    // Process content to insert Quick Practice exercises inline
    const processedContent = [];
    let quickPracticeIndex = 0;


    for (let i = 0; i < baseNodes.length; i++) {
      const node = baseNodes[i];

      // Check if this is a Quick Practice heading
      const isQuickPracticeHeading =
        node.kind === "heading" &&
        (() => {
          const pieces = [
            node.text?.en,
            node.text?.th,
            node.header_en,
            node.header_th,
            ...(node.inlines || []).map((inl) => inl?.text),
          ].filter(Boolean);

          // We check English "quick practice" and Thai roots.
          return pieces.some((raw) => {
            const t = String(raw);
            const tl = t.toLowerCase(); // safe for Thai, just no-ops
            return (
              tl.includes("quick practice") ||
              t.includes("แบบฝึกหัด") ||
              t.includes("ฝึกหัด")
            );
          });
        })();
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

        // ADD THIS DEBUG LOG:
    console.log("DEBUG processedContent:", {
      contentLang,
      totalNodes: processedContent.length,
      quickPracticeNodes: processedContent.filter(n => n.kind === "quick_practice_exercise"),
      allNodeKinds: processedContent.map((n, i) => ({ index: i, kind: n.kind, text: n.inlines?.[0]?.text?.substring(0, 30) }))
    });

    const defaultHeaderText = getFallbackHeader(
      section.type,
      section.type.replace("_", " ").toUpperCase()
    );
    const headerText = getSectionHeader(section, defaultHeaderText);

    return renderWithBackToTop(
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
              images={images}
              audioIndex={snipIdx}
              contentLang={contentLang}
            />
          )}
        />
      </article>
    );
  }

  /* ------------------ DEFAULT MARKDOWN SECTION -------- */
  const defaultHeaderText = getFallbackHeader(
    section.type,
    section.type.replace("_", " ").toUpperCase()
  );
  const headerText = getSectionHeader(section, defaultHeaderText);

  return renderWithBackToTop(
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

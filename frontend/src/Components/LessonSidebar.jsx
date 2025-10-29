import React from "react";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import "../Styles/LessonSidebar.css";

const LABEL_KEY_MAP = {
  comprehension: "lessonSidebar.labels.comprehension",
  transcript: "lessonSidebar.labels.transcript",
  apply: "lessonSidebar.labels.apply",
  understand: "lessonSidebar.labels.understand",
  extra_tip: "lessonSidebar.labels.extra_tip",
  common_mistake: "lessonSidebar.labels.common_mistake",
  phrases_verbs: "lessonSidebar.labels.phrases_verbs",
  culture_note: "lessonSidebar.labels.culture_note",
  practice: "lessonSidebar.labels.practice",
};

// The exact order you want in every lesson
const MASTER_ORDER = [
  "comprehension",
  "transcript",
  "apply",
  "understand",
  "extra_tip",
  "common_mistake",
  "phrases_verbs",
  "culture_note",
  "practice",
];

function getLessonHeader(lesson, uiLang) {
  const lessonLabel = t("lessonSidebar.lessonLabel", uiLang) || "LESSON";
  const checkpointLabel = t("lessonSidebar.checkpoint", uiLang) || "CHECKPOINT";

  if (!lesson) return `${lessonLabel} –`;
  const externalId = lesson.external_id || "";
  // Check for checkpoint: external_id ends with .chp or lesson_order === 0
  if (externalId.endsWith(".chp") || lesson.lesson_order === 0) {
    return checkpointLabel;
  }
  // Try to extract the lesson number from external_id (e.g., 1.14 -> 14)
  const match = externalId.match(/^(\d+)\.(\d+)$/);
  if (match) {
    return `${lessonLabel} ${parseInt(match[2], 10)}`;
  }
  // Fallback to lesson_order if available
  if (lesson.lesson_order) {
    return `${lessonLabel} ${lesson.lesson_order}`;
  }
  return `${lessonLabel} –`;
}

export default function LessonSidebar({
  sections = [],
  questions = [],
  transcript = [],
  practiceExercises = [],
  lessonPhrases = [],
  activeId,
  onSelect,
  lesson, // <-- new prop
  isLocked = false, // <-- add isLocked prop
}) {
  const { ui: uiLang } = useUiLang();

  const getLabel = (type) => {
    const key = LABEL_KEY_MAP[type];
    if (!key) return (type || "").toUpperCase();
    const translated = t(key, uiLang);
    if (translated) return translated;
    return (type || "").toUpperCase();
  };

  // For locked lessons, show all sections in MASTER_ORDER
  // For unlocked lessons, only show sections with content
  const menuItems = MASTER_ORDER
    .map((type) => {
      // If locked, show everything
      if (isLocked) {
        // Return a menu item for each type, using a generated ID
        return { id: type, type };
      }

      // Unlocked lesson - use existing logic
      if (type === "comprehension" && questions.length) {
        return { id: "comprehension", type };
      }
      if (type === "transcript" && transcript.length) {
        return { id: "transcript", type };
      }
      if (type === "practice" && practiceExercises.length) {
        return { id: "practice", type };
      }
      if (type === "phrases_verbs") {
        // Only show if there are phrases/verbs with non-empty content or content_md
        const hasPhrases = lessonPhrases.some(
          (item) =>
            (item.content_md && item.content_md.trim() !== "") ||
            (item.content && item.content.trim() !== "")
        );
        if (hasPhrases) {
          return { id: "phrases_verbs", type };
        }
        return null;
      }
      const sec = sections.find((s) => s.type === type);
      return sec ? { id: sec.id, type } : null;
    })
    .filter(Boolean);

  return (
    <aside className="ls-sidebar">
      <header className="ls-header">
        {getLessonHeader(lesson, uiLang)}
      </header>
      <ul className="ls-list">
        {menuItems.map((item) => (
          <li
            key={item.id}
            className={`ls-row ${item.id === activeId ? "ls-active" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <span className="ls-row-label">
              {getLabel(item.type)}
            </span>
            {item.id === activeId && (
              <span className="ls-row-check">✔︎</span>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}

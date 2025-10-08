import React from "react";
import "../Styles/LessonSidebar.css";

const LABELS = {
  comprehension:  "COMPREHENSION",
  transcript:     "TRANSCRIPT",
  apply:          "APPLY",
  understand:     "UNDERSTAND",
  extra_tip:      "EXTRA TIPS",
  common_mistake: "COMMON MISTAKES",
  phrases_verbs:  "PHRASES & VERBS",
  culture_note:   "CULTURE NOTE",
  practice:       "PRACTICE",
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

function getLessonHeader(lesson) {
  if (!lesson) return "LESSON –";
  const externalId = lesson.external_id || "";
  // Check for checkpoint: external_id ends with .chp or lesson_order === 0
  if (externalId.endsWith(".chp") || lesson.lesson_order === 0) {
    return "Checkpoint";
  }
  // Try to extract the lesson number from external_id (e.g., 1.14 -> 14)
  const match = externalId.match(/^(\d+)\.(\d+)$/);
  if (match) {
    return `LESSON ${parseInt(match[2], 10)}`;
  }
  // Fallback to lesson_order if available
  if (lesson.lesson_order) {
    return `LESSON ${lesson.lesson_order}`;
  }
  return "LESSON –";
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
        {getLessonHeader(lesson)}
      </header>
      <ul className="ls-list">
        {menuItems.map((item) => (
          <li
            key={item.id}
            className={`ls-row ${item.id === activeId ? "ls-active" : ""}`}
            onClick={() => onSelect(item.id)}
          >
            <span className="ls-row-label">
              {LABELS[item.type] || item.type.toUpperCase()}
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

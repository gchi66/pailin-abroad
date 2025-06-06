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

export default function LessonSidebar({
  sections = [],
  questions = [],
  transcript = [],
  practiceExercises = [],
  lessonPhrases = [],
  activeId,
  onSelect,
}) {
  // Build the menu in the master order, skipping types with no data
  const menuItems = MASTER_ORDER
    .map((type) => {
      if (type === "comprehension" && questions.length) {
        return { id: "comprehension", type };
      }
      if (type === "transcript" && transcript.length) {
        return { id: "transcript", type };
      }
      if (type === "practice" && practiceExercises.length) {   // ②  PRACTICE GATE
        return { id: "practice", type };
      }
      if (type === "phrases_verbs" && lessonPhrases.length) {
        // <-- Add this block
        return { id: "phrases_verbs", type };
      }
      const sec = sections.find((s) => s.type === type);
      return sec ? { id: sec.id, type } : null;
    })
    .filter(Boolean);

  return (
    <aside className="ls-sidebar">
      <header className="ls-header">
        LESSON {sections[0]?.sort_order ?? "–"}
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

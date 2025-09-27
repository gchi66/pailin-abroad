import React from "react";
import FillBlankExercise from "./ExerciseTypes/FillBlankExercise";
import MultipleChoiceExercise from "./ExerciseTypes/MultipleChoiceExercise";
import OpenEndedExercise from "./ExerciseTypes/OpenEndedExercise";
import SentenceTransformExercise from "./ExerciseTypes/SentenceTransformExercise";

import "../Styles/PracticeSection.css";

// map normalized "exercise_type" (or DB "kind") to component
const kindToComponent = {
  fill_blank: FillBlankExercise,
  multiple_choice: MultipleChoiceExercise,
  open: OpenEndedExercise,
  open_ended: OpenEndedExercise,         // tolerate alias
  sentence_transform: SentenceTransformExercise,
};

// tiny helpers
const arr = (v) => (Array.isArray(v) ? v : []);
const textOr = (a, b, c) => a ?? b ?? c ?? "";

// accept BOTH the raw DB row shape and the normalized row shape
const transformExercise = (row) => {
  const kind = row.exercise_type || row.kind || null;

  // prefer normalized fields; fall back to DB ones
  const items = arr(row.items);
  const options = arr(row.options);
  const answer_key = row.answer_key || {}; // object for fill_blank/open; array for MCQ is fine too

  // prompt: prefer normalized "prompt", then DB "prompt_md"; if open and still empty,
  // fall back to the first item's text/prompt/question
  let prompt = textOr(row.prompt, row.prompt_md, null);
  if (!prompt && (kind === "open" || kind === "open_ended")) {
    const first = items[0];
    prompt = textOr(first?.text, first?.prompt, first?.question);
  }

  const title = textOr(row.title, row.prompt, row.prompt_md, `Exercise ${row.sort_order ?? ""}`);
  const paragraph = row.paragraph || "";

  return {
    id: row.id,
    kind,
    title,
    prompt: prompt || "",
    paragraph,
    items,
    options,
    answer_key,
    sort_order: row.sort_order ?? 0,
  };
};

export default function PracticeSection({
  exercises = [],
  uiLang = "en",
  hideQuick = true,
  wrapInDetails = true,
  images = {},
  audioIndex = {},
}) {
  // ensure we’re working with an array
  const list0 = arr(exercises).map(transformExercise);

  // optionally hide "Quick Practice"
  const list = hideQuick
    ? list0.filter((ex) => !(ex.title || "").toLowerCase().includes("quick practice"))
    : list0;

  if (!list.length) return <p>No practice exercises for this lesson.</p>;

  return (
    <div className="ps-container">
      {list.map((ex) => {
        const Renderer = ex.kind ? kindToComponent[ex.kind] : null;
        if (!Renderer) {
          // eslint-disable-next-line no-console
          console.warn("[PracticeSection] Unknown exercise kind:", ex.kind, ex);
          return null;
        }

        // Pass full normalized exercise to the renderer.
        // MultipleChoiceExercise can read ex.options / ex.answer_key; fill_blank uses ex.items; open uses ex.prompt/items.
        if (!wrapInDetails) {
          return <Renderer key={ex.id} exercise={ex} uiLang={uiLang} images={images} audioIndex={audioIndex} />;
        }

        return (
          <details key={ex.id} className="ps-accordion">
            <summary className="ps-summary">
              {ex.title || ex.prompt || "Exercise"}
            </summary>
            <Renderer exercise={ex} uiLang={uiLang} images={images} audioIndex={audioIndex} />
          </details>
        );
      })}
    </div>
  );
}

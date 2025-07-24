import React from "react";
import FillBlankExercise from "./ExerciseTypes/FillBlankExercise";
import MultipleChoiceExercise from "./ExerciseTypes/MultipleChoiceExercise";
import OpenEndedExercise from "./ExerciseTypes/OpenEndedExercise";
import SentenceTransformExercise from "./ExerciseTypes/SentenceTransformExercise";

import "../Styles/PracticeSection.css";

const kindToComponent = {
  fill_blank: FillBlankExercise,
  multiple_choice: MultipleChoiceExercise,
  open: OpenEndedExercise,
  sentence_transform: SentenceTransformExercise,
};

// Transform DB data to component-friendly format
const transformExercise = (dbExercise) => {
  const base = {
    id: dbExercise.id,
    kind: dbExercise.kind,
    prompt: dbExercise.prompt_md || "",
    title: dbExercise.title || dbExercise.prompt_md || `Exercise ${dbExercise.sort_order ?? ""}`,
    paragraph: dbExercise.paragraph || ""
  };

  switch(dbExercise.kind) {
    case 'fill_blank':
      return {
        ...base,
        items: dbExercise.items || []
      };

    case 'multiple_choice':
      return {
        ...base,
        items: dbExercise.items || []
      };

    case 'open':
      return {
        ...base,
        items: dbExercise.items || []
      };

    case 'sentence_transform':
      return {
        ...base,
        items: dbExercise.items || []
      };

    default:
      return base;
  }
};

export default function PracticeSection({
  exercises = [],
  uiLang = "en",
  hideQuick = true,
  wrapInDetails = true,
}) {
  // optional filter
  const list = hideQuick
    ? exercises.filter(
        (ex) => !(ex.title || "").toLowerCase().includes("quick practice")
      )
    : exercises;

  if (!list.length) return <p>No practice exercises for this lesson.</p>;
  return (
    <div className="ps-container">
      {list.map((db) => {
        const ex = transformExercise(db);
        const Renderer = kindToComponent[ex.kind];
        if (!Renderer) return null;

        // If this is a Quick Practice exercise and wrapInDetails is false,
        // render without the details wrapper
        if (!wrapInDetails) {
          return <Renderer key={ex.id} exercise={ex} uiLang={uiLang} />;
        }

        // Otherwise, wrap in details
        return (
          <details key={ex.id} className="ps-accordion">
            <summary className="ps-summary">
              {ex.title || ex.prompt || "Exercise"}
            </summary>
            <Renderer exercise={ex} uiLang={uiLang} />
          </details>
        );
      })}
    </div>
  );
}

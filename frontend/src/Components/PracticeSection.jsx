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

export default function PracticeSection({ exercises = [], uiLang = "en" }) {
  if (!exercises.length) {
    return <p>No practice exercises for this lesson.</p>;
  }

  return (
    <div className="ps-container">
      {exercises.map((dbExercise) => {
        const exercise = transformExercise(dbExercise);
        const Renderer = kindToComponent[exercise.kind];

        if (!Renderer) {
          console.warn(`No component for exercise kind: "${exercise.kind}"`);
          return null;
        }

        return (
          <details key={exercise.id} className="ps-accordion">
            <summary className="ps-summary">
              {exercise.title || exercise.prompt || "Exercise"}
            </summary>
            <Renderer exercise={exercise} uiLang={uiLang} />
          </details>
        );
      })}
    </div>
  );
}

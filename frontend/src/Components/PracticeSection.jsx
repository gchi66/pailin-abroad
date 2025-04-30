import React from "react";
import FillBlankExercise from "./FillBlankExercise";
import MultipleChoiceExercise     from "./MultipleChoiceExercise";
import OpenEndedExercise          from "./OpenEndedExercise";
import SentenceTransformExercise  from "./SentenceTransformExercise";

import "../Styles/PracticeSection.css";

const kindToComponent = {
  fill_blank:          FillBlankExercise,
  multiple_choice:     MultipleChoiceExercise,
  open:                OpenEndedExercise,
  sentence_transform:  SentenceTransformExercise   // NEW
};

export default function PracticeSection({ exercises = [], uiLang = "en" }) {
  if (!exercises.length) {
    return <p>No practice exercises for this lesson.</p>;
  }

  return (
    <div className="ps-container">
      {exercises.map((ex) => console.log(ex.kind, ex.title))}
      {exercises.map((ex, idx) => {
        const Renderer = kindToComponent[ex.kind];
        if (!Renderer) return null;

        return (
          <details key={ex.id || idx} className="ps-accordion">
            <summary className="ps-summary">
              {ex.title || `Practice ${idx + 1}`}
            </summary>

            <Renderer exercise={ex} uiLang={uiLang} />
          </details>
        );
      })}
    </div>
  );
}

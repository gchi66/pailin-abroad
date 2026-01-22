import { useEffect, useState } from "react";
import supabaseClient from "../supabaseClient";
import MarkdownSection    from "./MarkdownSection";
import FillBlankExercise  from "./exercises/FillBlankExercise";
import SentenceTransform  from "./exercises/SentenceTransformExercise";
import MultipleChoice     from "./exercises/MultipleChoiceExercise";
import OpenEnded          from "./exercises/OpenEndedExercise";

/* handy lookup so we don’t need a switch every render */
const COMPONENT_FOR_KIND = {
  fill_blank:        FillBlankExercise,
  sentence_transform: SentenceTransform,
  multiple_choice:   MultipleChoice,
  open:              OpenEnded,
};

export default function UnderstandSection({ lessonId }) {
  const [markdown,  setMarkdown]  = useState("");
  const [quick,     setQuick]     = useState([]);   // array of exercise rows

  /* ── 1. fetch the UNDERSTAND markdown ───────────────────────── */
  useEffect(() => {
    supabaseClient
      .from("lesson_sections")
      .select("content")
      .eq("lesson_id", lessonId)
      .eq("type", "understand")
      .single()
      .then(({ data, error }) => {
        if (!error) setMarkdown(data.content || "");
      });
  }, [lessonId]);

  /* ── 2. fetch any “Quick Practice” exercises for this lesson ── */
  useEffect(() => {
    supabaseClient
      .from("practice_exercises")
      .select("*")                 // you already control column list
      .eq("lesson_id", lessonId)
      .ilike("title", "quick practice%")
      .order("sort_order")
      .then(({ data, error }) => {
        if (!error) setQuick(data || []);
      });
  }, [lessonId]);

  if (!markdown) return null;      // or a spinner

  const stripQuickPracticeSections = (content) => {
    if (!content) return "";
    const lines = content.split("\n");
    const output = [];
    let skipping = false;

    lines.forEach((line) => {
      if (line.startsWith("## ")) {
        const title = line.slice(3).trim().toLowerCase();
        if (title.startsWith("quick practice")) {
          skipping = true;
          return;
        }
        skipping = false;
      }
      if (!skipping) {
        output.push(line);
      }
    });

    return output.join("\n").trim();
  };
  const cleanedMarkdown = stripQuickPracticeSections(markdown);

  /* ── 3. build extra accordion cards for each practice row ───── */
  const extras = quick.map((ex) => {
    const Comp = COMPONENT_FOR_KIND[ex.kind];
    if (!Comp) return null;
    return {
      key:   `qp-${ex.id}`,
      title: ex.title || `Quick Practice ${ex.sort_order || ""}`,
      body:  (                        // JSX, not markdown
        <>
          {ex.prompt_md && <p className="fb-prompt">{ex.prompt_md}</p>}
          <Comp exercise={ex} />
        </>
      ),
    };
  }).filter(Boolean);

  return (
    <MarkdownSection
      markdown={cleanedMarkdown}
      extraSections={extras}   /* new prop, see next step */
      sectionType="understand"
    />
  );
}

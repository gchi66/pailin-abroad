import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";

import LessonHeader   from "../Components/LessonHeader";
import AudioBar       from "../Components/AudioBar";
import LessonSidebar  from "../Components/LessonSidebar";
import LessonContent  from "../Components/LessonContent";

import "../Styles/Lesson.css";

export default function Lesson() {
  const { id } = useParams();

  // high-level lesson row
  const [lesson, setLesson] = useState(null);

  // sections, questions, transcript
  const [sections,  setSections]  = useState([]);
  const [questions, setQuestions] = useState([]);
  const [transcript, setTranscript] = useState([]);

  // UI state
  const [activeId, setActiveId] = useState(null);
  const [uiLang,   setUiLang]   = useState("en");

  useEffect(() => {
    (async () => {
      // fetch lesson, sections, questions, and transcript in parallel
      const [
        { data: lsn,  error: e1 },
        { data: secs, error: e2 },
        { data: qs,   error: e3 },
        { data: tr,   error: e4 },
      ] = await Promise.all([
        supabaseClient
          .from("lessons")
          .select("*")
          .eq("id", id)
          .single(),
        supabaseClient
          .from("lesson_sections")
          .select("*")
          .eq("lesson_id", id)
          .order("sort_order"),
        supabaseClient
          .from("comprehension_questions")
          .select("*")
          .eq("lesson_id", id)
          .order("sort_order"),
        supabaseClient
          .from("transcript_lines")
          .select("*")
          .eq("lesson_id", id)
          .order("sort_order"),
      ]);

      if (e1 || e2 || e3 || e4) {
        console.error(e1, e2, e3, e4);
        return;
      }

      setLesson(lsn);
      setSections(secs);
      setQuestions(qs);
      setTranscript(tr);

      // initial active: first section, or fallback to comprehension/transcript
      setActiveId(
        secs[0]?.id
        || (qs.length ? "comprehension" : null)
        || (tr.length ? "transcript" : null)
      );
    })();
  }, [id]);

  if (!lesson) {
    return <div style={{ padding: "10vh", textAlign: "center" }}>Loading…</div>;
  }

  return (
    <main>
      <div className="lesson-page-container">
        {/* header banner */}
        <LessonHeader
          level={lesson.level}
          lessonOrder={lesson.lesson_order}
          title={lesson.title}
          subtitle={lesson.subtitle}
          titleTh={lesson.title_th}
          subtitleTh={lesson.subtitle_th}
        />

        {/* audio card */}
        <AudioBar
          audioSrc="/4.7_conversation.mp3"
          description={lesson.backstory}
        />

        {/* sidebar + content */}
        <div className="lesson-body">
          <LessonSidebar
            sections={sections}
            questions={questions}
            transcript={transcript}
            activeId={activeId}
            onSelect={setActiveId}
          />
          <LessonContent
            sections={sections}
            questions={questions}
            transcript={transcript}
            activeId={activeId}
            uiLang={uiLang}
            setUiLang={setUiLang}
          />
        </div>
      </div>
    </main>
  );
}

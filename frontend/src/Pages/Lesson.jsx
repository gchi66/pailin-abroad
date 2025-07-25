import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { fetchSnippets } from "../lib/fetchSnippets";

import LessonHeader   from "../Components/LessonHeader";
import AudioBar       from "../Components/AudioBar";
import LessonSidebar  from "../Components/LessonSidebar";
import LessonContent  from "../Components/LessonContent";
import PinnedComment   from "../Components/PinnedComment";

import "../Styles/Lesson.css";

export default function Lesson() {
  const { id } = useParams();

  // high-level lesson row
  const [lesson, setLesson] = useState(null);

  // sections, questions, transcript
  const [sections,  setSections]  = useState([]);
  const [questions, setQuestions] = useState([]);
  const [transcript, setTranscript] = useState([]);
  const [practiceExercises, setPracticeExercises] = useState([]);
  const [lessonPhrases, setLessonPhrases] = useState([]);

  // UI state
  const [activeId, setActiveId] = useState(null);
  const [uiLang,   setUiLang]   = useState("en");

  // Audio URL state
  const [audioUrl, setAudioUrl] = useState(null);

  // Add state for pinned comment
  const [pinnedComment, setPinnedComment] = useState("");

  // Audio snippet index
  const [snipIdx, setSnipIdx] = useState({});

  useEffect(() => {
    (async () => {
      // fetch lesson, sections, questions, and transcript in parallel
      const [
        { data: lsn,  error: e1 },
        { data: secs, error: e2 },
        { data: qs,   error: e3 },
        { data: tr,   error: e4 },
        { data: pe,   error: e5 },
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
        supabaseClient
          .from("practice_exercises")
          .select("*")
          .eq("lesson_id", id)
          .order("sort_order"),
      ]);

      if (e1 || e2 || e3 || e4 || e5) {
        console.error(e1, e2, e3, e4, e5);
        return;
      }

      setLesson(lsn);
      setSections(secs);
      setQuestions(qs);
      setTranscript(tr);
      setPracticeExercises(pe);

      // Find pinned comment section
      const pinnedSection = secs.find((s) => s.type === "pinned_comment");
      setPinnedComment(pinnedSection ? pinnedSection.content : "");

      // initial active: first section, or fallback to comprehension/transcript
      setActiveId(
        secs[0]?.id
        || (qs.length ? "comprehension" : null)
        || (tr.length ? "transcript" : null)
      );

      // Fetch audio URL if present
      const bucket = "lesson-audio";

      // Check if file exists by listing the directory
      const { data: files, error: listError } = await supabaseClient.storage
        .from('lesson-audio')
        .list('Beginner/L1/Conversations');

      if (lsn && lsn.conversation_audio_url) {
        console.log("Attempting to fetch audio for path:", lsn.conversation_audio_url);

        // Try to create signed URL
        const { data, error } = await supabaseClient
          .storage
          .from(bucket)
          .createSignedUrl(lsn.conversation_audio_url, 2 * 60 * 60);

        if (error) {
          console.error("Audio signed URL error:", error);
          console.error("Full error details:", JSON.stringify(error, null, 2));
          setAudioUrl(null);
        } else {
          console.log("Successfully created signed URL:", data.signedUrl);
          setAudioUrl(data.signedUrl);
        }
      } else {
        console.log("No audio URL found in lesson data");
        setAudioUrl(null);
      }

      // Fetch phrases for this lesson
      const { data: phraseLinks, error: phraseError } = await supabaseClient
        .from("lesson_phrases")
        .select("sort_order, phrases(*)")
        .eq("lesson_id", id)
        .order("sort_order");

      if (phraseError) {
        console.error("Error fetching lesson phrases:", phraseError);
        setLessonPhrases([]);
      } else {
        setLessonPhrases(phraseLinks.map(row => row.phrases));
      }
      console.log("Full lesson data:", lsn);
      console.log("Lesson external_id:", lsn.lesson_external_id);

      // Fetch audio snippet index for this lesson
      if (lsn && lsn.lesson_external_id) {
        try {
          const idx = await fetchSnippets(lsn.lesson_external_id);
          setSnipIdx(idx);
        } catch (err) {
          console.error("Error fetching audio snippets:", err);
        }
      }
    })(); // <-- closes the async IIFE
  }, [id]); // <-- closes useEffect

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
          audioSrc={audioUrl}
          description={lesson.backstory}
        />

        {/* sidebar + content */}
        <div className="lesson-body">
          <LessonSidebar
            sections={sections}
            questions={questions}
            transcript={transcript}
            practiceExercises={practiceExercises}
            lessonPhrases={lessonPhrases}
            activeId={activeId}
            onSelect={setActiveId}
            lesson={lesson}
          />
          <LessonContent
            sections={sections}
            questions={questions}
            transcript={transcript}
            practiceExercises={practiceExercises}
            lessonPhrases={lessonPhrases}
            activeId={activeId}
            uiLang={uiLang}
            setUiLang={setUiLang}
            snipIdx={snipIdx}
          />
        </div>
        {/* pinned comment at the bottom */}
        <PinnedComment comment={pinnedComment} />
      </div>
    </main>
  );
}

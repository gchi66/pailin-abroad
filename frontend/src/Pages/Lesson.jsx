// frontend/src/Pages/Lesson.jsx
import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link, useSearchParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { fetchResolvedLesson } from "../lib/fetchResolvedLesson";
import { fetchSnippets } from "../lib/fetchSnippets";

import LessonHeader from "../Components/LessonHeader";
import AudioBar from "../Components/AudioBar";
import LessonSidebar from "../Components/LessonSidebar";
import LessonContent from "../Components/LessonContent";
import LessonDiscussion from "../Components/LessonDiscussion";

import "../Styles/Lesson.css";

// ---------------- helpers ----------------

function safeJSON(v, fallback) {
  if (v == null) return fallback;
  if (Array.isArray(v) || (typeof v === "object" && v !== null)) return v;
  try {
    return JSON.parse(v);
  } catch {
    return fallback;
  }
}

function pickLang(en, th, lang) {
  const clean = (x) => {
    if (x == null) return null;
    const s = String(x).trim();
    return s === "" ? null : s;
  };
  if (lang === "th") return clean(th) ?? clean(en);
  return clean(en) ?? clean(th);
}

// Normalize a single practice exercise row to the shape the UI expects.
function normalizeExercise(ex, contentLang) {
  const exercise_type = ex.exercise_type || ex.kind || null;

  const title =
    ex.title != null || ex.title_th != null
      ? pickLang(ex.title, ex.title_th, contentLang)
      : ex.title ?? null;

  const prompt =
    ex.prompt != null || ex.prompt_th != null
      ? pickLang(ex.prompt, ex.prompt_th, contentLang)
      : pickLang(ex.prompt_md, ex.prompt_th, contentLang) ||
        ex.prompt_md ||
        ex.prompt ||
        null;

  const paragraph =
    ex.paragraph != null || ex.paragraph_th != null
      ? pickLang(ex.paragraph, ex.paragraph_th, contentLang)
      : null;

  const rawOptions =
    contentLang === "th" && ex.options_th ? ex.options_th : ex.options;
  const rawItems =
    contentLang === "th" && ex.items_th ? ex.items_th : ex.items;

  const options = safeJSON(rawOptions, []);
  const items = safeJSON(rawItems, []);
  const answer_key = safeJSON(ex.answer_key, {});
  const feedback =
    ex.feedback != null || ex.feedback_th != null
      ? pickLang(ex.feedback, ex.feedback_th, contentLang)
      : null;

  return {
    id: ex.id,
    lesson_id: ex.lesson_id,
    sort_order: ex.sort_order ?? 0,
    exercise_type, // "fill_blank" | "multiple_choice" | "open" | "sentence_transform"
    title,
    prompt, // from prompt_md or prompt
    paragraph, // optional helper text
    items, // for fill_blank / sentence_transform
    options, // for MCQ
    answer_key,
    feedback,
  };
}

// Normalize comprehension question rows to support BOTH schemas
function normalizeQuestion(q, contentLang) {
  const question_text =
    q.question_text != null || q.question_text_th != null
      ? pickLang(q.question_text, q.question_text_th, contentLang)
      : pickLang(q.prompt, q.prompt_th, contentLang) || q.prompt || null;

  let options;
  if (q.options || q.options_th) {
    const raw = contentLang === "th" && q.options_th ? q.options_th : q.options;
    options = safeJSON(raw, []);
  } else {
    const choices = ["choice_a", "choice_b", "choice_c", "choice_d"]
      .map((k) => {
        const en = q[k];
        const th = q[`${k}_th`];
        const v = pickLang(en, th, contentLang);
        return v ? v : null;
      })
      .filter(Boolean);
    options = choices.length ? choices : [];
  }

  const correct_choice = q.correct_choice ?? null; // legacy single-letter
  const answer_key = safeJSON(q.answer_key, null); // new array like ["B"]
  const explanation = pickLang(q.explanation, q.explanation_th, contentLang);

  return {
    id: q.id,
    lesson_id: q.lesson_id,
    sort_order: q.sort_order ?? 0,
    question_type: q.question_type || null,
    question_text,
    options,
    correct_choice,
    answer_key,
    explanation,
  };
}

// ---------------- component ----------------

export default function Lesson() {
  const { id } = useParams();

  // URL param → controls resolver language (content language)
  const [searchParams, setSearchParams] = useSearchParams();
  const contentLang = (searchParams.get("content_lang") || "en").toLowerCase(); // "en" | "th"

  // UI language for site-wide labels + header (independent of contentLang)
  const [uiLang, setUiLang] = useState("en");

  // Resolved payload pieces
  const [lesson, setLesson] = useState(null);
  const [sections, setSections] = useState([]);
  const [questions, setQuestions] = useState([]);
  const [transcript, setTranscript] = useState([]);
  const [practiceExercises, setPracticeExercises] = useState([]);
  const [lessonPhrases, setLessonPhrases] = useState([]);

  // UI state
  const [activeId, setActiveId] = useState(null);

  // Audio + snippets
  const [audioUrl, setAudioUrl] = useState(null);
  const [snipIdx, setSnipIdx] = useState({});

  // Lesson list for prev/next
  const [lessonList, setLessonList] = useState([]);

  // Pinned comment from sections
  const pinnedComment = useMemo(() => {
    const s = sections.find((x) => x.type === "pinned_comment");
    return s ? s.content || "" : "";
  }, [sections]);

  // Change content language via URL
  const setContentLang = (lang) => {
    const next = new URLSearchParams(searchParams);
    next.set("content_lang", lang);
    setSearchParams(next, { replace: true });
  };



  useEffect(() => {
    (async () => {
      try {
        // 1) fetch resolved payload from backend
        const payload = await fetchResolvedLesson(id, contentLang);

        // derive safe title/subtitle variants for UI (fall back if resolver doesn’t expose *_en/_th)
        const title_en = payload.title_en ?? payload.title ?? null;
        const title_th = payload.title_th ?? null;
        const subtitle_en = payload.subtitle_en ?? payload.subtitle ?? null;
        const subtitle_th = payload.subtitle_th ?? null;

        const lsn = {
          id: payload.id,
          stage: payload.stage,
          level: payload.level,
          lesson_order: payload.lesson_order,
          image_url: payload.image_url,
          conversation_audio_url: payload.conversation_audio_url,
          lesson_external_id: payload.lesson_external_id,
          // keep both for UI choice
          title_en,
          title_th,
          subtitle_en,
          subtitle_th,
          // convenient content-language strings too (if you still want them)
          title: payload.title ?? null,
          subtitle: payload.subtitle ?? null,
          focus: payload.focus ?? null,
          backstory: payload.backstory ?? null,
        };

        // normalize questions/exercises in case resolver sends raw DB rows
        const normalizedQuestions = (payload.questions || []).map((q) =>
          normalizeQuestion(q, contentLang)
        );

        const normalizedExercises = (payload.practice_exercises || []).map(
          (ex) => normalizeExercise(ex, contentLang)
        );

        setLesson(lsn);
        setSections(payload.sections || []);
        setTranscript(payload.transcript || []);
        setQuestions(normalizedQuestions);
        setPracticeExercises(normalizedExercises);
        setLessonPhrases(payload.phrases || []);

        // 2) initial active section
        const firstSectionId = (payload.sections && payload.sections[0]?.id) || null;
        const fallback =
          (normalizedQuestions.length ? "comprehension" : null) ||
          ((payload.transcript || []).length ? "transcript" : null);
        setActiveId(firstSectionId || fallback);

        // 3) sign conversation audio
        if (lsn.conversation_audio_url) {
          try {
            const { data, error } = await supabaseClient.storage
              .from("lesson-audio")
              .createSignedUrl(lsn.conversation_audio_url, 2 * 60 * 60);
            if (error) {
              console.warn("Audio signed URL error:", error);
              setAudioUrl(null);
            } else {
              setAudioUrl(data.signedUrl);
            }
          } catch (e) {
            console.warn("Audio signed URL exception:", e);
            setAudioUrl(null);
          }
        } else {
          setAudioUrl(null);
        }

        // 4) fetch audio snippet index
        if (lsn.lesson_external_id) {
          try {
            const idx = await fetchSnippets(lsn.lesson_external_id);
            setSnipIdx(idx || {});
          } catch (err) {
            console.error("Error fetching audio snippets:", err);
            setSnipIdx({});
          }
        } else {
          setSnipIdx({});
        }

        // 5) prev/next list
        if (lsn.stage && typeof lsn.level !== "undefined") {
          const { data: allLessons, error: allLessonsError } = await supabaseClient
            .from("lessons")
            .select("id, lesson_order, title, title_th, stage, level")
            .eq("stage", lsn.stage)
            .eq("level", lsn.level)
            .order("lesson_order", { ascending: true });
          if (!allLessonsError && allLessons) {
            setLessonList(allLessons);
          }
        }
      } catch (err) {
        console.error("Failed to fetch resolved lesson:", err);
        // clear to avoid stale UI
        setLesson(null);
        setSections([]);
        setTranscript([]);
        setQuestions([]);
        setPracticeExercises([]);
        setLessonPhrases([]);
      }
    })();
  }, [id, contentLang]); // refetch when lesson id or content language changes

  if (!lesson) {
    return <div style={{ padding: "10vh", textAlign: "center" }}>Loading…</div>;
  }

  // Prev/Next
  const currentIdx = lessonList.findIndex((l) => l.id === lesson.id);
  const prevLesson = currentIdx > 0 ? lessonList[currentIdx - 1] : null;
  const nextLesson =
    currentIdx >= 0 && currentIdx < lessonList.length - 1
      ? lessonList[currentIdx + 1]
      : null;

  // Choose header strings by UI language (independent of contentLang)
  const headerTitle =
    uiLang === "th" ? (lesson.title_th || lesson.title_en) : (lesson.title_en || lesson.title_th);
  const headerSubtitle =
    uiLang === "th" ? (lesson.subtitle_th || lesson.subtitle_en) : (lesson.subtitle_en || lesson.subtitle_th);

  return (
    <main>
      <div className="lesson-page-container">
        {/* Header */}
        <LessonHeader
          level={lesson.level}
          lessonOrder={lesson.lesson_order}
          title={headerTitle}
          subtitle={headerSubtitle}
        />

        {/* Audio card */}
        <AudioBar audioSrc={audioUrl} description={lesson.backstory} />

        {/* Language toggles */}
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", margin: "1rem 0" }}>
          {/* <LessonLanguageToggle contentLang={contentLang} onToggle={handleToggleContentLang} /> */}
          <span style={{ marginLeft: "1rem" }}>UI language:</span>
          <button
            className={`lesson-nav-btn${uiLang === "en" ? " active" : ""}`}
            onClick={() => setUiLang("en")}
          >
            EN
          </button>
          <button
            className={`lesson-nav-btn${uiLang === "th" ? " active" : ""}`}
            onClick={() => setUiLang("th")}
          >
            TH
          </button>
        </div>

        {/* Body */}
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
            contentLang={contentLang}
            setContentLang={setContentLang}
          />
        </div>

        {/* Prev / Next */}
        <div
          className="lesson-nav-buttons"
          style={{ display: "flex", justifyContent: "center", gap: "2rem", margin: "2rem 0" }}
        >
          <Link
            to={prevLesson ? `/lesson/${prevLesson.id}` : "#"}
            className={`lesson-nav-btn${prevLesson ? "" : " disabled"}`}
            style={{ pointerEvents: prevLesson ? "auto" : "none", opacity: prevLesson ? 1 : 0.5 }}
          >
            ← Previous Lesson
          </Link>
          <Link
            to={nextLesson ? `/lesson/${nextLesson.id}` : "#"}
            className={`lesson-nav-btn${nextLesson ? "" : " disabled"}`}
            style={{ pointerEvents: nextLesson ? "auto" : "none", opacity: nextLesson ? 1 : 0.5 }}
          >
            Next Lesson →
          </Link>
        </div>

        {/* Discussion */}
        <LessonDiscussion lessonId={lesson.id} isAdmin={false} />
      </div>
    </main>
  );
}

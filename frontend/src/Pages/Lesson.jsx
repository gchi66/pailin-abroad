// frontend/src/Pages/Lesson.jsx
import React, { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { fetchResolvedLesson } from "../lib/fetchResolvedLesson";
import { fetchSnippets, fetchPhrasesSnippets } from "../lib/fetchSnippets";

import LessonHeader from "../Components/LessonHeader";
import AudioBar from "../Components/AudioBar";
import LessonSidebar from "../Components/LessonSidebar";
import LessonContent from "../Components/LessonContent";
import LessonDiscussion from "../Components/LessonDiscussion";
// import LanguageToggle from "../Components/LanguageToggle"; // (unused)
import LessonNavigationBanner from "../Components/LessonNavigationBanner";

import "../Styles/Lesson.css";

// ---------------- helpers ----------------
// Your global order (match your sidebar's MASTER_ORDER)
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

function tabExists({ id, sections, questions, transcript, practiceExercises, lessonPhrases }) {
  if (id === "comprehension") return (questions?.length ?? 0) > 0;
  if (id === "transcript")    return (transcript?.length ?? 0) > 0;
  if (id === "practice")      return (practiceExercises?.length ?? 0) > 0;
  if (id === "phrases_verbs") {
    return (lessonPhrases ?? []).some(
      p => (p.content_md && p.content_md.trim()) || (p.content && p.content.trim())
    );
  }
  // otherwise it's a real section UUID from `sections`
  return sections.some(s => s.id === id);
}

function computeDefaultActiveId({ sections, questions, transcript, practiceExercises, lessonPhrases }) {
  if ((questions?.length ?? 0) > 0) return "comprehension";

  for (const type of MASTER_ORDER) {
    if (type === "comprehension" && (questions?.length ?? 0) > 0) return "comprehension";
    if (type === "transcript"    && (transcript?.length ?? 0) > 0) return "transcript";
    if (type === "practice"      && (practiceExercises?.length ?? 0) > 0) return "practice";
    if (type === "phrases_verbs") {
      const hasPhrases = (lessonPhrases ?? []).some(
        p => (p.content_md && p.content_md.trim()) || (p.content && p.content.trim())
      );
      if (hasPhrases) return "phrases_verbs";
      continue;
    }
    const sec = sections.find(s => s.type === type);
    if (sec) return sec.id;
  }
  return null;
}

function safeJSON(v, fallback) {
  if (v == null) return fallback;
  if (Array.isArray(v) || (typeof v === "object" && v !== null)) return v;
  const s = String(v).trim();
  if (s === "") return fallback;             // <— handle "" from DB
  try { return JSON.parse(s); } catch { return fallback; }
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

  // prefer prompt / prompt_md; if still missing and it's open-ended, use first item's text
  const rawItems = contentLang === "th" && ex.items_th ? ex.items_th : ex.items;
  const items    = safeJSON(rawItems, []);
  let prompt =
    (ex.prompt != null || ex.prompt_th != null
      ? pickLang(ex.prompt, ex.prompt_th, contentLang)
      : pickLang(ex.prompt_md, ex.prompt_th, contentLang) || ex.prompt_md || ex.prompt || null);

  if (!prompt && (exercise_type === "open" || exercise_type === "open_ended")) {
    const first = items && items[0] && (items[0].text || items[0].prompt || items[0].question);
    if (first) prompt = String(first);
  }

  const paragraph =
    ex.paragraph != null || ex.paragraph_th != null
      ? pickLang(ex.paragraph, ex.paragraph_th, contentLang)
      : null;

  const rawOptions = contentLang === "th" && ex.options_th ? ex.options_th : ex.options;
  const options    = safeJSON(rawOptions, []);
  const answer_key = safeJSON(ex.answer_key, {});

  const feedback =
    ex.feedback != null || ex.feedback_th != null
      ? pickLang(ex.feedback, ex.feedback_th, contentLang)
      : null;

  return {
    id: ex.id,
    lesson_id: ex.lesson_id,
    sort_order: ex.sort_order ?? 0,
    exercise_type,   // "fill_blank" | "multiple_choice" | "open" | ...
    title,
    prompt,          // will exist for open after fallback
    paragraph,
    items,
    options,
    answer_key,
    feedback,
  };
}

// Normalize comprehension question rows to match backend fields
function normalizeQuestion(q, contentLang) {
  // Use prompt and prompt_th from backend
  const prompt = pickLang(q.prompt, q.prompt_th, contentLang) || q.prompt || null;
  // Options now may already be structured (array of {label,text,image_key?,alt_text?})
  let options;
  if (q.options || q.options_th) {
    const raw = contentLang === "th" && q.options_th ? q.options_th : q.options;
    const parsed = safeJSON(raw, []);
    if (Array.isArray(parsed)) {
      // If they are strings, keep for backwards compatibility; else assume structured objects
      options = parsed.map((opt) => {
        if (typeof opt === "string") {
          // legacy fallback: try to split 'A. text'
            const m = opt.match(/^([A-Z])\.\s*(.*)$/s);
            if (m) {
              return { label: m[1], text: m[2] };
            }
            return { label: "", text: opt };
        }
        return opt;
      });
    } else {
      options = [];
    }
  } else {
    options = [];
  }

  const correct_choice = q.correct_choice ?? null; // legacy single-letter
  const answer_key = safeJSON(q.answer_key, null); // new array like ["B"]
  const explanation = pickLang(q.explanation, q.explanation_th, contentLang);

  return {
    id: q.id,
    lesson_id: q.lesson_id,
    sort_order: q.sort_order ?? 0,
    question_type: q.question_type || null,
    prompt,
    options, // structured options available to UI
    correct_choice,
    answer_key,
    explanation,
  };
}

// ---------------- component ----------------

export default function Lesson() {
  // Remember/restore the current tab across language toggles
  // UI state
  const [activeId, setActiveId] = useState(null);
  const lastActiveRef = useRef(null);
  useEffect(() => { lastActiveRef.current = activeId; }, [activeId]);
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
  const [images, setImages] = useState({});
  const [isLocked, setIsLocked] = useState(false);


  // Audio + snippets
  const [audioUrl, setAudioUrl] = useState(null);
  const [audioUrlNoBg, setAudioUrlNoBg] = useState(null);
  const [audioUrlBg, setAudioUrlBg] = useState(null);
  const [snipIdx, setSnipIdx] = useState({});
  const [phrasesSnipIdx, setPhrasesSnipIdx] = useState({});

  // Lesson list for prev/next
  const [lessonList, setLessonList] = useState([]);

  // (pinnedComment removed - unused)

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
        setIsLocked(payload.locked || false);
        console.log("Phrases payload:", payload.phrases);

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
        console.log("Normalized Exercises:", normalizedExercises);

        setLesson(lsn);
        setSections(payload.sections || []);
        setTranscript(payload.transcript || []);
        setQuestions(normalizedQuestions);
        setPracticeExercises(normalizedExercises);
        setLessonPhrases(payload.phrases || []);
        setImages(payload.images || {});

  // console.log("Practice exercises:", normalizedExercises);
        // 2) initial active section: only set if not already chosen
        setActiveId(prev => {
          if (prev) return prev;
          return computeDefaultActiveId({
            sections: payload.sections || [],
            questions: normalizedQuestions,
            transcript: payload.transcript || [],
            practiceExercises: normalizedExercises,
            lessonPhrases: payload.phrases || [],
          });
        });

        // Restore tab after all state is set
        {
          const desired = lastActiveRef.current;
          const canKeep = desired && tabExists({
            id: desired,
            sections: payload.sections || [],
            questions: normalizedQuestions,
            transcript: payload.transcript || [],
            practiceExercises: normalizedExercises,
            lessonPhrases: payload.phrases || [],
          });

          if (!canKeep) {
            setActiveId(prev => prev ?? computeDefaultActiveId({
              sections: payload.sections || [],
              questions: normalizedQuestions,
              transcript: payload.transcript || [],
              practiceExercises: normalizedExercises,
              lessonPhrases: payload.phrases || [],
            }));
          }
        }

        // 3) sign conversation audio (all three versions)
        if (lsn.conversation_audio_url) {
          try {
            // Sign the main conversation file
            const { data: mainData, error: mainError } = await supabaseClient.storage
              .from("lesson-audio")
              .createSignedUrl(lsn.conversation_audio_url, 2 * 60 * 60);

            if (mainError) {
              console.warn("Main audio signed URL error:", mainError);
              setAudioUrl(null);
            } else {
              setAudioUrl(mainData.signedUrl);
            }

            // Generate paths for split versions
            const basePath = lsn.conversation_audio_url;
            const noBgPath = basePath.replace('.mp3', '_no_bg.mp3');
            const bgPath = basePath.replace('.mp3', '_bg.mp3');

            // Sign the no-background version
            const { data: noBgData, error: noBgError } = await supabaseClient.storage
              .from("lesson-audio")
              .createSignedUrl(noBgPath, 2 * 60 * 60);

            if (noBgError) {
              console.warn("No-bg audio signed URL error:", noBgError);
              setAudioUrlNoBg(null);
            } else {
              setAudioUrlNoBg(noBgData.signedUrl);
            }

            // Sign the background-only version
            const { data: bgData, error: bgError } = await supabaseClient.storage
              .from("lesson-audio")
              .createSignedUrl(bgPath, 2 * 60 * 60);

            if (bgError) {
              console.warn("Background audio signed URL error:", bgError);
              setAudioUrlBg(null);
            } else {
              setAudioUrlBg(bgData.signedUrl);
            }

          } catch (e) {
            console.warn("Audio signed URL exception:", e);
            setAudioUrl(null);
            setAudioUrlNoBg(null);
            setAudioUrlBg(null);
          }
        } else {
          setAudioUrl(null);
          setAudioUrlNoBg(null);
          setAudioUrlBg(null);
        }

        // 4) fetch audio snippet index (including phrases audio snippets)
        if (lsn.lesson_external_id) {
          try {
            const idx = await fetchSnippets(lsn.lesson_external_id, lsn.id);
            setSnipIdx(idx || {});
          } catch (err) {
            console.error("Error fetching audio snippets:", err);
            setSnipIdx({});
          }
        } else {
          setSnipIdx({});
        }

        // 5) fetch phrases audio snippets
        if (lsn.id) {
          try {
            const phrasesAudio = await fetchPhrasesSnippets(lsn.id);
            setPhrasesSnipIdx(phrasesAudio || {});
          } catch (err) {
            console.error("Error fetching phrases audio snippets:", err);
            setPhrasesSnipIdx({});
          }
        } else {
          setPhrasesSnipIdx({});
        }

        // 6) prev/next list
        if (lsn.stage && typeof lsn.level !== "undefined") {
          const { data: allLessons, error: allLessonsError } = await supabaseClient
            .from("lessons")
            .select("id, lesson_order, title, title_th, stage, level")
            .eq("stage", lsn.stage)
            .eq("level", lsn.level)
            .order("lesson_order", { ascending: true });
          if (!allLessonsError && allLessons) {
            const normalLessons = allLessons.filter(
              l => !(l.external_id && l.external_id.endsWith('.chp'))
            );
            // If you want to show the checkpoint separately, you can find it:
            // checkpointLesson lookup removed (unused)
            setLessonList(normalLessons);
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
       <AudioBar
          audioSrc={audioUrl}
          audioSrcNoBg={audioUrlNoBg}
          audioSrcBg={audioUrlBg}
          description={lesson.backstory}
          isLocked={isLocked}
        />

        {/* Language toggles
        <LanguageToggle
          language={uiLang}
          setLanguage={setUiLang}
          label="UI language:"
          showLabel={true}
          buttonStyle={true}
        /> */}

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
            isLocked={isLocked}
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
            phrasesSnipIdx={phrasesSnipIdx}
            contentLang={contentLang}
            setContentLang={setContentLang}
            images={images}
            isLocked={isLocked}
          />
        </div>

        {/* Lesson Navigation Banner */}
        <LessonNavigationBanner
          prevLesson={prevLesson}
          nextLesson={nextLesson}
          currentLesson={lesson}
          onMarkComplete={(isCompleted) => {
            console.log(`Lesson ${lesson.lesson_external_id} marked as ${isCompleted ? 'completed' : 'incomplete'}`);
            // TODO: Add actual completion tracking logic here
          }}
        />

        {/* Discussion */}
        <LessonDiscussion lessonId={lesson.id} isAdmin={false} />
      </div>
    </main>
  );
}

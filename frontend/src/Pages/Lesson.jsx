// frontend/src/Pages/Lesson.jsx
import React, { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import supabaseClient from "../supabaseClient";
import { fetchResolvedLesson, prefetchResolvedLesson } from "../lib/fetchResolvedLesson";
import { fetchSnippets, fetchPhrasesSnippets } from "../lib/fetchSnippets";

import LessonHeader from "../Components/LessonHeader";
import AudioBar from "../Components/AudioBar";
import LessonSidebar from "../Components/LessonSidebar";
import LessonContent from "../Components/LessonContent";
import LessonDiscussion from "../Components/LessonDiscussion";
// import LanguageToggle from "../Components/LanguageToggle"; // (unused)
import LessonNavigationBanner from "../Components/LessonNavigationBanner";
import { useUiLang } from "../ui-lang/UiLangContext";
import { t } from "../ui-lang/i18n";
import { useStickyLessonToggle } from "../StickyLessonToggleContext";
import PrepareCard from "../Components/PrepareCard";

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

const LABEL_KEY_MAP = {
  comprehension: "lessonSidebar.labels.comprehension",
  transcript: "lessonSidebar.labels.transcript",
  apply: "lessonSidebar.labels.apply",
  understand: "lessonSidebar.labels.understand",
  extra_tip: "lessonSidebar.labels.extra_tip",
  common_mistake: "lessonSidebar.labels.common_mistake",
  phrases_verbs: "lessonSidebar.labels.phrases_verbs",
  culture_note: "lessonSidebar.labels.culture_note",
  practice: "lessonSidebar.labels.practice",
};

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

function getSectionLabel(type, uiLang) {
  const key = LABEL_KEY_MAP[type];
  if (!key) return (type || "").toUpperCase();
  const translated = t(key, uiLang);
  if (translated) return translated;
  return (type || "").toUpperCase();
}

function buildSectionMenu({ sections = [], questions = [], transcript = [], practiceExercises = [], lessonPhrases = [], isLocked = false, uiLang = "en" }) {
  const items = MASTER_ORDER
    .map((type) => {
      if (isLocked) {
        return { id: type, type };
      }
      if (type === "comprehension" && questions.length) {
        return { id: "comprehension", type };
      }
      if (type === "transcript" && transcript.length) {
        return { id: "transcript", type };
      }
      if (type === "practice" && practiceExercises.length) {
        return { id: "practice", type };
      }
      if (type === "phrases_verbs") {
        const hasPhrases = lessonPhrases.some(
          (item) =>
            (item.content_md && item.content_md.trim() !== "") ||
            (item.content && item.content.trim() !== "")
        );
        if (hasPhrases) {
          return { id: "phrases_verbs", type };
        }
        return null;
      }
      const sec = sections.find((s) => s.type === type);
      return sec ? { id: sec.id, type } : null;
    })
    .filter(Boolean);

  return items.map((item) => ({
    ...item,
    label: getSectionLabel(item.type, uiLang),
  }));
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
  const exercise_type = ex.exercise_type || ex.kind || ex.type || null;

  const title_en = ex.title_en ?? ex.title ?? null;
  const title_th = ex.title_th ?? null;
  const prompt_en = ex.prompt_en ?? ex.prompt_md ?? ex.prompt ?? null;
  const prompt_th = ex.prompt_th ?? null;
  const paragraph_en = ex.paragraph_en ?? ex.paragraph ?? null;
  const paragraph_th = ex.paragraph_th ?? null;

  const items_en = safeJSON(ex.items_en ?? ex.items, []);
  const items_th = safeJSON(ex.items_th, []);
  const options_en = safeJSON(ex.options_en ?? ex.options, []);
  const options_th = safeJSON(ex.options_th, []);
  const answer_key = safeJSON(ex.answer_key, {});

  const title = pickLang(title_en, title_th, contentLang) ?? null;
  let prompt = pickLang(prompt_en, prompt_th, contentLang) ?? null;
  const paragraph = pickLang(paragraph_en, paragraph_th, contentLang) ?? null;

  const isQuickPractice = typeof title_en === "string"
    ? title_en.trim().toLowerCase().startsWith("quick practice")
    : false;

  const mergeItemsWithThai = (enItems, thItems) => {
    const base = Array.isArray(enItems) && enItems.length
      ? enItems.map((item) => ({ ...(item || {}) }))
      : Array.isArray(thItems)
        ? thItems.map((item) => ({ ...(item || {}) }))
        : [];

    if (!Array.isArray(thItems) || !thItems.length) {
      return base;
    }

    const thaiByNumber = new Map();
    thItems.forEach((thItem, idx) => {
      if (!thItem) return;
      const key = thItem.number != null ? String(thItem.number) : `__idx_${idx}`;
      thaiByNumber.set(key, thItem);
    });

    return base.map((item, idx) => {
      const key = item.number != null ? String(item.number) : `__idx_${idx}`;
      const thItem = thaiByNumber.get(key) ?? thItems[idx];
      if (thItem && typeof item === "object") {
        const thaiTextCandidate =
          (typeof thItem.text_th === "string" && thItem.text_th.trim()) ||
          (typeof thItem.text === "string" && thItem.text.trim()) ||
          "";
        if (thaiTextCandidate) {
          item.text_th = thaiTextCandidate;
        }
      }
      return item;
    });
  };

  const items = mergeItemsWithThai(items_en, items_th);

  const options =
    contentLang === "th" && Array.isArray(options_th) && options_th.length
      ? options_th
      : options_en;

  if (!prompt && (exercise_type === "open" || exercise_type === "open_ended")) {
    const first = items && items[0] && (items[0].text || items[0].prompt || items[0].question);
    if (first && contentLang !== "th") prompt = String(first);
  }

  return {
    id: ex.id,
    lesson_id: ex.lesson_id,
    sort_order: ex.sort_order ?? 0,
    exercise_type,
    title,
    title_th,
    title_en,
    prompt,
    prompt_en,
    prompt_th,
    paragraph,
    items,
    options,
    answer_key,
    isQuickPractice,
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

function normalizeHeaderImagePath(raw) {
  if (!raw) return null;
  let value = String(raw).trim();
  if (!value) return null;
  if (/^https?:\/\//i.test(value)) {
    return null;
  }
  value = value.replace(/^lesson-images\//i, "");
  value = value.replace(/^\/+/, "");
  value = value.split(/[?#]/)[0];
  if (!/^headers\//i.test(value) && !value.includes("/")) {
    value = `headers/${value}`;
  }
  if (!/\.[a-z0-9]+$/i.test(value)) {
    value = `${value}.webp`;
  }
  return value;
}

// ---------------- component ----------------

export default function Lesson({ toggleLoginModal, toggleSignupModal }) {
  // Remember/restore the current tab across language toggles
  // UI state
  const [activeId, setActiveId] = useState(null);
  const lastActiveRef = useRef(null);
  useEffect(() => { lastActiveRef.current = activeId; }, [activeId]);
  const { id } = useParams();

  // Content language persists via localStorage (shared with exercise/topic sections)
  const [contentLang, setContentLangState] = useState(() => {
    if (typeof window === "undefined") return "en";
    const stored = (localStorage.getItem("contentLang") || "").toLowerCase();
    return stored === "th" ? "th" : "en";
  });

  useEffect(() => {
    // Reset active section when navigating to a different lesson
    setActiveId(null);
  }, [id]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("contentLang", contentLang);
    }
  }, [contentLang]);

  // UI language for site-wide labels + header
  const { ui: uiLang } = useUiLang();

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
  const [showStickyPlayer, setShowStickyPlayer] = useState(false);
  const [shouldAutoPlay, setShouldAutoPlay] = useState(false);
  const [isSidebarStuck, setIsSidebarStuck] = useState(false);
  const [sidebarHeight, setSidebarHeight] = useState(0);
  const [isMobileView, setIsMobileView] = useState(false);
  const handleSelectSection = useCallback((id) => {
    shouldAutoScrollRef.current = true;
    setActiveId(id);
  }, []);

  // Lesson list for prev/next
  const [lessonList, setLessonList] = useState([]);

  // (pinnedComment removed - unused)

  // Change content language via local state/storage (matches LessonLanguageToggle contract)
  const setContentLang = useCallback((lang) => {
    const normalized = lang === "th" ? "th" : "en";
    setContentLangState(normalized);
  }, []);

  const {
    registerLessonToggle,
    unregisterLessonToggle,
    updateContentLang: updateStickyContentLang,
    setShowStickyToggle,
  } = useStickyLessonToggle();

  const observerRef = useRef(null);
  const observerMarginRef = useRef("");
  const headNodesRef = useRef(new Map());
  const visibleHeadIdsRef = useRef(new Set());
  const headIdCounterRef = useRef(0);
  const reachedHeadsRef = useRef(false); // track if user has ever reached the lesson heads
  const topSentinelRef = useRef(null);
  const topSentinelVisibleRef = useRef(false);
  const topObserverRef = useRef(null);
  const sidebarSentinelRef = useRef(null);
  const sidebarRef = useRef(null);
  const hasSectionScrollRef = useRef(false);
  const shouldAutoScrollRef = useRef(false);

  const computeNavbarMargin = useCallback(() => {
    if (typeof window === "undefined") return "0px 0px 0px 0px";
    const raw = getComputedStyle(document.documentElement).getPropertyValue("--navbar-height");
    const parsed = parseFloat(raw);
    const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
    const sidebarOffset = isMobileView && isSidebarStuck ? sidebarHeight : 0;
    return `-${navbarHeight + sidebarOffset}px 0px 0px 0px`;
  }, [isMobileView, isSidebarStuck, sidebarHeight]);

  const recomputeStickyVisibility = useCallback(() => {
    const noHeadsVisible = visibleHeadIdsRef.current.size === 0;
    const shouldShow =
      reachedHeadsRef.current &&
      noHeadsVisible &&
      !topSentinelVisibleRef.current;
    setShowStickyToggle(shouldShow);
  }, [setShowStickyToggle]);

  const handleIntersection = useCallback((entries) => {
    if (headNodesRef.current.size === 0) return;
    let changed = false;
    entries.forEach((entry) => {
      const id = entry.target.getAttribute("data-sticky-head-id");
      if (!id) return;
      if (entry.isIntersecting) {
        reachedHeadsRef.current = true;
        if (!visibleHeadIdsRef.current.has(id)) {
          visibleHeadIdsRef.current.add(id);
          changed = true;
        }
      } else if (visibleHeadIdsRef.current.has(id)) {
        visibleHeadIdsRef.current.delete(id);
        changed = true;
      }
    });
    if (changed) {
      recomputeStickyVisibility();
    }
  }, [recomputeStickyVisibility]);

  const rebuildObserver = useCallback(() => {
    const margin = computeNavbarMargin();
    if (observerRef.current) {
      observerRef.current.disconnect();
    }
    const observer = new IntersectionObserver(handleIntersection, {
      root: null,
      threshold: 0,
      rootMargin: margin,
    });
    observerRef.current = observer;
    observerMarginRef.current = margin;
    headNodesRef.current.forEach((node) => {
      observer.observe(node);
    });
  }, [computeNavbarMargin, handleIntersection]);

  const ensureObserver = useCallback(() => {
    const margin = computeNavbarMargin();
    if (!observerRef.current || observerMarginRef.current !== margin) {
      rebuildObserver();
    }
    return observerRef.current;
  }, [computeNavbarMargin, rebuildObserver]);

  const registerStickyHeaders = useCallback((nodes, options = {}) => {
    const { preserveState = false } = options;
    if (!nodes || nodes.length === 0) {
      headNodesRef.current.clear();
      visibleHeadIdsRef.current.clear();
      if (!preserveState) {
        reachedHeadsRef.current = false;
        setShowStickyToggle(false);
      }
      return;
    }

    const observer = ensureObserver();
    const map = headNodesRef.current;
    const incomingIds = new Set();

    nodes.forEach((node) => {
      if (!node) return;
      if (!node.getAttribute("data-sticky-head-id")) {
        const newId = `lesson-head-${headIdCounterRef.current++}`;
        node.setAttribute("data-sticky-head-id", newId);
      }
      incomingIds.add(node.getAttribute("data-sticky-head-id"));
    });

    map.forEach((node, id) => {
      if (!incomingIds.has(id)) {
        if (observer) observer.unobserve(node);
        map.delete(id);
        visibleHeadIdsRef.current.delete(id);
      }
    });

    nodes.forEach((node) => {
      if (!node) return;
      const id = node.getAttribute("data-sticky-head-id");
      const existing = map.get(id);
      if (existing === node) return;
      if (existing && observer) {
        observer.unobserve(existing);
      }
      map.set(id, node);
      if (observer) {
        observer.observe(node);
      }
    });

    const navbarHeightRaw =
      typeof window !== "undefined"
        ? getComputedStyle(document.documentElement).getPropertyValue("--navbar-height")
        : "0";
    const parsed = parseFloat(navbarHeightRaw);
    const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
    const viewportHeight =
      typeof window !== "undefined" ? window.innerHeight : 0;

    const visibleNow = new Set();
    nodes.forEach((node) => {
      if (!node) return;
      const id = node.getAttribute("data-sticky-head-id");
      if (!id) return;
      const rect = node.getBoundingClientRect();
      const isVisible =
        rect.bottom > navbarHeight && rect.top < viewportHeight;
      if (isVisible) {
        visibleNow.add(id);
        reachedHeadsRef.current = true;
      }
    });

    visibleHeadIdsRef.current = visibleNow;
    recomputeStickyVisibility();
  }, [ensureObserver, recomputeStickyVisibility]);

  // Observe the top sentinel to know when the lesson is at the top of the screen
  useEffect(() => {
    const node = topSentinelRef.current;
    if (!node) return undefined;

    const margin = computeNavbarMargin();
    // turn "-80px 0px 0px 0px" into "80px 0px 0px 0px" to extend the root upward
    const positiveMargin = margin.startsWith("-") ? margin.slice(1) : margin;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          topSentinelVisibleRef.current = entry.isIntersecting;
        });
        recomputeStickyVisibility();
      },
      { threshold: 0, rootMargin: positiveMargin }
    );

    topObserverRef.current = observer;
    observer.observe(node);

    return () => {
      observer.disconnect();
      topObserverRef.current = null;
    };
  }, [computeNavbarMargin, recomputeStickyVisibility]);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const mediaQuery = window.matchMedia("(max-width: 768px)");
    const handleChange = (event) => setIsMobileView(event.matches);
    handleChange(mediaQuery);
    mediaQuery.addEventListener("change", handleChange);
    return () => {
      mediaQuery.removeEventListener("change", handleChange);
    };
  }, []);

  useEffect(() => {
    const node = sidebarRef.current;
    if (!node || typeof window === "undefined") return undefined;

    let frame = null;
    const updateHeight = () => {
      const rect = node.getBoundingClientRect();
      setSidebarHeight(rect.height);
    };

    updateHeight();

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(() => {
        if (frame !== null) return;
        frame = window.requestAnimationFrame(() => {
          frame = null;
          updateHeight();
        });
      });
      observer.observe(node);
      return () => {
        observer.disconnect();
        if (frame !== null) {
          window.cancelAnimationFrame(frame);
        }
      };
    }

    const handleResize = () => updateHeight();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, [isSidebarStuck, isMobileView]);

  useEffect(() => {
    registerLessonToggle({ contentLang, setContentLang });
    return () => {
      unregisterLessonToggle();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registerLessonToggle, unregisterLessonToggle, setContentLang]);

  useEffect(() => {
    updateStickyContentLang(contentLang);
  }, [contentLang, updateStickyContentLang]);

  useEffect(() => {
    let frame = null;
    const updateStuck = () => {
      const node = sidebarSentinelRef.current;
      if (!node || typeof window === "undefined") return;
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--navbar-height");
      const parsed = parseFloat(raw);
      const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
      const rect = node.getBoundingClientRect();
      const stickAt = navbarHeight + 4;
      const unstickAt = navbarHeight + 12;
      setIsSidebarStuck((prev) => {
        if (prev) {
          return rect.top <= unstickAt;
        }
        return rect.top <= stickAt;
      });
    };

    const handleScroll = () => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        updateStuck();
      });
    };

    updateStuck();
    window.addEventListener("scroll", handleScroll, { passive: true });
    window.addEventListener("resize", handleScroll);

    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("resize", handleScroll);
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
    };
  }, []);

  useEffect(() => {
    const handleResize = () => {
      rebuildObserver();
    };
    if (typeof window !== "undefined") {
      window.addEventListener("resize", handleResize);
    }
    return () => {
      if (typeof window !== "undefined") {
        window.removeEventListener("resize", handleResize);
      }
    };
  }, [rebuildObserver]);

  useEffect(() => {
    if (!activeId || typeof window === "undefined") return;
    if (!isMobileView) return;
    if (!hasSectionScrollRef.current) {
      hasSectionScrollRef.current = true;
      return;
    }
    if (!shouldAutoScrollRef.current) return;
    shouldAutoScrollRef.current = false;

    window.requestAnimationFrame(() => {
      const header = document.querySelector(".lesson-content-shell .lc-head");
      if (!header) return;
      const raw = getComputedStyle(document.documentElement).getPropertyValue("--navbar-height");
      const parsed = parseFloat(raw);
      const navbarHeight = Number.isNaN(parsed) ? 0 : parsed;
      const sidebarOffset = isMobileView ? sidebarHeight : 0;
      const gap = 1.6;
      const top =
        header.getBoundingClientRect().top +
        window.scrollY -
        navbarHeight -
        sidebarOffset -
        gap;
      window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    });
  }, [activeId, isMobileView, sidebarHeight]);

  useEffect(() => {
    rebuildObserver();
  }, [rebuildObserver, sidebarHeight, isSidebarStuck, isMobileView]);

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
        observerRef.current = null;
      }
      headNodesRef.current.clear();
      visibleHeadIdsRef.current.clear();
      setShowStickyToggle(false);
    };
  }, [setShowStickyToggle]);



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
        const focus_en = payload.focus_en ?? payload.focus ?? null;
        const focus_th = payload.focus_th ?? null;
        const backstory_en = payload.backstory_en ?? payload.backstory ?? null;
        const backstory_th = payload.backstory_th ?? null;

        let headerImageUrl = payload.header_image_url ?? null;
        let headerImagePath = payload.header_image_path ?? null;
        const headerImgRaw = payload.header_img ?? null;

        if (!headerImageUrl && headerImgRaw && /^https?:\/\//i.test(headerImgRaw)) {
          headerImageUrl = headerImgRaw;
        }

        if (!headerImageUrl) {
          const normalizedPath = normalizeHeaderImagePath(headerImagePath || headerImgRaw);
          if (normalizedPath) {
            headerImagePath = normalizedPath;
            const { data } = supabaseClient.storage
              .from("lesson-images")
              .getPublicUrl(normalizedPath);
            headerImageUrl = data?.publicUrl ?? null;
          }
        }

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
          focus_en,
          focus_th,
          backstory_en,
          backstory_th,
          // convenient content-language strings too (if you still want them)
          title: payload.title ?? null,
          subtitle: payload.subtitle ?? null,
          focus: payload.focus ?? null,
          backstory: payload.backstory ?? null,
          header_img: headerImgRaw,
          header_image_path: headerImagePath,
          header_image_url: headerImageUrl,
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

        const otherLang = contentLang === "th" ? "en" : "th";
        prefetchResolvedLesson(id, otherLang);

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

        // 3) sign conversation audio (all three versions, parallelized)
        if (lsn.conversation_audio_url) {
          const signAudio = async (path) => {
            const { data, error } = await supabaseClient.storage
              .from("lesson-audio")
              .createSignedUrl(path, 2 * 60 * 60);
            if (error) throw error;
            return data?.signedUrl ?? null;
          };

          try {
            const basePath = lsn.conversation_audio_url;
            const noBgPath = basePath.replace(".mp3", "_no_bg.mp3");
            const bgPath = basePath.replace(".mp3", "_bg.mp3");

            const [mainResult, noBgResult, bgResult] = await Promise.allSettled([
              signAudio(basePath),
              signAudio(noBgPath),
              signAudio(bgPath),
            ]);

            if (mainResult.status === "fulfilled") {
              setAudioUrl(mainResult.value);
            } else {
              console.warn("Main audio signed URL error:", mainResult.reason);
              setAudioUrl(null);
            }

            if (noBgResult.status === "fulfilled") {
              setAudioUrlNoBg(noBgResult.value);
            } else {
              console.warn("No-bg audio signed URL error:", noBgResult.reason);
              setAudioUrlNoBg(null);
            }

            if (bgResult.status === "fulfilled") {
              setAudioUrlBg(bgResult.value);
            } else {
              console.warn("Background audio signed URL error:", bgResult.reason);
              setAudioUrlBg(null);
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

        // 4) fetch audio snippet index + phrases audio snippets (in parallel)
        if (lsn.lesson_external_id) {
          try {
            if (lsn.id) {
              const [idx, phrasesAudio] = await Promise.all([
                fetchSnippets(lsn.lesson_external_id, lsn.id),
                fetchPhrasesSnippets(lsn.id),
              ]);
              const mergedByKey = {
                ...(idx?.by_key || {}),
                ...(phrasesAudio?.by_key || {}),
              };
              setSnipIdx({ ...(idx || {}), by_key: mergedByKey });
              setPhrasesSnipIdx(phrasesAudio || {});
            } else {
              const idx = await fetchSnippets(lsn.lesson_external_id, lsn.id);
              setSnipIdx(idx || {});
              setPhrasesSnipIdx({});
            }
          } catch (err) {
            console.error("Error fetching audio snippets:", err);
            setSnipIdx({});
            setPhrasesSnipIdx({});
          }
        } else {
          setSnipIdx({});
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
  const pickUiString = (enValue, thValue, fallback = "") =>
    uiLang === "th"
      ? thValue ?? enValue ?? fallback ?? ""
      : enValue ?? thValue ?? fallback ?? "";

  const headerTitle = pickUiString(lesson.title_en, lesson.title_th, lesson.title);
  const headerFocus = pickUiString(lesson.focus_en, lesson.focus_th, lesson.focus);
  const headerBackstory = pickUiString(
    lesson.backstory_en,
    lesson.backstory_th,
    lesson.backstory
  );
  const sectionMenu = buildSectionMenu({
    sections,
    questions,
    transcript,
    practiceExercises,
    lessonPhrases,
    isLocked,
    uiLang,
  });
  const prepareSection = sections.find((s) => s.type === "prepare");
  return (
    <main>
      <div className="lesson-page-container">
        {/* Header */}
        <LessonHeader
          lessonId={lesson.id}
          stage={lesson.stage}
          level={lesson.level}
          lessonOrder={lesson.lesson_order}
          title={headerTitle}
          headerImageUrl={lesson.header_image_url}
          headerImagePath={lesson.header_image_path}
          focus={headerFocus}
          backstory={headerBackstory}
        />

        <div className="lesson-content-container">
          {/* Prepare (vocab) card */}
          {prepareSection && (
            <PrepareCard
              section={prepareSection}
              audioIndex={snipIdx}
              uiLang={uiLang}
              isLocked={isLocked}
            />
          )}

          {/* Listen CTA */}
          {(audioUrl || audioUrlNoBg || audioUrlBg) && (
            <div className="listen-cta-wrapper">
              <button
                type="button"
                className={`listen-cta${showStickyPlayer ? " is-active" : ""}`}
                onClick={() => {
                  if (showStickyPlayer) {
                    setShowStickyPlayer(false);
                    setShouldAutoPlay(false);
                  } else {
                    setShowStickyPlayer(true);
                    setShouldAutoPlay(true);
                  }
                }}
                disabled={isLocked}
              >
                <img
                  src={showStickyPlayer ? "/images/pause-audio-lesson.webp" : "/images/play-audio-lesson.webp"}
                  alt="Play"
                  className="listen-cta-icon"
                />
                <span>{showStickyPlayer ? t("listenCta.playing", uiLang) : t("listenCta.listen", uiLang)}</span>
              </button>
            </div>
          )}

          <div ref={topSentinelRef} className="lesson-top-sentinel" aria-hidden="true" />

          {/* Body */}
          <div className="lesson-body">
            <div ref={sidebarSentinelRef} className="lesson-sidebar-sentinel" aria-hidden="true" />
            <LessonSidebar
              ref={sidebarRef}
              sections={sections}
              questions={questions}
              transcript={transcript}
              practiceExercises={practiceExercises}
              lessonPhrases={lessonPhrases}
              activeId={activeId}
              onSelect={handleSelectSection}
              contentLang={contentLang}
              lesson={lesson}
              isLocked={isLocked}
              isStuck={isSidebarStuck}
              isMobileView={isMobileView}
            />
            <LessonContent
              sections={sections}
              questions={questions}
              transcript={transcript}
              practiceExercises={practiceExercises}
              lessonPhrases={lessonPhrases}
              activeId={activeId}
              sectionMenu={sectionMenu}
              uiLang={uiLang}
              snipIdx={snipIdx}
              phrasesSnipIdx={phrasesSnipIdx}
              contentLang={contentLang}
              setContentLang={setContentLang}
              images={images}
              isLocked={isLocked}
              registerStickyHeaders={registerStickyHeaders}
              topSentinelRef={topSentinelRef}
              toggleLoginModal={toggleLoginModal}
              toggleSignupModal={toggleSignupModal}
              onSelectSection={handleSelectSection}
            />
          </div>
        </div>

        {/* Lesson Navigation Banner */}
        <div className="lesson-nav-banner-wrapper">
          <LessonNavigationBanner
            prevLesson={prevLesson}
            nextLesson={nextLesson}
            currentLesson={lesson}
            onMarkComplete={(isCompleted) => {
              console.log(`Lesson ${lesson.lesson_external_id} marked as ${isCompleted ? 'completed' : 'incomplete'}`);
              // TODO: Add actual completion tracking logic here
            }}
          />
        </div>

        {/* Discussion */}
        <LessonDiscussion lessonId={lesson.id} isAdmin={false} />
      </div>

      {/* Sticky audio bar */}
      {showStickyPlayer && (audioUrl || audioUrlNoBg || audioUrlBg) && (
        <AudioBar
          audioSrc={audioUrl}
          audioSrcNoBg={audioUrlNoBg}
          audioSrcBg={audioUrlBg}
          description={headerBackstory}
          isLocked={isLocked}
          variant="sticky"
          focusText={headerFocus}
          shouldAutoPlay={shouldAutoPlay}
          onAutoPlayComplete={() => setShouldAutoPlay(false)}
        />
      )}
    </main>
  );
}

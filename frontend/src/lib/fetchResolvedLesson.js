import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";

const CACHE_TTL_MS = 5 * 60 * 1000;
const resolvedLessonCache = new Map();

function cacheKey(lessonId, lang) {
  return `${lessonId}:${lang}`;
}

function getCachedLesson(lessonId, lang) {
  const key = cacheKey(lessonId, lang);
  const entry = resolvedLessonCache.get(key);
  if (!entry) return null;
  if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
    resolvedLessonCache.delete(key);
    return null;
  }
  return entry.payload;
}

function setCachedLesson(lessonId, lang, payload) {
  const key = cacheKey(lessonId, lang);
  resolvedLessonCache.set(key, { payload, timestamp: Date.now() });
}

export async function fetchResolvedLesson(lessonId, lang = "en") {
  const cached = getCachedLesson(lessonId, lang);
  if (cached) return cached;

  // Get the current session to include auth token (refresh if expired)
  let {
    data: { session },
    error: sessionError,
  } = await supabaseClient.auth.getSession();

  if (!sessionError && session?.expires_at) {
    const now = Math.floor(Date.now() / 1000);
    if (session.expires_at <= now) {
      const { data: refreshed, error: refreshError } = await supabaseClient.auth.refreshSession();
      if (!refreshError) {
        session = refreshed.session ?? null;
      }
    }
  }

  const headers = {
    'Content-Type': 'application/json',
  };

  // Add Authorization header if user is logged in
  if (session?.access_token) {
    headers['Authorization'] = `Bearer ${session.access_token}`;
  }

  const res = await fetch(`${API_BASE_URL}/api/lessons/${lessonId}/resolved?lang=${lang}`, {
    headers,
  });

  if (!res.ok) throw new Error(`Failed to fetch lesson (${res.status})`);
  const payload = await res.json();
  setCachedLesson(lessonId, lang, payload);
  return payload;
}

export async function prefetchResolvedLesson(lessonId, lang = "en") {
  const cached = getCachedLesson(lessonId, lang);
  if (cached) return;
  try {
    await fetchResolvedLesson(lessonId, lang);
  } catch (err) {
    console.warn("Prefetch lesson failed:", err);
  }
}

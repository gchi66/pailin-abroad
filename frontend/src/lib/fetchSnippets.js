// src/lib/fetchSnippets.js
import supabaseClient from "../supabaseClient";

export async function fetchSnippets(lessonExternalId, lessonId = null) {
  const { data, error } = await supabaseClient
    .from("audio_snippets")
    .select("section, seq, storage_path, audio_key")
    .eq("lesson_external_id", lessonExternalId);

  if (error) throw error;

  // Build a quick lookup: section → seq → snippet
  const idx = {};
  data.forEach((s) => {
    if (!idx[s.section]) idx[s.section] = {};
    idx[s.section][s.seq] = s;
  });

  // Build a by_key lookup for standard audio (where audio_key is populated)
  const by_key = {};
  data.forEach((s) => {
    if (s.audio_key) {
      by_key[s.audio_key] = s;
    }
  });

  // If lessonId is provided, also fetch phrases audio snippets and add to by_key
  if (lessonId) {
    try {
      const phrasesData = await fetchPhrasesSnippets(lessonId);
      if (phrasesData.by_key) {
        // Merge phrases audio snippets into by_key lookup
        Object.assign(by_key, phrasesData.by_key);
      }
    } catch (phrasesError) {
      console.warn("Failed to fetch phrases audio snippets:", phrasesError);
      // Don't fail the whole function if phrases audio fails
    }
  }

  return { ...idx, by_key };
}

// Fetch phrases audio snippets from the phrases_audio_snippets table
export async function fetchPhrasesSnippets(lessonId) {
  // First get all phrases for this lesson via the lesson_phrases junction table
  const { data: lessonPhrases, error: phrasesError } = await supabaseClient
    .from("lesson_phrases")
    .select("phrases(id, phrase)")
    .eq("lesson_id", lessonId);

  if (phrasesError) throw phrasesError;

  if (!lessonPhrases || lessonPhrases.length === 0) {
    return {};
  }

  // Extract phrase data from the nested structure
  const phrases = lessonPhrases
    .map(lp => lp.phrases)
    .filter(p => p && p.id);

  if (phrases.length === 0) {
    return {};
  }

  // Get phrase IDs
  const phraseIds = phrases.map(p => p.id);

  // Fetch audio snippets for these phrases (including audio_key)
  const { data, error } = await supabaseClient
    .from("phrases_audio_snippets")
    .select("phrase_id, variant, seq, storage_path, audio_key")
    .in("phrase_id", phraseIds);

  if (error) throw error;

  // Build a lookup: phrase_id → variant → seq → snippet
  const idx = {};
  data.forEach((s) => {
    if (!idx[s.phrase_id]) idx[s.phrase_id] = {};
    if (!idx[s.phrase_id][s.variant]) idx[s.phrase_id][s.variant] = {};
    idx[s.phrase_id][s.variant][s.seq] = s;
  });

  // Build by_key lookup for phrases audio (where audio_key is populated)
  const by_key = {};
  data.forEach((s) => {
    if (s.audio_key) {
      by_key[s.audio_key] = s;
    }
  });

  // Also create a phrase text to phrase_id mapping for easier lookup
  const phraseTextToId = {};
  phrases.forEach(p => {
    phraseTextToId[p.phrase] = p.id;
  });

  return { idx, phraseTextToId, by_key };
}

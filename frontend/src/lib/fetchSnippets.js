// src/lib/fetchSnippets.js
import supabaseClient from "../supabaseClient";

export async function fetchSnippets(lessonExternalId) {
  const { data, error } = await supabaseClient
    .from("audio_snippets")
    .select("section, seq, storage_path")
    .eq("lesson_external_id", lessonExternalId);

  if (error) throw error;

  // Build a quick lookup: section → seq → snippet
  const idx = {};
  data.forEach((s) => {
    if (!idx[s.section]) idx[s.section] = {};
    idx[s.section][s.seq] = s;
  });
  return idx;
}

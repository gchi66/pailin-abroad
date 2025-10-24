import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";

export async function fetchResolvedLesson(lessonId, lang = "en") {
  // Get the current session to include auth token
  const { data: { session } } = await supabaseClient.auth.getSession();

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
  return await res.json();
}

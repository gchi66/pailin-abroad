export async function fetchResolvedLesson(lessonId, lang = "en") {
  const res = await fetch(`/api/lessons/${lessonId}/resolved?lang=${lang}`);
  if (!res.ok) throw new Error(`Failed to fetch lesson (${res.status})`);
  return await res.json();
}

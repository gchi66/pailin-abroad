import supabaseClient from "../supabaseClient";

export function buildSectionUnitKey(activeId) {
  return `section:${activeId}`;
}

function stripSectionUnitKey(sectionKey) {
  if (typeof sectionKey !== "string" || !sectionKey.startsWith("section:")) {
    return null;
  }
  const rawId = sectionKey.slice("section:".length);
  return rawId || null;
}

export async function fetchLessonResumeActiveId({
  userId,
  lessonId,
}) {
  const { data: progressRow, error: progressError } = await supabaseClient
    .from("user_lesson_progress")
    .select("last_unit_type, last_unit_key")
    .eq("user_id", userId)
    .eq("lesson_id", lessonId)
    .maybeSingle();

  if (progressError) {
    throw progressError;
  }

  if (!progressRow?.last_unit_key) {
    return null;
  }

  if (progressRow.last_unit_type === "section") {
    const rawId = stripSectionUnitKey(progressRow.last_unit_key);
    if (!rawId || rawId === "prepare") {
      return null;
    }
    return rawId;
  }

  if (progressRow.last_unit_type === "exercise") {
    const { data: unitRow, error: unitError } = await supabaseClient
      .from("user_lesson_unit_progress")
      .select("section_key")
      .eq("user_id", userId)
      .eq("lesson_id", lessonId)
      .eq("unit_key", progressRow.last_unit_key)
      .maybeSingle();

    if (unitError) {
      throw unitError;
    }

    const rawId = stripSectionUnitKey(unitRow?.section_key);
    if (!rawId || rawId === "prepare") {
      return null;
    }
    return rawId;
  }

  return null;
}

export async function saveSectionVisitProgress({
  userId,
  lessonId,
  sectionKey,
}) {
  const now = new Date().toISOString();

  const { error: progressError } = await supabaseClient
    .from("user_lesson_progress")
    .upsert(
      {
        user_id: userId,
        lesson_id: lessonId,
        started_at: now,
        last_unit_type: "section",
        last_unit_key: sectionKey,
      },
      {
        onConflict: "user_id,lesson_id",
      }
    );

  if (progressError) {
    throw progressError;
  }

  const { error: unitError } = await supabaseClient
    .from("user_lesson_unit_progress")
    .upsert(
      {
        user_id: userId,
        lesson_id: lessonId,
        unit_type: "section",
        unit_key: sectionKey,
        is_completed: true,
        last_visited_at: now,
        completed_at: now,
      },
      {
        onConflict: "user_id,lesson_id,unit_key",
      }
    );

  if (unitError) {
    throw unitError;
  }
}

export async function saveExerciseCompletionProgress({
  userId,
  lessonId,
  unitKey,
  sectionKey,
  isCompleted,
}) {
  const now = new Date().toISOString();
  const progressRecord = {
    user_id: userId,
    lesson_id: lessonId,
    started_at: now,
    last_unit_type: "exercise",
    last_unit_key: unitKey,
  };

  if (isCompleted) {
    progressRecord.is_completed = true;
    progressRecord.completed_at = now;
  }

  const { error: progressError } = await supabaseClient
    .from("user_lesson_progress")
    .upsert(progressRecord, {
      onConflict: "user_id,lesson_id",
    });

  if (progressError) {
    throw progressError;
  }

  const { error: unitError } = await supabaseClient
    .from("user_lesson_unit_progress")
    .upsert(
      {
        user_id: userId,
        lesson_id: lessonId,
        unit_type: "exercise",
        unit_key: unitKey,
        section_key: sectionKey || null,
        is_completed: true,
        last_visited_at: now,
        completed_at: now,
      },
      {
        onConflict: "user_id,lesson_id,unit_key",
      }
    );

  if (unitError) {
    throw unitError;
  }
}

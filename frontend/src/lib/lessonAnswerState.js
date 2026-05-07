import supabaseClient from "../supabaseClient";

export function buildExerciseUnitKey(exerciseId) {
  return `exercise:${exerciseId}`;
}

export function buildComprehensionUnitKey() {
  return "exercise:comprehension_quiz";
}

export async function fetchLessonAnswerStates({ userId, lessonId }) {
  if (!userId || !lessonId) {
    return {};
  }

  const { data, error } = await supabaseClient
    .from("user_lesson_answer_state")
    .select("unit_key, answer_payload")
    .eq("user_id", userId)
    .eq("lesson_id", lessonId);

  if (error) {
    throw error;
  }

  return (data || []).reduce((acc, row) => {
    if (!row?.unit_key) {
      return acc;
    }
    acc[row.unit_key] = row.answer_payload ?? {};
    return acc;
  }, {});
}

export async function saveLessonAnswerState({
  userId,
  lessonId,
  unitKey,
  answerPayload,
  stateKey = "default",
}) {
  const { error } = await supabaseClient
    .from("user_lesson_answer_state")
    .upsert(
      {
        user_id: userId,
        lesson_id: lessonId,
        unit_key: unitKey,
        state_key: stateKey,
        answer_payload: answerPayload,
      },
      {
        onConflict: "user_id,lesson_id,unit_key,state_key",
      }
    );

  if (error) {
    throw error;
  }
}

export async function clearLessonAnswerState({
  userId,
  lessonId,
  unitKey,
  stateKey = "default",
}) {
  const { error } = await supabaseClient
    .from("user_lesson_answer_state")
    .delete()
    .eq("user_id", userId)
    .eq("lesson_id", lessonId)
    .eq("unit_key", unitKey)
    .eq("state_key", stateKey);

  if (error) {
    throw error;
  }
}

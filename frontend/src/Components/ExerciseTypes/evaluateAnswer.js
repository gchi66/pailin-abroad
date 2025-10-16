async function evaluateAnswer({
  userId,
  exerciseType,
  userAnswer,
  correctAnswer,
  sourceType,
  exerciseId,
  questionNumber,
  questionPrompt,
  extra = {},
}) {
  if (!userId) {
    throw new Error("You need to be logged in to check your answer.");
  }
  if (!exerciseType) {
    throw new Error("Missing exercise type for evaluation.");
  }
  if (!sourceType) {
    throw new Error("Missing exercise source type.");
  }

  const payload = {
    user_id: userId,
    exercise_type: exerciseType,
    user_answer:
      typeof userAnswer === "string" ? userAnswer : JSON.stringify(userAnswer),
    correct_answer:
      typeof correctAnswer === "string"
        ? correctAnswer
        : JSON.stringify(correctAnswer),
    source_type: sourceType,
  };

  if (sourceType === "bank" && exerciseId != null) {
    payload.exercise_bank_id = exerciseId;
  } else if (sourceType === "practice" && exerciseId != null) {
    payload.practice_exercise_id = exerciseId;
  }

  if (typeof questionNumber !== "undefined") {
    payload.question_number = questionNumber;
  }

  if (questionPrompt) {
    payload.question_prompt = questionPrompt;
  }

  if (extra && typeof extra === "object") {
    Object.assign(payload, extra);
  }

  const response = await fetch("/api/evaluate_answer", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const message = data?.error || "Unable to evaluate answer right now.";
    throw new Error(message);
  }

  return data;
}

export default evaluateAnswer;

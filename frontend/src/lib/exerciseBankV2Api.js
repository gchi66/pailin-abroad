import { API_BASE_URL } from "../config/api";
import supabaseClient from "../supabaseClient";

async function getAuthHeaders() {
  const {
    data: { session },
  } = await supabaseClient.auth.getSession();

  if (!session?.access_token) {
    throw new Error("Please sign in to use the Exercise Bank.");
  }

  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

async function request(path, options = {}) {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...headers, ...(options.headers || {}) },
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || "Unable to load the Exercise Bank.");
  }
  return payload;
}

export const fetchExerciseBankTopics = (options = {}) =>
  request("/api/exercise-bank-v2/topics", options);

export const fetchExerciseBankTopic = (topicId, options = {}) =>
  request(`/api/exercise-bank-v2/topics/${topicId}`, options);

export const fetchExerciseBankSet = (topicId, setNumber, options = {}) =>
  request(`/api/exercise-bank-v2/topics/${topicId}/sets/${setNumber}`, options);

export const submitExerciseBankAnswer = (questionId, userAnswer) =>
  request(`/api/exercise-bank-v2/questions/${questionId}/answer`, {
    method: "POST",
    body: JSON.stringify({ user_answer: userAnswer }),
  });

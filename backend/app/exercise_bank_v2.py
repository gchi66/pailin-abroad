"""Authenticated read API for the normalized Exercise Bank v2."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable

from flask import Blueprint, jsonify, request

from app.ai_evaluate import (
    _personalize_feedback,
    _remove_correct_answer,
    contractions_equivalent,
    evaluate_with_gpt,
)
from app.supabase_client import create_auth_client, supabase_admin


exercise_bank_v2 = Blueprint("exercise_bank_v2", __name__)

TOPIC_SELECT = (
    "id,topic,display_title,category,sub_category,lesson_external_id,sort_order,"
    "is_featured,featured_sort_order,content_version"
)
EXERCISE_SELECT = (
    "id,topic_id,exercise_type,display_type,prompt,keywords,sort_order"
)
QUESTION_SELECT = (
    "id,exercise_id,source_number,content,practice_order"
)
EXAMPLE_SELECT = "id,exercise_id,source_number,content,sort_order"
STATE_SELECT = (
    "topic_id,question_id,set_number,set_position,attempt_count,"
    "has_answered_correctly,latest_user_answer,latest_is_correct,latest_ai_score,"
    "latest_ai_feedback_en,latest_ai_feedback_th,last_attempted_at,assigned_content_version"
)
TOPIC_PROGRESS_SELECT = (
    "topic_id,first_completed_at,completed_content_version,version_completed_at"
)

REDACTED_CONTENT_KEYS = frozenset(
    {
        "accepted_answer",
        "accepted_answers",
        "answer",
        "answer_key",
        "answers",
        "answers_v2",
        "correct",
        "correct_answer",
        "correct_answers",
        "correct_choice",
        "correct_index",
        "correct_label",
        "correct_option",
        "correct_raw",
        "expected_answer",
        "expected_answers",
        "is_correct",
        "raw_answer",
        "raw_answers",
        "review_answer",
        "review_answer_meta",
        "solution",
        "solutions",
    }
)


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _authenticated_user_id() -> tuple[str | None, tuple[Any, int] | None]:
    auth_header = request.headers.get("Authorization") or ""
    scheme, separator, token = auth_header.partition(" ")
    if not separator or scheme.lower() != "bearer" or not token.strip():
        return None, (jsonify({"error": "Authorization token required"}), 401)

    try:
        user_response = create_auth_client().auth.get_user(token.strip())
    except Exception:
        return None, (jsonify({"error": "Invalid token"}), 401)

    user = getattr(user_response, "user", None)
    user_id = getattr(user, "id", None)
    if not user_id:
        return None, (jsonify({"error": "Invalid token"}), 401)
    return str(user_id), None


def _sanitize_content(value: Any) -> Any:
    """Recursively remove evaluator-only fields from a question payload."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return value
        if isinstance(parsed, (dict, list)):
            return _sanitize_content(parsed)
        return value
    if isinstance(value, list):
        return [_sanitize_content(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _sanitize_content(item)
            for key, item in value.items()
            if str(key).strip().lower() not in REDACTED_CONTENT_KEYS
        }
    return value


def _sanitize_example_content(value: Any) -> dict[str, Any]:
    """Return display-safe example content, including its intentionally shown solution."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            value = {}
    if not isinstance(value, dict):
        return {}

    sanitized = _sanitize_content(value)
    if not isinstance(sanitized, dict):
        sanitized = {}

    accepted_answers = _answer_values(value.get("accepted_answers") or value.get("answer"))
    if accepted_answers:
        sanitized["example_answer"] = accepted_answers[0]
    if "is_correct" in value:
        sanitized["example_is_correct"] = bool(value.get("is_correct"))
    correct_option = _serialize_answer(value.get("correct_option"))
    if correct_option:
        sanitized["example_correct_option"] = correct_option
    return sanitized


def _eligible_questions(
    questions: Iterable[dict[str, Any]],
    active_exercise_ids: set[Any],
) -> list[dict[str, Any]]:
    eligible = [
        question
        for question in questions
        if question.get("exercise_id") in active_exercise_ids
        and isinstance(question.get("practice_order"), int)
        and question["practice_order"] > 0
    ]
    return sorted(eligible, key=lambda row: (row["practice_order"], row.get("id") or 0))


def _set_number(practice_order: int) -> int:
    return ((practice_order - 1) // 5) + 1


def _set_position(practice_order: int) -> int:
    return ((practice_order - 1) % 5) + 1


def _serialize_answer(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def _deserialize_answer(value: Any) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return value
    return decoded if isinstance(decoded, (dict, list)) else value


def _review_answer(exercise: dict[str, Any], question: dict[str, Any]) -> str:
    content = question.get("content") or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return ""
    if not isinstance(content, dict):
        return ""

    polished_answer = _serialize_answer(content.get("review_answer"))
    if polished_answer:
        return polished_answer

    if exercise.get("exercise_type") == "multiple_choice":
        correct_label = _serialize_answer(content.get("correct_option"))
        correct_option = next(
            (
                option for option in content.get("options") or []
                if isinstance(option, dict)
                and _normalized_answer(option.get("label")) == _normalized_answer(correct_label)
            ),
            None,
        )
        if correct_option:
            option_text = _serialize_answer(correct_option.get("text"))
            return f"{correct_label}. {option_text}" if option_text else correct_label
        return correct_label

    if exercise.get("exercise_type") == "sentence_transform" and content.get("is_correct") is True:
        return "The sentence is correct."

    accepted_answers = content.get("accepted_answers") or []
    if isinstance(accepted_answers, list) and accepted_answers:
        return _serialize_answer(accepted_answers[0])
    return _serialize_answer(accepted_answers)


def _normalized_answer(value: Any) -> str:
    text = _serialize_answer(value).lower().replace("’", "'")
    text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _answer_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [
            serialized
            for serialized in (_serialize_answer(item) for item in value.values())
            if serialized
        ]
    if isinstance(value, list):
        return [
            serialized
            for serialized in (_serialize_answer(item) for item in value)
            if serialized
        ]
    serialized = _serialize_answer(value)
    return [serialized] if serialized else []


def _matches_accepted_answer(user_answer: Any, accepted_answers: Any) -> bool:
    user_values = _answer_values(user_answer)
    expected_values = _answer_values(accepted_answers)
    for user_value in user_values:
        normalized_user = _normalized_answer(user_value)
        for expected_value in expected_values:
            if normalized_user and normalized_user == _normalized_answer(expected_value):
                return True
            if contractions_equivalent(user_value, expected_value):
                return True
    return False


def _boolean_answer(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "correct", "1"}:
            return True
        if normalized in {"false", "no", "incorrect", "0"}:
            return False
    return None


def _deterministic_result(correct: bool, *, kind: str = "answer") -> dict[str, Any]:
    if correct:
        return {
            "correct": True,
            "score": 1.0,
            "feedback_en": "Great job! Your answer is correct.",
            "feedback_th": "เยี่ยมมาก! คำตอบของคุณถูกต้อง",
            "grading_method": "deterministic",
            "ai_model": None,
        }
    if kind == "judgment":
        feedback_en = "Take another look at whether the original sentence is correct."
        feedback_th = "ลองตรวจดูอีกครั้งว่าประโยคเดิมถูกต้องหรือไม่"
    else:
        feedback_en = "That answer is not correct yet. Try again."
        feedback_th = "คำตอบนี้ยังไม่ถูกต้อง ลองอีกครั้ง"
    return {
        "correct": False,
        "score": 0.0,
        "feedback_en": feedback_en,
        "feedback_th": feedback_th,
        "grading_method": "deterministic",
        "ai_model": None,
    }


def _ai_result(
    *,
    exercise_type: str,
    instruction: str,
    question_text: str,
    user_answer: Any,
    accepted_answers: Any,
    review_answer: str,
) -> dict[str, Any]:
    user_answer_raw = _serialize_answer(user_answer)
    accepted_raw = _serialize_answer(accepted_answers)
    parsed = evaluate_with_gpt(
        exercise_type=exercise_type,
        question=question_text,
        user_answer=user_answer_raw,
        correct_answer=accepted_raw,
        instruction=instruction,
        review_answer=review_answer,
    )
    correct = bool(parsed.get("correct"))
    try:
        score = float(parsed.get("score"))
    except (TypeError, ValueError):
        score = 1.0 if correct else 0.0
    score = max(0.0, min(1.0, score))
    feedback_en = _personalize_feedback(parsed.get("feedback_en") or "")
    feedback_th = parsed.get("feedback_th") or ""
    for private_answer in (accepted_raw, review_answer):
        feedback_en = _remove_correct_answer(feedback_en, private_answer)
        feedback_th = _remove_correct_answer(feedback_th, private_answer)
    return {
        "correct": correct,
        "score": score,
        "feedback_en": feedback_en,
        "feedback_th": feedback_th,
        "grading_method": "ai",
        "ai_model": "gpt-4o-mini",
    }


def _grade_question(
    exercise: dict[str, Any], question: dict[str, Any], user_answer: Any
) -> dict[str, Any]:
    exercise_type = exercise.get("exercise_type")
    content = question.get("content") or {}
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            content = {}
    if not isinstance(content, dict):
        raise ValueError("Question content is invalid")

    if exercise_type == "multiple_choice":
        submitted = user_answer
        if isinstance(user_answer, dict):
            submitted = (
                user_answer.get("label")
                or user_answer.get("selected")
                or user_answer.get("answer")
            )
        if isinstance(submitted, list):
            submitted = submitted[0] if len(submitted) == 1 else submitted
        correct_option = content.get("correct_option")
        if not _serialize_answer(correct_option):
            raise ValueError("Question has no correct option")
        return _deterministic_result(
            _normalized_answer(submitted) == _normalized_answer(correct_option)
        )

    accepted_answers = content.get("accepted_answers") or []
    instruction = _serialize_answer(exercise.get("prompt"))
    review_answer = _serialize_answer(content.get("review_answer"))
    question_text = (
        content.get("stem")
        or content.get("text")
        or ""
    )

    if exercise_type == "sentence_transform" and "is_correct" in content:
        if not isinstance(user_answer, dict):
            raise ValueError(
                "Correct-or-incorrect questions require a judgment and optional rewrite"
            )
        judgment = _boolean_answer(
            user_answer.get("marked_as_correct", user_answer.get("is_correct"))
        )
        if judgment is None:
            judgment = _boolean_answer(user_answer.get("judgment"))
        if judgment is None:
            raise ValueError("A correct-or-incorrect judgment is required")
        expected_judgment = bool(content.get("is_correct"))
        if judgment != expected_judgment:
            return _deterministic_result(False, kind="judgment")
        if expected_judgment:
            return _deterministic_result(True)
        rewrite = (
            user_answer.get("rewrite")
            or user_answer.get("answer")
            or user_answer.get("text")
        )
        if not _serialize_answer(rewrite):
            return _deterministic_result(False)
        if _matches_accepted_answer(rewrite, accepted_answers):
            return _deterministic_result(True)
        return _ai_result(
            exercise_type="sentence_transform",
            instruction=instruction,
            question_text=question_text,
            user_answer=rewrite,
            accepted_answers=accepted_answers,
            review_answer=review_answer,
        )

    if exercise_type == "fill_blank":
        if _matches_accepted_answer(user_answer, accepted_answers):
            return _deterministic_result(True)
        if not accepted_answers:
            raise ValueError("Question has no accepted answers")
        return _ai_result(
            exercise_type="fill_blank",
            instruction=instruction,
            question_text=question_text,
            user_answer=user_answer,
            accepted_answers=accepted_answers,
            review_answer=review_answer,
        )

    if exercise_type == "sentence_transform":
        if _matches_accepted_answer(user_answer, accepted_answers):
            return _deterministic_result(True)
        if not accepted_answers:
            raise ValueError("Question has no accepted answers")
        return _ai_result(
            exercise_type="sentence_transform",
            instruction=instruction,
            question_text=question_text,
            user_answer=user_answer,
            accepted_answers=accepted_answers,
            review_answer=review_answer,
        )

    if exercise_type in {"open", "open_ended"}:
        return _ai_result(
            exercise_type="open",
            instruction=instruction,
            question_text=question_text,
            user_answer=user_answer,
            accepted_answers=accepted_answers,
            review_answer=review_answer,
        )

    raise ValueError(f"Unsupported exercise type: {exercise_type}")


def _progress_payload(
    topic: dict[str, Any],
    questions: list[dict[str, Any]],
    state_by_question: dict[Any, dict[str, Any]],
    topic_progress: dict[str, Any] | None,
) -> dict[str, Any]:
    total_questions = len(questions)
    total_sets = math.ceil(total_questions / 5) if total_questions else 0
    mastered_question_ids = {
        question["id"]
        for question in questions
        if state_by_question.get(question.get("id"), {}).get("has_answered_correctly") is True
    }

    completed_sets = 0
    for set_number in range(1, total_sets + 1):
        set_questions = [
            question
            for question in questions
            if _set_number(question["practice_order"]) == set_number
        ]
        if set_questions and all(question["id"] in mastered_question_ids for question in set_questions):
            completed_sets += 1

    progress = topic_progress or {}
    content_version = int(topic.get("content_version") or 1)
    completed_version = progress.get("completed_content_version")
    all_current_questions_mastered = bool(total_questions) and len(mastered_question_ids) == total_questions
    historically_completed = bool(progress.get("first_completed_at")) or all_current_questions_mastered

    return {
        "total_questions": total_questions,
        "total_sets": total_sets,
        "mastered_questions": len(mastered_question_ids),
        "completed_sets": completed_sets,
        "is_completed": historically_completed,
        "is_current_version_completed": (
            all_current_questions_mastered
            or (
                isinstance(completed_version, int)
                and completed_version >= content_version
            )
        ),
        "has_new_content": (
            historically_completed
            and isinstance(completed_version, int)
            and completed_version < content_version
        ),
        "first_completed_at": progress.get("first_completed_at"),
        "completed_content_version": completed_version,
        "version_completed_at": progress.get("version_completed_at"),
    }


def _topic_payload(topic: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": topic.get("id"),
        "topic": topic.get("topic"),
        "display_title": topic.get("display_title"),
        "category": topic.get("category"),
        "sub_category": topic.get("sub_category"),
        "lesson_external_id": topic.get("lesson_external_id"),
        "sort_order": topic.get("sort_order"),
        "is_featured": bool(topic.get("is_featured")),
        "featured_sort_order": topic.get("featured_sort_order"),
        "content_version": int(topic.get("content_version") or 1),
        "progress": progress,
    }


def _fetch_topics() -> list[dict[str, Any]]:
    query = (
        supabase_admin.table("exercise_bank_topics")
        .select(TOPIC_SELECT)
        .eq("is_active", True)
        .order("sort_order")
    )
    category = (request.args.get("category") or "").strip()
    if category:
        query = query.eq("category", category)
    if (request.args.get("featured") or "").strip().lower() in {"1", "true", "yes"}:
        query = query.eq("is_featured", True)
    return _rows(query.execute())


def _fetch_topic(topic_id: int) -> dict[str, Any] | None:
    rows = _rows(
        supabase_admin.table("exercise_bank_topics")
        .select(TOPIC_SELECT)
        .eq("id", topic_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return rows[0] if rows else None


def _fetch_exercises(topic_ids: list[Any]) -> list[dict[str, Any]]:
    if not topic_ids:
        return []
    return _rows(
        supabase_admin.table("exercise_bank_exercises")
        .select(EXERCISE_SELECT)
        .in_("topic_id", topic_ids)
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )


def _fetch_questions(exercise_ids: list[Any]) -> list[dict[str, Any]]:
    if not exercise_ids:
        return []
    return _rows(
        supabase_admin.table("exercise_bank_questions")
        .select(QUESTION_SELECT)
        .in_("exercise_id", exercise_ids)
        .eq("is_active", True)
        .eq("is_example", False)
        .order("practice_order")
        .execute()
    )


def _fetch_examples(exercise_ids: list[Any]) -> list[dict[str, Any]]:
    if not exercise_ids:
        return []
    return _rows(
        supabase_admin.table("exercise_bank_questions")
        .select(EXAMPLE_SELECT)
        .in_("exercise_id", exercise_ids)
        .eq("is_active", True)
        .eq("is_example", True)
        .order("sort_order")
        .execute()
    )


def _fetch_states(user_id: str, topic_ids: list[Any]) -> list[dict[str, Any]]:
    if not topic_ids:
        return []
    return _rows(
        supabase_admin.table("user_exercise_bank_question_state")
        .select(STATE_SELECT)
        .eq("user_id", user_id)
        .in_("topic_id", topic_ids)
        .execute()
    )


def _fetch_topic_progress(user_id: str, topic_ids: list[Any]) -> list[dict[str, Any]]:
    if not topic_ids:
        return []
    return _rows(
        supabase_admin.table("user_exercise_bank_topic_progress")
        .select(TOPIC_PROGRESS_SELECT)
        .eq("user_id", user_id)
        .in_("topic_id", topic_ids)
        .execute()
    )


def _load_topic_context(user_id: str, topics: list[dict[str, Any]]) -> dict[str, Any]:
    topic_ids = [topic["id"] for topic in topics]
    exercises = _fetch_exercises(topic_ids)
    exercise_by_id = {exercise["id"]: exercise for exercise in exercises}
    exercises_by_topic: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for exercise in exercises:
        exercises_by_topic[exercise.get("topic_id")].append(exercise)

    questions = _fetch_questions(list(exercise_by_id))
    questions_by_topic: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        exercise = exercise_by_id.get(question.get("exercise_id"))
        if exercise:
            questions_by_topic[exercise.get("topic_id")].append(question)
    for topic_id, rows in questions_by_topic.items():
        questions_by_topic[topic_id] = _eligible_questions(rows, set(exercise_by_id))

    examples_by_exercise: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for example in _fetch_examples(list(exercise_by_id)):
        examples_by_exercise[example.get("exercise_id")].append(example)

    states = _fetch_states(user_id, topic_ids)
    states_by_topic: dict[Any, dict[Any, dict[str, Any]]] = defaultdict(dict)
    for state in states:
        states_by_topic[state.get("topic_id")][state.get("question_id")] = state

    progress_by_topic = {
        row.get("topic_id"): row for row in _fetch_topic_progress(user_id, topic_ids)
    }
    return {
        "exercise_by_id": exercise_by_id,
        "exercises_by_topic": exercises_by_topic,
        "questions_by_topic": questions_by_topic,
        "examples_by_exercise": examples_by_exercise,
        "states_by_topic": states_by_topic,
        "progress_by_topic": progress_by_topic,
    }


def _fetch_question_for_grading(
    question_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    question_rows = _rows(
        supabase_admin.table("exercise_bank_questions")
        .select("id,exercise_id,content,practice_order")
        .eq("id", question_id)
        .eq("is_active", True)
        .eq("is_example", False)
        .limit(1)
        .execute()
    )
    if not question_rows:
        return None
    question = question_rows[0]
    if not isinstance(question.get("practice_order"), int) or question["practice_order"] < 1:
        return None

    exercise_rows = _rows(
        supabase_admin.table("exercise_bank_exercises")
        .select(EXERCISE_SELECT)
        .eq("id", question.get("exercise_id"))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not exercise_rows:
        return None
    exercise = exercise_rows[0]

    topic_rows = _rows(
        supabase_admin.table("exercise_bank_topics")
        .select(TOPIC_SELECT)
        .eq("id", exercise.get("topic_id"))
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not topic_rows:
        return None
    return topic_rows[0], exercise, question


def _persist_evaluation(
    *,
    user_id: str,
    question_id: int,
    user_answer_raw: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    is_ai = result.get("grading_method") == "ai"
    response = supabase_admin.rpc(
        "record_exercise_bank_v2_attempt",
        {
            "p_user_id": user_id,
            "p_question_id": question_id,
            "p_user_answer": user_answer_raw,
            "p_is_correct": bool(result.get("correct")),
            "p_grading_method": result.get("grading_method"),
            "p_ai_score": result.get("score") if is_ai else None,
            "p_ai_feedback_en": result.get("feedback_en") if is_ai else None,
            "p_ai_feedback_th": result.get("feedback_th") if is_ai else None,
            "p_ai_model": result.get("ai_model") if is_ai else None,
        },
    ).execute()
    data = getattr(response, "data", None)
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        raise RuntimeError("Progress update returned no result")
    return data


@exercise_bank_v2.route("/api/exercise-bank-v2/topics", methods=["GET"])
def list_topics():
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    try:
        topics = _fetch_topics()
        context = _load_topic_context(user_id, topics)
        payload = []
        for topic in topics:
            topic_id = topic["id"]
            progress = _progress_payload(
                topic,
                context["questions_by_topic"].get(topic_id, []),
                context["states_by_topic"].get(topic_id, {}),
                context["progress_by_topic"].get(topic_id),
            )
            payload.append(_topic_payload(topic, progress))
        return jsonify({"topics": payload}), 200
    except Exception as exc:
        print(f"Error fetching Exercise Bank v2 topics: {exc}", flush=True)
        return jsonify({"error": "Failed to fetch exercise topics"}), 500


@exercise_bank_v2.route("/api/exercise-bank-v2/topics/<int:topic_id>", methods=["GET"])
def get_topic(topic_id: int):
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    try:
        topic = _fetch_topic(topic_id)
        if not topic:
            return jsonify({"error": "Exercise topic not found"}), 404
        context = _load_topic_context(user_id, [topic])
        questions = context["questions_by_topic"].get(topic_id, [])
        state_by_question = context["states_by_topic"].get(topic_id, {})
        progress = _progress_payload(
            topic,
            questions,
            state_by_question,
            context["progress_by_topic"].get(topic_id),
        )

        sets = []
        for set_number in range(1, progress["total_sets"] + 1):
            set_questions = [
                question
                for question in questions
                if _set_number(question["practice_order"]) == set_number
            ]
            mastered = sum(
                state_by_question.get(question["id"], {}).get("has_answered_correctly") is True
                for question in set_questions
            )
            attempted = sum(
                int(state_by_question.get(question["id"], {}).get("attempt_count") or 0) > 0
                for question in set_questions
            )
            sets.append(
                {
                    "set_number": set_number,
                    "question_count": len(set_questions),
                    "attempted_questions": attempted,
                    "mastered_questions": mastered,
                    "is_complete": bool(set_questions) and mastered == len(set_questions),
                }
            )

        next_incomplete = next(
            (row["set_number"] for row in sets if not row["is_complete"]), None
        )
        response_topic = _topic_payload(topic, progress)
        response_topic["sets"] = sets
        response_topic["next_incomplete_set"] = next_incomplete
        return jsonify({"topic": response_topic}), 200
    except Exception as exc:
        print(f"Error fetching Exercise Bank v2 topic {topic_id}: {exc}", flush=True)
        return jsonify({"error": "Failed to fetch exercise topic"}), 500


@exercise_bank_v2.route(
    "/api/exercise-bank-v2/topics/<int:topic_id>/sets/<int:set_number>",
    methods=["GET"],
)
def get_topic_set(topic_id: int, set_number: int):
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    if set_number < 1:
        return jsonify({"error": "Set number must be positive"}), 400
    try:
        topic = _fetch_topic(topic_id)
        if not topic:
            return jsonify({"error": "Exercise topic not found"}), 404
        context = _load_topic_context(user_id, [topic])
        questions = context["questions_by_topic"].get(topic_id, [])
        state_by_question = context["states_by_topic"].get(topic_id, {})
        selected_questions = [
            question
            for question in questions
            if _set_number(question["practice_order"]) == set_number
        ]
        if not selected_questions:
            return jsonify({"error": "Exercise set not found"}), 404

        response_questions = []
        exercise_by_id = context["exercise_by_id"]
        examples_by_exercise = context["examples_by_exercise"]
        for question in selected_questions:
            exercise = exercise_by_id[question["exercise_id"]]
            state = state_by_question.get(question["id"], {})
            response_questions.append(
                {
                    "id": question.get("id"),
                    "source_number": question.get("source_number"),
                    "practice_order": question.get("practice_order"),
                    "set_number": set_number,
                    "set_position": _set_position(question["practice_order"]),
                    "exercise": {
                        "id": exercise.get("id"),
                        "exercise_type": exercise.get("exercise_type"),
                        "display_type": exercise.get("display_type"),
                        "prompt": exercise.get("prompt"),
                        "keywords": exercise.get("keywords"),
                        "examples": [
                            {
                                "id": example.get("id"),
                                "content": _sanitize_example_content(example.get("content") or {}),
                            }
                            for example in examples_by_exercise.get(exercise.get("id"), [])
                        ],
                    },
                    "content": _sanitize_content(question.get("content") or {}),
                    "progress": {
                        "attempt_count": int(state.get("attempt_count") or 0),
                        "has_answered_correctly": bool(state.get("has_answered_correctly")),
                        "latest_user_answer": _deserialize_answer(state.get("latest_user_answer")),
                        "latest_is_correct": state.get("latest_is_correct"),
                        "latest_score": float(state.get("latest_ai_score") or 0),
                        "latest_feedback_en": state.get("latest_ai_feedback_en") or "",
                        "latest_feedback_th": state.get("latest_ai_feedback_th") or "",
                        "review_answer": _review_answer(exercise, question)
                        if int(state.get("attempt_count") or 0) > 0 else "",
                        "last_attempted_at": state.get("last_attempted_at"),
                    },
                }
            )

        mastered = sum(
            question["progress"]["has_answered_correctly"]
            for question in response_questions
        )
        return jsonify(
            {
                "topic": {
                    "id": topic.get("id"),
                    "topic": topic.get("topic"),
                    "display_title": topic.get("display_title"),
                    "category": topic.get("category"),
                    "content_version": int(topic.get("content_version") or 1),
                },
                "set": {
                    "set_number": set_number,
                    "question_count": len(response_questions),
                    "mastered_questions": mastered,
                    "is_complete": mastered == len(response_questions),
                    "questions": response_questions,
                },
            }
        ), 200
    except Exception as exc:
        print(
            f"Error fetching Exercise Bank v2 topic {topic_id} set {set_number}: {exc}",
            flush=True,
        )
        return jsonify({"error": "Failed to fetch exercise set"}), 500


@exercise_bank_v2.route(
    "/api/exercise-bank-v2/questions/<int:question_id>/answer",
    methods=["POST"],
)
def submit_question_answer(question_id: int):
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or "user_answer" not in payload:
        return jsonify({"error": "user_answer is required"}), 400
    user_answer = payload.get("user_answer")
    user_answer_raw = _serialize_answer(user_answer)
    if not user_answer_raw:
        return jsonify({"error": "user_answer cannot be empty"}), 400

    try:
        context = _fetch_question_for_grading(question_id)
        if not context:
            return jsonify({"error": "Exercise question not found"}), 404
        topic, exercise, question = context

        try:
            result = _grade_question(exercise, question, user_answer)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            print(
                f"Exercise Bank v2 AI grading failed question_id={question_id}: {exc}",
                flush=True,
            )
            return jsonify({"error": "Unable to grade this answer right now"}), 502

        progress = _persist_evaluation(
            user_id=user_id,
            question_id=question_id,
            user_answer_raw=user_answer_raw,
            result=result,
        )
        return jsonify(
            {
                "question_id": question_id,
                "topic_id": topic.get("id"),
                "correct": bool(result.get("correct")),
                "score": result.get("score"),
                "feedback_en": result.get("feedback_en") or "",
                "feedback_th": result.get("feedback_th") or "",
                "review_answer": _review_answer(exercise, question),
                "grading_method": result.get("grading_method"),
                "progress": progress,
            }
        ), 200
    except Exception as exc:
        print(
            f"Error submitting Exercise Bank v2 answer question_id={question_id}: {exc}",
            flush=True,
        )
        return jsonify({"error": "Failed to save exercise answer"}), 500

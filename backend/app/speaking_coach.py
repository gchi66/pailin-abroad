"""Authenticated learner-facing API for speaking-coach curriculum and evaluation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import io
import json
import time
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4
import wave

from flask import Blueprint, current_app, g, jsonify, request

from app.config import Config
from app.speaking_coach_evaluator import (
    EVALUATOR_SCHEMA_VERSION,
    PROMPT_VERSION,
    EvaluationStatus,
    EvaluatorError,
    evaluate_speaking_attempt,
)
from app.speaking_coach_cleanup import (
    LEARNER_AUDIO_BUCKET,
    delete_session_audio,
    run_retention_cleanup,
)
from app.supabase_client import create_auth_client, supabase_admin


speaking_coach = Blueprint("speaking_coach", __name__)

PROMPT_AUDIO_BUCKET = "speaking-coach-prompts"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
SUPABASE_PAGE_SIZE = 1000
UNCLEAR_AUDIO_RETRY_LIMIT = 5
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/aac": "audio/aac",
    "audio/m4a": "audio/m4a",
    "audio/mp4": "audio/mp4",
    "audio/x-m4a": "audio/x-m4a",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mp3",
    "audio/wav": "audio/wav",
    "audio/wave": "audio/wav",
    "audio/vnd.wave": "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/aiff": "audio/aiff",
    "audio/ogg": "audio/ogg",
    "audio/flac": "audio/flac",
}
AUDIO_FILE_EXTENSIONS = {
    "audio/aac": ".aac",
    "audio/m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/aiff": ".aiff",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
}
LESSON_SELECT = "id,lesson_external_id,title,title_th"
PRACTICE_SET_SELECT = "id,practice_type,tip_en,tip_th,sort_order"
QUESTION_SELECT = (
    "id,practice_set_id,sort_order,prompt_en,prompt_th,examples,prompt_audio_key"
)


def _looks_like_wav(audio_bytes: bytes) -> bool:
    return (
        len(audio_bytes) >= 12
        and audio_bytes[:4] == b"RIFF"
        and audio_bytes[8:12] == b"WAVE"
    )


def _audio_capture_diagnostics(
    audio_bytes: bytes, audio_mime_type: str
) -> dict[str, Any]:
    """Return non-content metadata that helps diagnose empty native recordings."""

    diagnostics: dict[str, Any] = {
        "byte_count": len(audio_bytes),
        "mime_type": audio_mime_type,
        "looks_like_wav": _looks_like_wav(audio_bytes),
    }
    if not diagnostics["looks_like_wav"]:
        return diagnostics
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
            frame_count = wav_file.getnframes()
            frame_rate = wav_file.getframerate()
            diagnostics.update(
                {
                    "wav_frame_count": frame_count,
                    "wav_frame_rate": frame_rate,
                    "wav_channel_count": wav_file.getnchannels(),
                    "wav_sample_width_bytes": wav_file.getsampwidth(),
                    "wav_duration_ms": (
                        round(frame_count * 1000 / frame_rate)
                        if frame_rate > 0
                        else None
                    ),
                }
            )
    except (wave.Error, EOFError):
        diagnostics["wav_parse_error"] = True
    return diagnostics


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _paged_rows(build_query: Any, page_size: int = SUPABASE_PAGE_SIZE) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while True:
        query = build_query()
        if not hasattr(query, "range"):
            return _rows(query.execute())
        response = query.range(start, start + page_size - 1).execute()
        batch = _rows(response)
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        start += page_size


def _first_row(response: Any) -> dict[str, Any] | None:
    rows = _rows(response)
    return rows[0] if rows else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _measure_stage(
    timings: dict[str, int] | None,
    stage: str,
    operation,
):
    """Measure one startup operation without changing its return value."""

    started = time.monotonic()
    try:
        return operation()
    finally:
        if timings is not None:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            timings[stage] = timings.get(stage, 0) + elapsed_ms


def _log_startup_timing(
    *,
    route: str,
    request_id: str,
    request_started: float,
    status: int,
    timings: dict[str, int],
    lesson_external_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "request_id": request_id,
        "route": route,
        "lesson_external_id": lesson_external_id,
        "status": status,
        **timings,
        "total_ms": round((time.monotonic() - request_started) * 1000),
    }
    print(
        "[speaking-coach-startup-timing] "
        + json.dumps(payload, separators=(",", ":")),
        flush=True,
    )
    return payload


def _begin_startup_timing(
    route: str, lesson_external_id: str | None = None
) -> dict[str, int]:
    timings: dict[str, int] = {}
    g.speaking_coach_startup_timing = {
        "route": route,
        "request_id": uuid4().hex[:8],
        "request_started": time.monotonic(),
        "timings": timings,
        "lesson_external_id": lesson_external_id,
    }
    return timings


@speaking_coach.after_request
def _emit_startup_timing(response):
    context = getattr(g, "speaking_coach_startup_timing", None)
    if context:
        payload = _log_startup_timing(
            route=context["route"],
            request_id=context["request_id"],
            request_started=context["request_started"],
            status=response.status_code,
            timings=context["timings"],
            lesson_external_id=context["lesson_external_id"],
        )
        response.headers["X-Speaking-Coach-Timing"] = json.dumps(
            payload, separators=(",", ":")
        )
    return response


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


def _is_admin_user(user_id: str) -> bool:
    """Fail closed when deciding whether evaluator diagnostics may be returned."""

    try:
        response = (
            supabase_admin.table("users")
            .select("is_admin")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        user = _first_row(response)
        return bool(user and user.get("is_admin") is True)
    except Exception:
        return False


def _reserve_speaking_coach_usage(user_id: str) -> dict[str, Any]:
    """Atomically reserve one billable evaluation before contacting providers."""

    response = supabase_admin.rpc(
        "reserve_speaking_coach_usage",
        {
            "p_user_id": user_id,
            "p_is_admin": _is_admin_user(user_id),
            "p_per_minute_limit": Config.SPEAKING_COACH_PER_MINUTE_LIMIT,
            "p_per_user_daily_limit": (
                Config.SPEAKING_COACH_PER_USER_DAILY_LIMIT
            ),
            "p_global_daily_limit": Config.SPEAKING_COACH_GLOBAL_DAILY_LIMIT,
        },
    ).execute()
    result = response.data
    if isinstance(result, list):
        result = result[0] if result else None
    if not isinstance(result, dict) or not isinstance(result.get("allowed"), bool):
        raise RuntimeError("Speaking-coach quota RPC returned an invalid response")
    return result


def _speaking_coach_limit_response(reservation: dict[str, Any]):
    reason = reservation.get("reason")
    messages = {
        "per_minute_limit": (
            "You’re submitting recordings too quickly. Please try again in a minute."
        ),
        "per_user_daily_limit": (
            "You’ve reached today’s speaking-practice limit. Please try again tomorrow."
        ),
        "global_daily_limit": (
            "Speaking practice has reached today’s usage limit. Please try again tomorrow."
        ),
    }
    response = jsonify(
        {
            "error": messages.get(
                reason,
                "Speaking practice is temporarily unavailable. Please try again later.",
            ),
            "code": reason or "speaking_coach_limit_reached",
            "retry_after_seconds": reservation.get("retry_after_seconds"),
        }
    )
    response.status_code = 429
    retry_after = reservation.get("retry_after_seconds")
    if isinstance(retry_after, int) and retry_after > 0:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _prompt_audio_url(object_key: Any) -> str | None:
    if not isinstance(object_key, str) or not object_key.strip():
        return None
    base_url = (Config.SUPABASE_URL or "").rstrip("/")
    if not base_url:
        return None
    encoded_key = quote(object_key.strip(), safe="/")
    return (
        f"{base_url}/storage/v1/object/public/"
        f"{PROMPT_AUDIO_BUCKET}/{encoded_key}"
    )


def _fetch_lesson(lesson_external_id: str) -> dict[str, Any] | None:
    response = (
        supabase_admin.table("lessons")
        .select(LESSON_SELECT)
        .eq("lesson_external_id", lesson_external_id)
        .limit(2)
        .execute()
    )
    lessons = _rows(response)
    if len(lessons) > 1:
        raise RuntimeError("Multiple lessons share the same lesson_external_id")
    return lessons[0] if lessons else None


def _lesson_external_id_sort_key(value: Any) -> tuple[int, int, str]:
    text = str(value or "").strip()
    level_text, separator, lesson_text = text.partition(".")
    if not separator or not level_text.isdigit():
        return (10**9, 10**9, text.casefold())
    level = int(level_text)
    if lesson_text.isdigit():
        return (level, int(lesson_text), "")
    if lesson_text.casefold() == "chp":
        return (level, 10**8, "")
    return (level, 10**9, lesson_text.casefold())


def _available_speaking_lessons(
    timings: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    practices = _measure_stage(
        timings,
        "practice_sets_query_ms",
        lambda: _paged_rows(
            lambda: supabase_admin.table("speaking_coach_practice_sets")
            .select("id,lesson_id")
            .eq("is_active", True)
        ),
    )
    if not practices:
        return []

    practice_ids = [row["id"] for row in practices]
    questions = _measure_stage(
        timings,
        "questions_query_ms",
        lambda: _paged_rows(
            lambda: supabase_admin.table("speaking_coach_questions")
            .select("id,practice_set_id")
            .in_("practice_set_id", practice_ids)
            .eq("is_active", True)
        ),
    )
    question_counts: dict[Any, int] = defaultdict(int)
    for question in questions:
        question_counts[question.get("practice_set_id")] += 1

    lesson_counts: dict[Any, dict[str, int]] = defaultdict(
        lambda: {"practice_set_count": 0, "question_count": 0}
    )
    for practice in practices:
        question_count = question_counts.get(practice.get("id"), 0)
        if question_count <= 0:
            continue
        counts = lesson_counts[practice.get("lesson_id")]
        counts["practice_set_count"] += 1
        counts["question_count"] += question_count
    lesson_ids = [lesson_id for lesson_id in lesson_counts if lesson_id is not None]
    if not lesson_ids:
        return []

    lessons = _measure_stage(
        timings,
        "lessons_query_ms",
        lambda: _paged_rows(
            lambda: supabase_admin.table("lessons")
            .select(LESSON_SELECT)
            .in_("id", lesson_ids)
        ),
    )
    result = []
    for lesson in lessons:
        counts = lesson_counts.get(lesson.get("id"))
        if not counts:
            continue
        result.append(
            {
                "id": lesson.get("id"),
                "lesson_external_id": lesson.get("lesson_external_id"),
                "title": lesson.get("title"),
                "title_th": lesson.get("title_th"),
                **counts,
            }
        )
    return sorted(
        result,
        key=lambda lesson: _lesson_external_id_sort_key(
            lesson.get("lesson_external_id")
        ),
    )


def _fetch_lesson_payload(
    lesson: dict[str, Any],
    *,
    include_test_answers: bool = False,
    first_set_only: bool = False,
    timings: dict[str, int] | None = None,
) -> dict[str, Any]:
    practice_response = _measure_stage(
        timings,
        "practice_sets_query_ms",
        lambda: supabase_admin.table("speaking_coach_practice_sets")
        .select(PRACTICE_SET_SELECT)
        .eq("lesson_id", lesson["id"])
        .eq("is_active", True)
        .order("sort_order")
        .execute(),
    )
    practice_sets = sorted(
        _rows(practice_response),
        key=lambda row: (row.get("sort_order") or 0, row.get("id") or 0),
    )
    if first_set_only:
        practice_sets = practice_sets[:1]
    practice_ids = [row["id"] for row in practice_sets]

    questions: list[dict[str, Any]] = []
    if practice_ids:
        question_select = QUESTION_SELECT
        if include_test_answers:
            question_select += ",target_answers"
        question_response = _measure_stage(
            timings,
            "questions_query_ms",
            lambda: supabase_admin.table("speaking_coach_questions")
            .select(question_select)
            .in_("practice_set_id", practice_ids)
            .eq("is_active", True)
            .execute(),
        )
        questions = _rows(question_response)

    questions_by_practice: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        questions_by_practice[question.get("practice_set_id")].append(question)
    for grouped_questions in questions_by_practice.values():
        grouped_questions.sort(
            key=lambda row: (row.get("sort_order") or 0, row.get("id") or 0)
        )

    lesson_position = 0
    practice_payloads = []
    for practice in practice_sets:
        question_payloads = []
        grouped_questions = questions_by_practice.get(practice["id"], [])
        for set_position, question in enumerate(grouped_questions, start=1):
            lesson_position += 1
            question_payload = {
                "id": question.get("id"),
                "position": set_position,
                "lesson_position": lesson_position,
                "prompt_en": question.get("prompt_en"),
                "prompt_th": question.get("prompt_th"),
                "examples": question.get("examples") or [],
                "prompt_audio_url": _prompt_audio_url(
                    question.get("prompt_audio_key")
                ),
            }
            if include_test_answers:
                target_answers = question.get("target_answers") or []
                question_payload["test_answer_en"] = next(
                    (
                        answer.strip()
                        for answer in target_answers
                        if isinstance(answer, str) and answer.strip()
                    ),
                    None,
                )
            question_payloads.append(question_payload)
        practice_payloads.append(
            {
                "id": practice.get("id"),
                "practice_type": practice.get("practice_type"),
                "position": len(practice_payloads) + 1,
                "tip_en": practice.get("tip_en"),
                "tip_th": practice.get("tip_th"),
                "question_count": len(question_payloads),
                "questions": question_payloads,
            }
        )

    return {
        "lesson": {
            "id": lesson.get("id"),
            "lesson_external_id": lesson.get("lesson_external_id"),
            "title": lesson.get("title"),
            "title_th": lesson.get("title_th"),
            "practice_set_count": len(practice_payloads),
            "question_count": lesson_position,
            "practice_sets": practice_payloads,
        }
    }


def _active_curriculum(
    lesson_id: str,
    timings: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    practice_response = _measure_stage(
        timings,
        "practice_sets_query_ms",
        lambda: supabase_admin.table("speaking_coach_practice_sets")
        .select("id,sort_order,content_hash")
        .eq("lesson_id", lesson_id)
        .eq("is_active", True)
        .order("sort_order")
        .execute(),
    )
    practices = sorted(
        _rows(practice_response),
        key=lambda row: (row.get("sort_order") or 0, row.get("id") or 0),
    )
    practice_ids = [row["id"] for row in practices]
    if not practice_ids:
        return practices, []
    question_response = _measure_stage(
        timings,
        "questions_query_ms",
        lambda: supabase_admin.table("speaking_coach_questions")
        .select("id,practice_set_id,sort_order,content_hash")
        .in_("practice_set_id", practice_ids)
        .eq("is_active", True)
        .execute(),
    )
    practice_positions = {
        practice["id"]: index for index, practice in enumerate(practices)
    }
    questions = sorted(
        _rows(question_response),
        key=lambda row: (
            practice_positions.get(row.get("practice_set_id"), 10**9),
            row.get("sort_order") or 0,
            row.get("id") or 0,
        ),
    )
    return practices, questions


def _curriculum_hash(
    practices: list[dict[str, Any]], questions: list[dict[str, Any]]
) -> str:
    serialized = json.dumps(
        {
            "practice_sets": [
                [row.get("id"), row.get("content_hash")] for row in practices
            ],
            "questions": [
                [row.get("id"), row.get("content_hash")] for row in questions
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _completed_question_results(session_id: str) -> dict[int, str]:
    response = (
        supabase_admin.table("user_speaking_coach_attempts")
        .select("question_id,evaluation_result")
        .eq("session_id", session_id)
        .eq("completes_question", True)
        .execute()
    )
    return {
        int(row["question_id"]): str(row.get("evaluation_result") or "")
        for row in _rows(response)
        if row.get("question_id") is not None
    }


def _completed_question_ids(session_id: str) -> set[int]:
    return set(_completed_question_results(session_id))


def _skipped_question_ids(session_id: str) -> set[int]:
    response = (
        supabase_admin.table("user_speaking_coach_skips")
        .select("question_id")
        .eq("session_id", session_id)
        .execute()
    )
    return {
        int(row["question_id"])
        for row in _rows(response)
        if row.get("question_id") is not None
    }


def _session_payload(
    session: dict[str, Any],
    ordered_question_ids: list[int],
    timings: dict[str, int] | None = None,
) -> dict[str, Any]:
    completed_results = _measure_stage(
        timings,
        "completed_attempts_query_ms",
        lambda: _completed_question_results(str(session["id"])),
    )
    completed = set(completed_results)
    skipped = _measure_stage(
        timings,
        "skips_query_ms",
        lambda: _skipped_question_ids(str(session["id"])),
    )
    resolved = completed | skipped
    correct = {
        question_id
        for question_id, result in completed_results.items()
        if result == EvaluationStatus.PASS.value
    }
    needs_review = (completed - correct) | skipped
    current_question_id = next(
        (question_id for question_id in ordered_question_ids if question_id not in resolved),
        None,
    )
    instructional_attempt_number = 1
    previous_attempt_id = None
    consecutive_unclear_audio_count = 0
    if current_question_id is not None:
        attempts = _measure_stage(
            timings,
            "current_question_attempts_query_ms",
            lambda: _attempts_for_question(
                str(session["id"]), current_question_id
            ),
        )
        consecutive_unclear_audio_count = _consecutive_unclear_audio_count(attempts)
        instructional_attempt_number, retry_attempt = _expected_instructional_attempt(
            attempts
        )
        if retry_attempt:
            previous_attempt_id = str(retry_attempt["id"])
    return {
        "id": session.get("id"),
        "lesson_id": session.get("lesson_id"),
        "status": session.get("status"),
        "current_question_id": current_question_id,
        "completed_question_ids": sorted(completed),
        "skipped_question_ids": sorted(skipped),
        "correct_question_ids": sorted(correct),
        "needs_review_question_ids": sorted(needs_review),
        "instructional_attempt_number": instructional_attempt_number,
        "previous_attempt_id": previous_attempt_id,
        "consecutive_unclear_audio_count": consecutive_unclear_audio_count,
        "unclear_audio_retry_limit": UNCLEAR_AUDIO_RETRY_LIMIT,
    }


def _fetch_session(session_id: str, user_id: str) -> dict[str, Any] | None:
    response = (
        supabase_admin.table("user_speaking_coach_sessions")
        .select("id,user_id,lesson_id,content_hash,status,current_question_id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return _first_row(response)


def _fetch_evaluator_question(question_id: int) -> tuple[dict[str, Any], dict[str, Any]]:
    question_response = (
        supabase_admin.table("speaking_coach_questions")
        .select(
            "id,practice_set_id,prompt_en,prompt_th,target_answers,examples,"
            "focus,focus_items,is_active"
        )
        .eq("id", question_id)
        .limit(1)
        .execute()
    )
    question = _first_row(question_response)
    if not question:
        raise LookupError("Speaking question not found")
    practice_response = (
        supabase_admin.table("speaking_coach_practice_sets")
        .select("id,lesson_id,practice_type,focus,is_active")
        .eq("id", question["practice_set_id"])
        .limit(1)
        .execute()
    )
    practice = _first_row(practice_response)
    if not practice:
        raise LookupError("Speaking practice set not found")
    return question, practice


def _attempts_for_question(session_id: str, question_id: int) -> list[dict[str, Any]]:
    response = (
        supabase_admin.table("user_speaking_coach_attempts")
        .select(
            "id,evaluation_sequence,instructional_attempt_number,processing_status,"
            "evaluation_result,normalized_evaluation,provider_response_raw,"
            "completes_question"
        )
        .eq("session_id", session_id)
        .eq("question_id", question_id)
        .order("evaluation_sequence")
        .execute()
    )
    return sorted(
        _rows(response), key=lambda row: row.get("evaluation_sequence") or 0
    )


def _consecutive_unclear_audio_count(attempts: list[dict[str, Any]]) -> int:
    """Count completed unclear results since the most recent usable evaluation."""

    count = 0
    for attempt in reversed(attempts):
        if attempt.get("processing_status") != "completed":
            continue
        if attempt.get("evaluation_result") == EvaluationStatus.UNCLEAR_AUDIO.value:
            count += 1
            continue
        break
    return count


def _attempt_for_submission(
    session_id: str, client_submission_id: str
) -> dict[str, Any] | None:
    response = (
        supabase_admin.table("user_speaking_coach_attempts")
        .select(
            "id,question_id,evaluation_sequence,instructional_attempt_number,processing_status,"
            "evaluation_result,normalized_evaluation,failure_code"
        )
        .eq("session_id", session_id)
        .eq("client_submission_id", client_submission_id)
        .limit(1)
        .execute()
    )
    return _first_row(response)


def _existing_submission_response(
    attempt: dict[str, Any],
    session: dict[str, Any],
    ordered_question_ids: list[int],
):
    processing_status = attempt.get("processing_status")
    normalized = attempt.get("normalized_evaluation")
    if processing_status == "completed" and isinstance(normalized, dict):
        return jsonify(
            {
                "attempt": {
                    "id": attempt.get("id"),
                    "instructional_attempt_number": attempt.get(
                        "instructional_attempt_number"
                    ),
                    "evaluation_sequence": attempt.get("evaluation_sequence"),
                    "evaluation": normalized,
                    "replayed": True,
                },
                "session": _session_payload(session, ordered_question_ids),
            }
        ), 200
    if processing_status in {"uploaded", "evaluating"}:
        return jsonify(
            {
                "error": "This recording is still being evaluated.",
                "code": "submission_in_progress",
                "attempt_id": attempt.get("id"),
            }
        ), 409
    if processing_status == "failed":
        return jsonify(
            {
                "error": "This recording could not be evaluated. Record again to create a new submission.",
                "code": "submission_failed",
                "attempt_id": attempt.get("id"),
                "failure_code": attempt.get("failure_code"),
            }
        ), 409
    return jsonify(
        {
            "error": "The stored submission result is unavailable.",
            "code": "submission_result_unavailable",
            "attempt_id": attempt.get("id"),
        }
    ), 409


def _is_attempt_uniqueness_error(error: Exception) -> bool:
    code = getattr(error, "code", None)
    message = str(error)
    return code == "23505" or any(
        marker in message
        for marker in (
            "23505",
            "user_speaking_coach_attempts_submission_unique",
            "user_speaking_coach_attempts_one_processing",
        )
    )


def _expected_instructional_attempt(
    attempts: list[dict[str, Any]],
) -> tuple[int, dict[str, Any] | None]:
    expected = 1
    retry_attempt = None
    for attempt in attempts:
        if attempt.get("completes_question"):
            raise ValueError("This speaking question is already complete.")
        result = attempt.get("evaluation_result")
        if (
            attempt.get("processing_status") == "completed"
            and result == EvaluationStatus.RETRY.value
        ):
            expected = 2
            retry_attempt = attempt
    return expected, retry_attempt


def _update_attempt(attempt_id: str, values: dict[str, Any]) -> None:
    supabase_admin.table("user_speaking_coach_attempts").update(values).eq(
        "id", attempt_id
    ).execute()


def _advance_session(
    session: dict[str, Any], ordered_question_ids: list[int]
) -> dict[str, Any]:
    completed = _completed_question_ids(str(session["id"]))
    skipped = _skipped_question_ids(str(session["id"]))
    resolved = completed | skipped
    next_question_id = next(
        (question_id for question_id in ordered_question_ids if question_id not in resolved),
        None,
    )
    values: dict[str, Any] = {
        "current_question_id": next_question_id,
        "updated_at": _iso(_now()),
    }
    if next_question_id is None:
        values.update({"status": "completed", "ended_at": _iso(_now())})
    response = (
        supabase_admin.table("user_speaking_coach_sessions")
        .update(values)
        .eq("id", session["id"])
        .execute()
    )
    updated = _first_row(response) or {**session, **values}
    if next_question_id is None:
        try:
            delete_session_audio(str(session["id"]), client=supabase_admin)
        except Exception:
            current_app.logger.exception(
                "Speaking audio cleanup failed for completed session %s",
                session["id"],
            )
    return _session_payload(updated, ordered_question_ids)


@speaking_coach.route("/api/internal/speaking/cleanup", methods=["POST"])
def cleanup_speaking_retention():
    expected_secret = Config.SPEAKING_COACH_CLEANUP_SECRET or ""
    auth_header = request.headers.get("Authorization") or ""
    scheme, separator, supplied_secret = auth_header.partition(" ")
    if not expected_secret:
        return jsonify({"error": "Speaking cleanup is not configured"}), 503
    if (
        not separator
        or scheme.lower() != "bearer"
        or not hmac.compare_digest(supplied_secret, expected_secret)
    ):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        result = run_retention_cleanup()
        current_app.logger.info("Speaking retention cleanup completed: %s", result)
        return jsonify(result), 200
    except Exception:
        current_app.logger.exception("Speaking retention cleanup failed")
        return jsonify({"error": "Speaking cleanup failed"}), 500


@speaking_coach.route(
    "/api/speaking/lessons/<string:lesson_external_id>", methods=["GET"]
)
def get_speaking_lesson(lesson_external_id: str):
    normalized_id = lesson_external_id.strip()
    timings = _begin_startup_timing("lesson", normalized_id or None)
    user_id, auth_error = _measure_stage(
        timings, "auth_ms", _authenticated_user_id
    )
    if auth_error:
        return auth_error

    if not normalized_id:
        return jsonify({"error": "Lesson ID is required"}), 400

    try:
        lesson = _measure_stage(
            timings,
            "lesson_query_ms",
            lambda: _fetch_lesson(normalized_id),
        )
        if not lesson:
            return jsonify({"error": "Speaking lesson not found"}), 404
        wants_test_answers = request.args.get("include_test_answers") == "1"
        first_set_only = request.args.get("first_set_only") == "1"
        include_test_answers = wants_test_answers and _measure_stage(
            timings,
            "admin_query_ms",
            lambda: _is_admin_user(user_id),
        )
        payload = _measure_stage(
            timings,
            "payload_total_ms",
            lambda: _fetch_lesson_payload(
                lesson,
                include_test_answers=include_test_answers,
                first_set_only=first_set_only,
                timings=timings,
            ),
        )
        if not payload["lesson"]["practice_sets"]:
            return jsonify({"error": "Speaking lesson not found"}), 404
        return jsonify(payload), 200
    except Exception as exc:
        print(
            f"Error fetching speaking lesson {normalized_id}: {exc}", flush=True
        )
        return jsonify({"error": "Failed to fetch speaking lesson"}), 500


@speaking_coach.route("/api/speaking/lessons", methods=["GET"])
def list_speaking_lessons():
    timings = _begin_startup_timing("lesson_catalog")
    user_id, auth_error = _measure_stage(
        timings, "auth_ms", _authenticated_user_id
    )
    if auth_error:
        return auth_error
    try:
        lessons = _measure_stage(
            timings,
            "catalog_total_ms",
            lambda: _available_speaking_lessons(timings),
        )
        completed_sessions = _measure_stage(
            timings,
            "completed_sessions_query_ms",
            lambda: _paged_rows(
                lambda: supabase_admin.table("user_speaking_coach_sessions")
                .select("lesson_id")
                .eq("user_id", user_id)
                .eq("status", "completed")
            ),
        )
        completed_lesson_ids = {row.get("lesson_id") for row in completed_sessions}
        for lesson in lessons:
            lesson["is_completed"] = lesson["id"] in completed_lesson_ids
        return jsonify({"lessons": lessons}), 200
    except Exception:
        current_app.logger.exception("Failed to list speaking lessons")
        return jsonify({"error": "Failed to list speaking lessons"}), 500


@speaking_coach.route("/api/speaking/sessions", methods=["POST"])
def create_or_resume_speaking_session():
    timings = _begin_startup_timing("session")
    user_id, auth_error = _measure_stage(
        timings, "auth_ms", _authenticated_user_id
    )
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    lesson_external_id = str(payload.get("lesson_external_id") or "").strip()
    g.speaking_coach_startup_timing["lesson_external_id"] = (
        lesson_external_id or None
    )
    force_new = payload.get("force_new") is True
    timings["force_new"] = int(force_new)
    if not lesson_external_id:
        return jsonify({"error": "lesson_external_id is required"}), 400

    try:
        lesson = _measure_stage(
            timings,
            "lesson_query_ms",
            lambda: _fetch_lesson(lesson_external_id),
        )
        if not lesson:
            return jsonify({"error": "Speaking lesson not found"}), 404
        practices, questions = _measure_stage(
            timings,
            "curriculum_total_ms",
            lambda: _active_curriculum(str(lesson["id"]), timings),
        )
        if not practices or not questions:
            return jsonify({"error": "Speaking lesson not found"}), 404

        curriculum_state = _measure_stage(
            timings,
            "curriculum_build_ms",
            lambda: (
                _curriculum_hash(practices, questions),
                [int(question["id"]) for question in questions],
            ),
        )
        content_hash, ordered_question_ids = curriculum_state
        active_response = _measure_stage(
            timings,
            "active_session_query_ms",
            lambda: supabase_admin.table("user_speaking_coach_sessions")
            .select("id,user_id,lesson_id,content_hash,status,current_question_id")
            .eq("user_id", user_id)
            .eq("lesson_id", lesson["id"])
            .eq("status", "active")
            .limit(2)
            .execute(),
        )
        active_sessions = _rows(active_response)
        if len(active_sessions) > 1:
            raise RuntimeError("Multiple active speaking sessions found")
        active_session = active_sessions[0] if active_sessions else None
        if (
            active_session
            and not force_new
            and active_session.get("content_hash") == content_hash
        ):
            session_payload = _measure_stage(
                timings,
                "session_payload_total_ms",
                lambda: _session_payload(
                    active_session, ordered_question_ids, timings
                ),
            )
            return jsonify({"session": session_payload}), 200

        if active_session:
            _measure_stage(
                timings,
                "abandon_session_query_ms",
                lambda: supabase_admin.table("user_speaking_coach_sessions")
                .update(
                    {
                        "status": "abandoned",
                        "ended_at": _iso(_now()),
                        "updated_at": _iso(_now()),
                    }
                )
                .eq("id", active_session["id"])
                .execute(),
            )

        session_values = {
            "id": str(uuid4()),
            "user_id": user_id,
            "lesson_id": lesson["id"],
            "content_hash": content_hash,
            "status": "active",
            "current_question_id": ordered_question_ids[0],
        }
        inserted = _measure_stage(
            timings,
            "insert_session_query_ms",
            lambda: supabase_admin.table("user_speaking_coach_sessions")
            .insert(session_values)
            .execute(),
        )
        session = _first_row(inserted) or session_values
        session_payload = _measure_stage(
            timings,
            "session_payload_total_ms",
            lambda: _session_payload(session, ordered_question_ids, timings),
        )
        return jsonify({"session": session_payload}), 201
    except Exception as exc:
        print(f"Error creating speaking session: {exc}", flush=True)
        return jsonify({"error": "Failed to create speaking session"}), 500


@speaking_coach.route("/api/speaking/evaluate", methods=["POST"])
def evaluate_speaking_recording():
    request_started = time.monotonic()
    auth_started = time.monotonic()
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error
    auth_ms = round((time.monotonic() - auth_started) * 1000)

    session_id = str(request.form.get("session_id") or "").strip()
    raw_submission_id = str(
        request.form.get("client_submission_id") or ""
    ).strip()
    try:
        question_id = int(request.form.get("question_id") or "")
    except ValueError:
        return jsonify({"error": "Invalid question"}), 400
    if not session_id:
        return jsonify({"error": "Invalid evaluation request"}), 400
    try:
        client_submission_id = str(UUID(raw_submission_id))
    except (ValueError, AttributeError):
        return jsonify({"error": "Invalid client_submission_id"}), 400

    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "Audio recording is required"}), 400
    supplied_mime_type = (audio.mimetype or "").lower().split(";", 1)[0]
    audio_bytes = audio.read(MAX_AUDIO_BYTES + 1)
    if not audio_bytes:
        return jsonify({"error": "Audio recording is empty"}), 400
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify({"error": "Audio recording exceeds 10 MB"}), 413
    provider_mime_type = ALLOWED_AUDIO_MIME_TYPES.get(supplied_mime_type)
    if not provider_mime_type and _looks_like_wav(audio_bytes):
        supplied_mime_type = "audio/wav"
        provider_mime_type = "audio/wav"
    if not provider_mime_type:
        return jsonify({"error": "Unsupported audio format"}), 415
    capture_diagnostics = _audio_capture_diagnostics(
        audio_bytes, provider_mime_type
    )
    print(
        "[speaking-capture-received] "
        + json.dumps(
            {
                "client_submission_id": client_submission_id,
                "question_id": question_id,
                **capture_diagnostics,
            },
            separators=(",", ":"),
        ),
        flush=True,
    )

    attempt_id: str | None = None
    try:
        setup_started = time.monotonic()
        session = _fetch_session(session_id, user_id)
        if not session:
            return jsonify({"error": "Speaking session not found"}), 404

        practices, questions = _active_curriculum(str(session["lesson_id"]))
        ordered_question_ids = [int(question["id"]) for question in questions]
        existing_submission = _attempt_for_submission(
            session_id, client_submission_id
        )
        if existing_submission:
            if int(existing_submission.get("question_id") or 0) != question_id:
                return jsonify(
                    {
                        "error": "This submission ID belongs to a different question.",
                        "code": "submission_id_conflict",
                    }
                ), 409
            return _existing_submission_response(
                existing_submission, session, ordered_question_ids
            )
        if session.get("status") != "active":
            return jsonify({"error": "Speaking session is not active"}), 409
        if _curriculum_hash(practices, questions) != session.get("content_hash"):
            supabase_admin.table("user_speaking_coach_sessions").update(
                {
                    "status": "abandoned",
                    "ended_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            ).eq("id", session_id).execute()
            return jsonify(
                {
                    "error": "Speaking lesson changed; start a new session",
                    "code": "session_content_changed",
                }
            ), 409
        if question_id not in ordered_question_ids:
            return jsonify({"error": "Question is not part of this session"}), 400
        if question_id in _skipped_question_ids(session_id):
            return jsonify({"error": "This speaking question was skipped."}), 409

        question, practice = _fetch_evaluator_question(question_id)
        if (
            not question.get("is_active")
            or not practice.get("is_active")
            or str(practice.get("lesson_id")) != str(session["lesson_id"])
        ):
            return jsonify({"error": "Speaking question is not active"}), 409

        attempts = _attempts_for_question(session_id, question_id)
        if _consecutive_unclear_audio_count(attempts) >= UNCLEAR_AUDIO_RETRY_LIMIT:
            return jsonify(
                {
                    "error": "We’re unable to check another recording for this question. Skip it or exit practice.",
                    "code": "unclear_audio_limit_reached",
                    "session": _session_payload(session, ordered_question_ids),
                }
            ), 429
        try:
            expected_attempt, retry_attempt = _expected_instructional_attempt(attempts)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        instructional_attempt_number = expected_attempt
        previous_attempt_id = str(retry_attempt["id"]) if retry_attempt else None

        try:
            usage_reservation = _reserve_speaking_coach_usage(user_id)
        except Exception:
            current_app.logger.exception(
                "Speaking-coach usage limiter unavailable for user %s", user_id
            )
            return jsonify(
                {
                    "error": "Speaking practice is temporarily unavailable. Please try again later.",
                    "code": "speaking_coach_limiter_unavailable",
                }
            ), 503
        if not usage_reservation["allowed"]:
            return _speaking_coach_limit_response(usage_reservation)

        attempt_id = str(uuid4())
        evaluation_sequence = max(
            [int(item.get("evaluation_sequence") or 0) for item in attempts],
            default=0,
        ) + 1
        audio_extension = AUDIO_FILE_EXTENSIONS[provider_mime_type]
        audio_object_path = (
            f"{user_id}/{session_id}/{attempt_id}{audio_extension}"
        )
        attempt_values = {
            "id": attempt_id,
            "user_id": user_id,
            "session_id": session_id,
            "question_id": question_id,
            "client_submission_id": client_submission_id,
            "evaluation_sequence": evaluation_sequence,
            "instructional_attempt_number": instructional_attempt_number,
            "previous_attempt_id": previous_attempt_id,
            "processing_status": "uploaded",
            "detected_issues": [],
            "displayed_issues": [],
            "retry_focus": [],
            "evaluation_context": {
                "capture_diagnostics": capture_diagnostics,
            },
            "audio_object_path": audio_object_path,
            "audio_expires_at": _iso(
                _now() + timedelta(hours=Config.SPEAKING_COACH_AUDIO_RETENTION_HOURS)
            ),
        }
        try:
            supabase_admin.table("user_speaking_coach_attempts").insert(
                attempt_values
            ).execute()
        except Exception as exc:
            if not _is_attempt_uniqueness_error(exc):
                raise
            existing_submission = _attempt_for_submission(
                session_id, client_submission_id
            )
            if existing_submission:
                return _existing_submission_response(
                    existing_submission, session, ordered_question_ids
                )
            return jsonify(
                {
                    "error": "Another recording for this question is already being evaluated.",
                    "code": "question_evaluation_in_progress",
                }
            ), 409
        setup_ms = round((time.monotonic() - setup_started) * 1000)

        storage_started = time.monotonic()
        try:
            supabase_admin.storage.from_(LEARNER_AUDIO_BUCKET).upload(
                audio_object_path,
                audio_bytes,
                {"content-type": provider_mime_type, "upsert": "false"},
            )
        except Exception as exc:
            _update_attempt(
                attempt_id,
                {
                    "processing_status": "failed",
                    "failure_code": "audio_upload_failed",
                    "failure_detail": str(exc)[:500],
                    "completed_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                },
            )
            return jsonify(
                {"error": "Could not store the audio recording", "code": "audio_upload_failed"}
            ), 503
        storage_ms = round((time.monotonic() - storage_started) * 1000)

        _update_attempt(
            attempt_id,
            {"processing_status": "evaluating", "updated_at": _iso(_now())},
        )
        previous_evaluation = None
        if retry_attempt:
            normalized_previous = retry_attempt.get("normalized_evaluation")
            previous_evaluation = (
                dict(normalized_previous)
                if isinstance(normalized_previous, dict)
                else {}
            )
            previous_provider = retry_attempt.get("provider_response_raw")
            if isinstance(previous_provider, dict):
                previous_evaluation["_provider_policy"] = (
                    previous_provider.get("policy")
                )
        evaluator_started = time.monotonic()
        result = evaluate_speaking_attempt(
            audio_bytes=audio_bytes,
            audio_mime_type=provider_mime_type,
            practice_type=practice["practice_type"],
            focus=question.get("focus") or practice.get("focus") or "",
            focus_items=question.get("focus_items") or [],
            prompt_en=question.get("prompt_en"),
            prompt_th=question.get("prompt_th"),
            target_answers=question.get("target_answers") or [],
            examples=question.get("examples") or [],
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
        )
        evaluator_ms = round((time.monotonic() - evaluator_started) * 1000)
        evaluation = result.evaluation
        normalized = evaluation.model_dump(mode="json")
        completed_at = _iso(_now())
        persistence_started = time.monotonic()
        _update_attempt(
            attempt_id,
            {
                "processing_status": "completed",
                "evaluation_result": evaluation.status.value,
                "transcript": evaluation.transcript,
                "content_result": evaluation.content.model_dump(mode="json"),
                "pronunciation_result": evaluation.pronunciation.model_dump(mode="json"),
                "feedback_en": evaluation.feedback_en,
                "feedback_th": evaluation.feedback_th,
                "detected_issues": [
                    issue.model_dump(mode="json") for issue in evaluation.detected_issues
                ],
                "displayed_issues": [
                    issue.model_dump(mode="json") for issue in evaluation.displayed_issues
                ],
                "corrected_answer": evaluation.corrected_answer,
                "retry_focus": evaluation.retry_focus,
                "provider": result.provider,
                "model_used": result.model,
                "prompt_version": PROMPT_VERSION,
                "evaluator_schema_version": EVALUATOR_SCHEMA_VERSION,
                "evaluation_context": {
                    **result.evaluation_context,
                    "capture_diagnostics": capture_diagnostics,
                },
                "provider_response_raw": result.provider_metadata,
                "provider_output_text": result.provider_output_text,
                "normalized_evaluation": normalized,
                "usage": result.usage,
                "latency_ms": result.latency_ms,
                "completed_at": completed_at,
                "updated_at": completed_at,
            },
        )

        completes_question = evaluation.status in (
            EvaluationStatus.PASS,
            EvaluationStatus.CONTINUE_WITH_CORRECTION,
        )
        if completes_question:
            session_payload = _advance_session(session, ordered_question_ids)
        else:
            session_payload = _session_payload(session, ordered_question_ids)
        persistence_ms = round((time.monotonic() - persistence_started) * 1000)
        total_ms = round((time.monotonic() - request_started) * 1000)
        evaluator_timings = result.provider_metadata.get("timings_ms", {})
        print(
            "[speaking-coach-timing] "
            + json.dumps(
                {
                    "question_id": question_id,
                    "practice_type": practice["practice_type"],
                    "auth_ms": auth_ms,
                    "setup_ms": setup_ms,
                    "audio_storage_ms": storage_ms,
                    "evaluator_ms": evaluator_ms,
                    "persistence_ms": persistence_ms,
                    "total_ms": total_ms,
                    "evaluator": evaluator_timings,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
        attempt_payload: dict[str, Any] = {
            "id": attempt_id,
            "instructional_attempt_number": instructional_attempt_number,
            "evaluation_sequence": evaluation_sequence,
            "evaluation": normalized,
        }
        if _is_admin_user(user_id):
            attempt_payload["debug"] = {
                "provider": result.provider,
                "model": result.model,
                "latency_ms": result.latency_ms,
                "usage": result.usage,
                "provider_response": result.provider_metadata,
                "request_timings_ms": {
                    "auth": auth_ms,
                    "setup": setup_ms,
                    "audio_storage": storage_ms,
                    "evaluator": evaluator_ms,
                    "persistence": persistence_ms,
                    "total": total_ms,
                },
            }
        return jsonify(
            {"attempt": attempt_payload, "session": session_payload}
        ), 200
    except EvaluatorError as exc:
        if attempt_id:
            _update_attempt(
                attempt_id,
                {
                    "processing_status": "failed",
                    "failure_code": exc.code,
                    "failure_detail": exc.detail[:500],
                    "completed_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                },
            )
        audio_error = exc.code.startswith("audio_")
        temporarily_unavailable = exc.code in {
            "audio_converter_unavailable",
            "azure_not_configured",
            "azure_timeout",
            "azure_unavailable",
            "gemini_not_configured",
            "gemini_timeout",
            "gemini_unavailable",
        } or exc.code in {
            "azure_http_429",
            "azure_http_500",
            "azure_http_502",
            "azure_http_503",
            "azure_http_504",
            "gemini_http_429",
            "gemini_http_500",
            "gemini_http_502",
            "gemini_http_503",
            "gemini_http_504",
        }
        status = 422 if audio_error else (503 if temporarily_unavailable else 502)
        public_error = (
            "Audio recording could not be processed"
            if audio_error and not temporarily_unavailable
            else "Speaking evaluation is temporarily unavailable"
        )
        return jsonify(
            {"error": public_error, "code": exc.code}
        ), status
    except Exception as exc:
        print(f"Error evaluating speaking recording: {exc}", flush=True)
        if attempt_id:
            try:
                _update_attempt(
                    attempt_id,
                    {
                        "processing_status": "failed",
                        "failure_code": "evaluation_failed",
                        "failure_detail": str(exc)[:500],
                        "completed_at": _iso(_now()),
                        "updated_at": _iso(_now()),
                    },
                )
            except Exception:
                pass
        return jsonify({"error": "Failed to evaluate speaking recording"}), 500


@speaking_coach.route(
    "/api/speaking/sessions/<string:session_id>/questions/<int:question_id>/skip",
    methods=["POST"],
)
def skip_speaking_question(session_id: str, question_id: int):
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error

    try:
        session = _fetch_session(session_id, user_id)
        if not session:
            return jsonify({"error": "Speaking session not found"}), 404

        practices, questions = _active_curriculum(str(session["lesson_id"]))
        ordered_question_ids = [int(question["id"]) for question in questions]
        if question_id in _skipped_question_ids(session_id):
            return jsonify({"session": _session_payload(session, ordered_question_ids)}), 200
        if session.get("status") != "active":
            return jsonify({"error": "Speaking session is not active"}), 409
        if _curriculum_hash(practices, questions) != session.get("content_hash"):
            supabase_admin.table("user_speaking_coach_sessions").update(
                {
                    "status": "abandoned",
                    "ended_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            ).eq("id", session_id).execute()
            return jsonify(
                {
                    "error": "Speaking lesson changed; start a new session",
                    "code": "session_content_changed",
                }
            ), 409
        if question_id not in ordered_question_ids:
            return jsonify({"error": "Question is not part of this session"}), 400
        if question_id in _completed_question_ids(session_id):
            return jsonify({"error": "This speaking question is already complete."}), 409

        supabase_admin.table("user_speaking_coach_skips").insert(
            {
                "id": str(uuid4()),
                "user_id": user_id,
                "session_id": session_id,
                "question_id": question_id,
                "skipped_at": _iso(_now()),
            }
        ).execute()

        return jsonify({"session": _advance_session(session, ordered_question_ids)}), 200
    except Exception:
        current_app.logger.exception(
            "Failed to skip speaking question %s in session %s",
            question_id,
            session_id,
        )
        return jsonify({"error": "Failed to skip speaking question"}), 500

"""Authenticated learner-facing API for speaking-coach curriculum and evaluation."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request

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
ALLOWED_AUDIO_MIME_TYPES = {
    "audio/aac": "audio/aac",
    "audio/m4a": "audio/m4a",
    "audio/mp4": "audio/mp4",
    "audio/x-m4a": "audio/x-m4a",
    "audio/mpeg": "audio/mpeg",
    "audio/mp3": "audio/mp3",
    "audio/wav": "audio/wav",
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


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _first_row(response: Any) -> dict[str, Any] | None:
    rows = _rows(response)
    return rows[0] if rows else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


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


def _fetch_lesson_payload(lesson: dict[str, Any]) -> dict[str, Any]:
    practice_response = (
        supabase_admin.table("speaking_coach_practice_sets")
        .select(PRACTICE_SET_SELECT)
        .eq("lesson_id", lesson["id"])
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    practice_sets = sorted(
        _rows(practice_response),
        key=lambda row: (row.get("sort_order") or 0, row.get("id") or 0),
    )
    practice_ids = [row["id"] for row in practice_sets]

    questions: list[dict[str, Any]] = []
    if practice_ids:
        question_response = (
            supabase_admin.table("speaking_coach_questions")
            .select(QUESTION_SELECT)
            .in_("practice_set_id", practice_ids)
            .eq("is_active", True)
            .execute()
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
            question_payloads.append(
                {
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
            )
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


def _active_curriculum(lesson_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    practice_response = (
        supabase_admin.table("speaking_coach_practice_sets")
        .select("id,sort_order,content_hash")
        .eq("lesson_id", lesson_id)
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    practices = sorted(
        _rows(practice_response),
        key=lambda row: (row.get("sort_order") or 0, row.get("id") or 0),
    )
    practice_ids = [row["id"] for row in practices]
    if not practice_ids:
        return practices, []
    question_response = (
        supabase_admin.table("speaking_coach_questions")
        .select("id,practice_set_id,sort_order,content_hash")
        .in_("practice_set_id", practice_ids)
        .eq("is_active", True)
        .execute()
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


def _completed_question_ids(session_id: str) -> set[int]:
    response = (
        supabase_admin.table("user_speaking_coach_attempts")
        .select("question_id")
        .eq("session_id", session_id)
        .eq("completes_question", True)
        .execute()
    )
    return {
        int(row["question_id"])
        for row in _rows(response)
        if row.get("question_id") is not None
    }


def _session_payload(
    session: dict[str, Any], ordered_question_ids: list[int]
) -> dict[str, Any]:
    completed = _completed_question_ids(str(session["id"]))
    current_question_id = next(
        (question_id for question_id in ordered_question_ids if question_id not in completed),
        None,
    )
    instructional_attempt_number = 1
    previous_attempt_id = None
    if current_question_id is not None:
        attempts = _attempts_for_question(str(session["id"]), current_question_id)
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
        "instructional_attempt_number": instructional_attempt_number,
        "previous_attempt_id": previous_attempt_id,
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
            "id,practice_set_id,prompt_en,prompt_th,target_answers,examples,is_active"
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
    next_question_id = next(
        (question_id for question_id in ordered_question_ids if question_id not in completed),
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
    _user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error

    normalized_id = lesson_external_id.strip()
    if not normalized_id:
        return jsonify({"error": "Lesson ID is required"}), 400

    try:
        lesson = _fetch_lesson(normalized_id)
        if not lesson:
            return jsonify({"error": "Speaking lesson not found"}), 404
        payload = _fetch_lesson_payload(lesson)
        if not payload["lesson"]["practice_sets"]:
            return jsonify({"error": "Speaking lesson not found"}), 404
        return jsonify(payload), 200
    except Exception as exc:
        print(
            f"Error fetching speaking lesson {normalized_id}: {exc}", flush=True
        )
        return jsonify({"error": "Failed to fetch speaking lesson"}), 500


@speaking_coach.route("/api/speaking/sessions", methods=["POST"])
def create_or_resume_speaking_session():
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error

    payload = request.get_json(silent=True) or {}
    lesson_external_id = str(payload.get("lesson_external_id") or "").strip()
    force_new = payload.get("force_new") is True
    if not lesson_external_id:
        return jsonify({"error": "lesson_external_id is required"}), 400

    try:
        lesson = _fetch_lesson(lesson_external_id)
        if not lesson:
            return jsonify({"error": "Speaking lesson not found"}), 404
        practices, questions = _active_curriculum(str(lesson["id"]))
        if not practices or not questions:
            return jsonify({"error": "Speaking lesson not found"}), 404

        content_hash = _curriculum_hash(practices, questions)
        ordered_question_ids = [int(question["id"]) for question in questions]
        active_response = (
            supabase_admin.table("user_speaking_coach_sessions")
            .select("id,user_id,lesson_id,content_hash,status,current_question_id")
            .eq("user_id", user_id)
            .eq("lesson_id", lesson["id"])
            .eq("status", "active")
            .limit(2)
            .execute()
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
            return jsonify(
                {"session": _session_payload(active_session, ordered_question_ids)}
            ), 200

        if active_session:
            supabase_admin.table("user_speaking_coach_sessions").update(
                {
                    "status": "abandoned",
                    "ended_at": _iso(_now()),
                    "updated_at": _iso(_now()),
                }
            ).eq("id", active_session["id"]).execute()

        session_values = {
            "id": str(uuid4()),
            "user_id": user_id,
            "lesson_id": lesson["id"],
            "content_hash": content_hash,
            "status": "active",
            "current_question_id": ordered_question_ids[0],
        }
        inserted = (
            supabase_admin.table("user_speaking_coach_sessions")
            .insert(session_values)
            .execute()
        )
        session = _first_row(inserted) or session_values
        return jsonify(
            {"session": _session_payload(session, ordered_question_ids)}
        ), 201
    except Exception as exc:
        print(f"Error creating speaking session: {exc}", flush=True)
        return jsonify({"error": "Failed to create speaking session"}), 500


@speaking_coach.route("/api/speaking/evaluate", methods=["POST"])
def evaluate_speaking_recording():
    user_id, auth_error = _authenticated_user_id()
    if auth_error:
        return auth_error

    session_id = str(request.form.get("session_id") or "").strip()
    try:
        question_id = int(request.form.get("question_id") or "")
    except ValueError:
        return jsonify({"error": "Invalid question"}), 400
    if not session_id:
        return jsonify({"error": "Invalid evaluation request"}), 400

    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "Audio recording is required"}), 400
    supplied_mime_type = (audio.mimetype or "").lower().split(";", 1)[0]
    provider_mime_type = ALLOWED_AUDIO_MIME_TYPES.get(supplied_mime_type)
    if not provider_mime_type:
        return jsonify({"error": "Unsupported audio format"}), 415
    audio_bytes = audio.read(MAX_AUDIO_BYTES + 1)
    if not audio_bytes:
        return jsonify({"error": "Audio recording is empty"}), 400
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        return jsonify({"error": "Audio recording exceeds 10 MB"}), 413

    attempt_id: str | None = None
    try:
        session = _fetch_session(session_id, user_id)
        if not session:
            return jsonify({"error": "Speaking session not found"}), 404
        if session.get("status") != "active":
            return jsonify({"error": "Speaking session is not active"}), 409

        practices, questions = _active_curriculum(str(session["lesson_id"]))
        ordered_question_ids = [int(question["id"]) for question in questions]
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

        question, practice = _fetch_evaluator_question(question_id)
        if (
            not question.get("is_active")
            or not practice.get("is_active")
            or str(practice.get("lesson_id")) != str(session["lesson_id"])
        ):
            return jsonify({"error": "Speaking question is not active"}), 409

        attempts = _attempts_for_question(session_id, question_id)
        try:
            expected_attempt, retry_attempt = _expected_instructional_attempt(attempts)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409
        instructional_attempt_number = expected_attempt
        previous_attempt_id = str(retry_attempt["id"]) if retry_attempt else None

        attempt_id = str(uuid4())
        evaluation_sequence = max(
            [int(item.get("evaluation_sequence") or 0) for item in attempts],
            default=0,
        ) + 1
        audio_extension = AUDIO_FILE_EXTENSIONS[supplied_mime_type]
        audio_object_path = (
            f"{user_id}/{session_id}/{attempt_id}{audio_extension}"
        )
        attempt_values = {
            "id": attempt_id,
            "user_id": user_id,
            "session_id": session_id,
            "question_id": question_id,
            "evaluation_sequence": evaluation_sequence,
            "instructional_attempt_number": instructional_attempt_number,
            "previous_attempt_id": previous_attempt_id,
            "processing_status": "uploaded",
            "detected_issues": [],
            "displayed_issues": [],
            "retry_focus": [],
            "audio_object_path": audio_object_path,
            "audio_expires_at": _iso(
                _now() + timedelta(hours=Config.SPEAKING_COACH_AUDIO_RETENTION_HOURS)
            ),
        }
        supabase_admin.table("user_speaking_coach_attempts").insert(
            attempt_values
        ).execute()

        try:
            supabase_admin.storage.from_(LEARNER_AUDIO_BUCKET).upload(
                audio_object_path,
                audio_bytes,
                {"content-type": supplied_mime_type, "upsert": "false"},
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
        result = evaluate_speaking_attempt(
            audio_bytes=audio_bytes,
            audio_mime_type=provider_mime_type,
            practice_type=practice["practice_type"],
            focus=practice.get("focus") or "",
            prompt_en=question.get("prompt_en"),
            prompt_th=question.get("prompt_th"),
            target_answers=question.get("target_answers") or [],
            examples=question.get("examples") or [],
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
        )
        evaluation = result.evaluation
        normalized = evaluation.model_dump(mode="json")
        completed_at = _iso(_now())
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
                "evaluation_context": result.evaluation_context,
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

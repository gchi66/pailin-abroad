"""Retention cleanup for learner speaking-coach data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Config
from app.supabase_client import supabase_admin


LEARNER_AUDIO_BUCKET = "speaking-coach-audio"
ATTEMPTS_TABLE = "user_speaking_coach_attempts"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _bounded_batch_size(value: int | None) -> int:
    configured = value or Config.SPEAKING_COACH_CLEANUP_BATCH_SIZE
    return max(1, min(int(configured), 500))


def _delete_audio_rows(
    rows: list[dict[str, Any]], *, deleted_at: str, client: Any
) -> int:
    """Delete a selected batch and mark it only after Storage accepts removal."""
    selected = [
        row
        for row in rows
        if row.get("id") and isinstance(row.get("audio_object_path"), str)
    ]
    if not selected:
        return 0

    deleted_count = 0
    for offset in range(0, len(selected), 100):
        chunk = selected[offset : offset + 100]
        paths = list(
            dict.fromkeys(row["audio_object_path"] for row in chunk)
        )
        client.storage.from_(LEARNER_AUDIO_BUCKET).remove(paths)
        attempt_ids = [row["id"] for row in chunk]
        (
            client.table(ATTEMPTS_TABLE)
            .update({"audio_deleted_at": deleted_at, "updated_at": deleted_at})
            .in_("id", attempt_ids)
            .is_("audio_deleted_at", "null")
            .execute()
        )
        deleted_count += len(chunk)
    return deleted_count


def delete_session_audio(
    session_id: str, *, now: datetime | None = None, client: Any = None
) -> int:
    """Immediately remove recordings once a speaking session is complete."""
    deleted_at = _iso(now or _now())
    database = client or supabase_admin
    response = (
        database.table(ATTEMPTS_TABLE)
        .select("id,audio_object_path")
        .eq("session_id", session_id)
        .is_("audio_deleted_at", "null")
        .not_.is_("audio_object_path", "null")
        .execute()
    )
    return _delete_audio_rows(_rows(response), deleted_at=deleted_at, client=database)


def delete_user_audio(
    user_id: str, *, now: datetime | None = None, client: Any = None
) -> int:
    """Remove all learner recordings before the user's database rows cascade away."""
    deleted_at = _iso(now or _now())
    database = client or supabase_admin
    response = (
        database.table(ATTEMPTS_TABLE)
        .select("id,audio_object_path")
        .eq("user_id", user_id)
        .is_("audio_deleted_at", "null")
        .not_.is_("audio_object_path", "null")
        .execute()
    )
    return _delete_audio_rows(_rows(response), deleted_at=deleted_at, client=database)


def delete_expired_audio(
    *, now: datetime | None = None, batch_size: int | None = None
) -> int:
    """Remove one bounded batch of expired recordings."""
    deleted_at = _iso(now or _now())
    response = (
        supabase_admin.table(ATTEMPTS_TABLE)
        .select("id,audio_object_path")
        .is_("audio_deleted_at", "null")
        .not_.is_("audio_object_path", "null")
        .lte("audio_expires_at", deleted_at)
        .limit(_bounded_batch_size(batch_size))
        .execute()
    )
    return _delete_audio_rows(
        _rows(response), deleted_at=deleted_at, client=supabase_admin
    )


def redact_expired_diagnostics(
    *, now: datetime | None = None, batch_size: int | None = None
) -> int:
    """Purge raw provider/debug material while retaining normalized results and usage."""
    current_time = now or _now()
    cutoff = _iso(
        current_time
        - timedelta(days=Config.SPEAKING_COACH_DIAGNOSTIC_RETENTION_DAYS)
    )
    limit = _bounded_batch_size(batch_size)
    redacted_at = _iso(current_time)
    redacted_ids: set[str] = set()

    completed_response = (
        supabase_admin.table(ATTEMPTS_TABLE)
        .select("id")
        .lte("created_at", cutoff)
        .not_.is_("provider_response_raw", "null")
        .limit(limit)
        .execute()
    )
    completed_ids = [row["id"] for row in _rows(completed_response) if row.get("id")]
    if completed_ids:
        (
            supabase_admin.table(ATTEMPTS_TABLE)
            .update(
                {
                    "evaluation_context": None,
                    "provider_response_raw": None,
                    "provider_output_text": None,
                    "updated_at": redacted_at,
                }
            )
            .in_("id", completed_ids)
            .execute()
        )
        redacted_ids.update(completed_ids)

    failed_response = (
        supabase_admin.table(ATTEMPTS_TABLE)
        .select("id")
        .lte("created_at", cutoff)
        .not_.is_("failure_detail", "null")
        .limit(limit)
        .execute()
    )
    failed_ids = [row["id"] for row in _rows(failed_response) if row.get("id")]
    if failed_ids:
        (
            supabase_admin.table(ATTEMPTS_TABLE)
            .update({"failure_detail": None, "updated_at": redacted_at})
            .in_("id", failed_ids)
            .execute()
        )
        redacted_ids.update(failed_ids)

    return len(redacted_ids)


def run_retention_cleanup(
    *, now: datetime | None = None, batch_size: int | None = None
) -> dict[str, int]:
    """Run a safe, bounded retention pass suitable for an hourly scheduler."""
    current_time = now or _now()
    return {
        "audio_deleted": delete_expired_audio(
            now=current_time, batch_size=batch_size
        ),
        "diagnostics_redacted": redact_expired_diagnostics(
            now=current_time, batch_size=batch_size
        ),
    }

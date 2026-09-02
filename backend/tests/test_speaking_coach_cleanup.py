from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app import speaking_coach_cleanup as cleanup


NOW = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.operation = "select"
        self.values = {}
        self.limit_count = None

    @property
    def not_(self):
        return FakeNotFilter(self)

    def select(self, _columns):
        return self

    def update(self, values):
        self.operation = "update"
        self.values = values
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, values))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, None if value == "null" else value))
        return self

    def lte(self, column, value):
        self.filters.append(("lte", column, value))
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = self.rows
        for operation, column, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif operation == "in":
                rows = [row for row in rows if row.get(column) in value]
            elif operation == "is":
                rows = [row for row in rows if row.get(column) is value]
            elif operation == "not_is":
                rows = [row for row in rows if row.get(column) is not value]
            elif operation == "lte":
                rows = [
                    row
                    for row in rows
                    if row.get(column) is not None and row[column] <= value
                ]
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        if self.operation == "update":
            for row in rows:
                row.update(self.values)
        elif self.operation == "delete":
            for row in rows:
                self.rows.remove(row)
        return SimpleNamespace(data=[dict(row) for row in rows])


class FakeNotFilter:
    def __init__(self, query):
        self.query = query

    def is_(self, column, value):
        self.query.filters.append(
            ("not_is", column, None if value == "null" else value)
        )
        return self.query


class FakeBucket:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.removed = []

    def remove(self, paths):
        if self.fail:
            raise RuntimeError("storage unavailable")
        self.removed.extend(paths)
        return SimpleNamespace(data=paths)


class FakeStorage:
    def __init__(self, bucket):
        self.bucket = bucket

    def from_(self, name):
        assert name == cleanup.LEARNER_AUDIO_BUCKET
        return self.bucket


class FakeSupabase:
    def __init__(self, attempts, *, sessions=None, skips=None, storage_fails=False):
        self.attempts = attempts
        self.sessions = sessions or []
        self.skips = skips or []
        self.bucket = FakeBucket(fail=storage_fails)
        self.storage = FakeStorage(self.bucket)

    def table(self, name):
        tables = {
            cleanup.ATTEMPTS_TABLE: self.attempts,
            cleanup.SESSIONS_TABLE: self.sessions,
            cleanup.SKIPS_TABLE: self.skips,
        }
        return FakeQuery(tables[name])


def test_expired_audio_is_deleted_and_marked(monkeypatch):
    attempts = [
        {
            "id": "expired",
            "audio_object_path": "user/session/expired.m4a",
            "audio_expires_at": "2026-08-25T11:00:00Z",
            "audio_deleted_at": None,
        },
        {
            "id": "future",
            "audio_object_path": "user/session/future.m4a",
            "audio_expires_at": "2026-08-26T11:00:00Z",
            "audio_deleted_at": None,
        },
    ]
    fake = FakeSupabase(attempts)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)

    count = cleanup.delete_expired_audio(now=NOW)

    assert count == 1
    assert fake.bucket.removed == ["user/session/expired.m4a"]
    assert attempts[0]["audio_deleted_at"] == "2026-08-25T12:00:00Z"
    assert attempts[1]["audio_deleted_at"] is None


def test_storage_failure_does_not_mark_audio_deleted(monkeypatch):
    attempts = [
        {
            "id": "expired",
            "audio_object_path": "user/session/expired.m4a",
            "audio_expires_at": "2026-08-25T11:00:00Z",
            "audio_deleted_at": None,
        }
    ]
    fake = FakeSupabase(attempts, storage_fails=True)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)

    with pytest.raises(RuntimeError, match="storage unavailable"):
        cleanup.delete_expired_audio(now=NOW)

    assert attempts[0]["audio_deleted_at"] is None


def test_stale_processing_attempt_is_failed_to_release_question_lock(monkeypatch):
    attempts = [
        {
            "id": "stale",
            "processing_status": "evaluating",
            "updated_at": "2026-08-25T11:00:00Z",
        },
        {
            "id": "recent",
            "processing_status": "evaluating",
            "updated_at": "2026-08-25T11:55:00Z",
        },
    ]
    fake = FakeSupabase(attempts)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)
    monkeypatch.setattr(cleanup.Config, "SPEAKING_COACH_PROCESSING_STALE_MINUTES", 10)

    count = cleanup.fail_stale_processing_attempts(now=NOW)

    assert count == 1
    assert attempts[0]["processing_status"] == "failed"
    assert attempts[0]["failure_code"] == "processing_interrupted"
    assert attempts[1]["processing_status"] == "evaluating"


def test_user_audio_cleanup_ignores_expiry(monkeypatch):
    attempts = [
        {
            "id": "target",
            "user_id": "user-1",
            "audio_object_path": "user-1/session/audio.m4a",
            "audio_expires_at": "2026-08-26T11:00:00Z",
            "audio_deleted_at": None,
        },
        {
            "id": "other",
            "user_id": "user-2",
            "audio_object_path": "user-2/session/audio.m4a",
            "audio_deleted_at": None,
        },
    ]
    fake = FakeSupabase(attempts)

    count = cleanup.delete_user_audio("user-1", now=NOW, client=fake)

    assert count == 1
    assert fake.bucket.removed == ["user-1/session/audio.m4a"]
    assert attempts[0]["audio_deleted_at"] is not None
    assert attempts[1]["audio_deleted_at"] is None


def test_user_history_cleanup_removes_sessions_attempts_and_skips():
    sessions = [
        {"id": "target-session", "user_id": "user-1"},
        {"id": "other-session", "user_id": "user-2"},
    ]
    attempts = [
        {"id": "target-attempt", "session_id": "target-session"},
        {"id": "other-attempt", "session_id": "other-session"},
    ]
    skips = [
        {"id": "target-skip", "session_id": "target-session"},
        {"id": "other-skip", "session_id": "other-session"},
    ]
    fake = FakeSupabase(attempts, sessions=sessions, skips=skips)

    count = cleanup.delete_user_history("user-1", client=fake)

    assert count == 1
    assert [row["id"] for row in sessions] == ["other-session"]
    assert [row["id"] for row in attempts] == ["other-attempt"]
    assert [row["id"] for row in skips] == ["other-skip"]


def test_old_detailed_data_is_redacted_but_compact_metrics_remain(monkeypatch):
    attempts = [
        {
            "id": "old",
            "created_at": "2026-05-01T00:00:00Z",
            "evaluation_context": {"prompt": "private"},
            "provider_response_raw": {"id": "interaction"},
            "provider_output_text": "raw model output",
            "failure_detail": "provider details",
            "transcript": "I'm studying English.",
            "content_result": {"meaning_correct": True},
            "pronunciation_result": {"intelligible": True},
            "feedback_en": "Good answer.",
            "feedback_th": "คำตอบดี",
            "detected_issues": [{"category": "grammar"}],
            "displayed_issues": [{"category": "grammar"}],
            "corrected_answer": "I'm studying English.",
            "retry_focus": ["grammar"],
            "normalized_evaluation": {"status": "retry"},
            "audio_object_path": "user/session/old.m4a",
            "audio_deleted_at": "2026-05-01T01:00:00Z",
            "evaluation_result": "retry",
            "provider": "azure+gemini",
            "latency_ms": 1200,
            "usage": {"total_token_count": 42},
        },
        {
            "id": "recent",
            "created_at": "2026-08-24T00:00:00Z",
            "provider_response_raw": {"id": "recent"},
            "failure_detail": "recent details",
        },
    ]
    fake = FakeSupabase(attempts)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)
    monkeypatch.setattr(
        cleanup.Config, "SPEAKING_COACH_DETAILED_RETENTION_DAYS", 90
    )

    count = cleanup.redact_expired_attempt_details(now=NOW)

    assert count == 1
    assert attempts[0]["evaluation_context"] is None
    assert attempts[0]["provider_response_raw"] is None
    assert attempts[0]["provider_output_text"] is None
    assert attempts[0]["failure_detail"] is None
    assert attempts[0]["transcript"] is None
    assert attempts[0]["content_result"] is None
    assert attempts[0]["pronunciation_result"] is None
    assert attempts[0]["feedback_en"] is None
    assert attempts[0]["feedback_th"] is None
    assert attempts[0]["detected_issues"] == []
    assert attempts[0]["displayed_issues"] == []
    assert attempts[0]["corrected_answer"] is None
    assert attempts[0]["retry_focus"] == []
    assert attempts[0]["normalized_evaluation"] is None
    assert attempts[0]["audio_object_path"] is None
    assert attempts[0]["evaluation_result"] == "retry"
    assert attempts[0]["provider"] == "azure+gemini"
    assert attempts[0]["latency_ms"] == 1200
    assert attempts[0]["usage"] == {"total_token_count": 42}
    assert attempts[1]["provider_response_raw"] == {"id": "recent"}


def test_redaction_keeps_path_when_audio_deletion_is_unconfirmed(monkeypatch):
    attempts = [
        {
            "id": "old",
            "created_at": "2026-05-01T00:00:00Z",
            "normalized_evaluation": {"status": "pass"},
            "audio_object_path": "user/session/orphan-risk.m4a",
            "audio_deleted_at": None,
        }
    ]
    fake = FakeSupabase(attempts)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)
    monkeypatch.setattr(
        cleanup.Config, "SPEAKING_COACH_DETAILED_RETENTION_DAYS", 90
    )

    cleanup.redact_expired_attempt_details(now=NOW)

    assert attempts[0]["normalized_evaluation"] is None
    assert attempts[0]["audio_object_path"] == "user/session/orphan-risk.m4a"


def test_expired_identifiable_history_is_deleted(monkeypatch):
    sessions = [
        {"id": "old-session", "created_at": "2025-08-01T00:00:00Z"},
        {"id": "recent-session", "created_at": "2026-08-01T00:00:00Z"},
    ]
    attempts = [
        {
            "id": "old-attempt",
            "session_id": "old-session",
            "audio_object_path": "user/old-session/audio.m4a",
            "audio_deleted_at": None,
        },
        {
            "id": "recent-attempt",
            "session_id": "recent-session",
            "audio_object_path": None,
            "audio_deleted_at": "2026-08-01T01:00:00Z",
        },
    ]
    skips = [
        {"id": "old-skip", "session_id": "old-session"},
        {"id": "recent-skip", "session_id": "recent-session"},
    ]
    fake = FakeSupabase(attempts, sessions=sessions, skips=skips)
    monkeypatch.setattr(cleanup, "supabase_admin", fake)
    monkeypatch.setattr(cleanup.Config, "SPEAKING_COACH_HISTORY_RETENTION_DAYS", 365)

    count = cleanup.delete_expired_history(now=NOW)

    assert count == 1
    assert fake.bucket.removed == ["user/old-session/audio.m4a"]
    assert [row["id"] for row in sessions] == ["recent-session"]
    assert [row["id"] for row in attempts] == ["recent-attempt"]
    assert [row["id"] for row in skips] == ["recent-skip"]

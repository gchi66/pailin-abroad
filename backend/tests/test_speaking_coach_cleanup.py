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
    def __init__(self, attempts, *, storage_fails=False):
        self.attempts = attempts
        self.bucket = FakeBucket(fail=storage_fails)
        self.storage = FakeStorage(self.bucket)

    def table(self, name):
        assert name == cleanup.ATTEMPTS_TABLE
        return FakeQuery(self.attempts)


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


def test_old_diagnostics_are_redacted_but_normalized_results_remain(monkeypatch):
    attempts = [
        {
            "id": "old",
            "created_at": "2026-05-01T00:00:00Z",
            "evaluation_context": {"prompt": "private"},
            "provider_response_raw": {"id": "interaction"},
            "provider_output_text": "raw model output",
            "failure_detail": "provider details",
            "normalized_evaluation": {"status": "retry"},
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
        cleanup.Config, "SPEAKING_COACH_DIAGNOSTIC_RETENTION_DAYS", 90
    )

    count = cleanup.redact_expired_diagnostics(now=NOW)

    assert count == 1
    assert attempts[0]["evaluation_context"] is None
    assert attempts[0]["provider_response_raw"] is None
    assert attempts[0]["provider_output_text"] is None
    assert attempts[0]["failure_detail"] is None
    assert attempts[0]["normalized_evaluation"] == {"status": "retry"}
    assert attempts[0]["usage"] == {"total_token_count": 42}
    assert attempts[1]["provider_response_raw"] == {"id": "recent"}

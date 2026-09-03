from types import SimpleNamespace
from importlib import import_module
from io import BytesIO

from flask import Flask
import pytest

from app.speaking_coach_evaluator import (
    EvaluatorError,
    EvaluatorResult,
    SpeakingEvaluation,
)


module = import_module("app.speaking_coach")
SUBMISSION_ID = "11111111-1111-4111-8111-111111111111"


class FakeQuery:
    def __init__(self, rows, selected_columns, table_name=None):
        self.rows = rows
        self.selected_columns = selected_columns
        self.table_name = table_name
        self.filters = []
        self.limit_count = None
        self.operation = "select"
        self.values = None

    @property
    def not_(self):
        return FakeNotFilter(self)

    def select(self, columns):
        self.selected_columns.append(columns)
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, set(values)))
        return self

    def order(self, _column):
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def insert(self, values):
        self.operation = "insert"
        self.values = dict(values)
        return self

    def update(self, values):
        self.operation = "update"
        self.values = dict(values)
        return self

    def execute(self):
        if self.operation == "insert":
            if self.table_name == "user_speaking_coach_attempts":
                for row in self.rows:
                    if (
                        row.get("session_id") == self.values.get("session_id")
                        and row.get("client_submission_id")
                        == self.values.get("client_submission_id")
                    ):
                        raise RuntimeError(
                            "23505 user_speaking_coach_attempts_submission_unique"
                        )
                    if (
                        row.get("session_id") == self.values.get("session_id")
                        and row.get("question_id") == self.values.get("question_id")
                        and row.get("processing_status") in {"uploaded", "evaluating"}
                    ):
                        raise RuntimeError(
                            "23505 user_speaking_coach_attempts_one_processing"
                        )
            self.rows.append(dict(self.values))
            return SimpleNamespace(data=[dict(self.values)])
        rows = self.rows
        for operation, column, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(column) == value]
            elif operation == "is":
                expected = None if value == "null" else value
                rows = [row for row in rows if row.get(column) is expected]
            elif operation == "not_is":
                expected = None if value == "null" else value
                rows = [row for row in rows if row.get(column) is not expected]
            else:
                rows = [row for row in rows if row.get(column) in value]
        if self.operation == "update":
            for row in rows:
                row.update(self.values)
                if row.get("processing_status") == "completed":
                    row["completes_question"] = row.get("evaluation_result") in {
                        "pass",
                        "continue_with_correction",
                    }
            return SimpleNamespace(data=[dict(row) for row in rows])
        result = rows[: self.limit_count] if self.limit_count is not None else rows
        return SimpleNamespace(data=[dict(row) for row in result])


class FakeNotFilter:
    def __init__(self, query):
        self.query = query

    def is_(self, column, value):
        self.query.filters.append(("not_is", column, value))
        return self.query


class FakeBucket:
    def __init__(self):
        self.uploads = []
        self.removed = []

    def upload(self, path, data, options):
        self.uploads.append((path, data, options))
        return SimpleNamespace(path=path)

    def remove(self, paths):
        self.removed.extend(paths)
        return SimpleNamespace(data=list(paths))


class FakeStorage:
    def __init__(self):
        self.buckets = {}

    def from_(self, name):
        return self.buckets.setdefault(name, FakeBucket())


class FakeSupabase:
    def __init__(self):
        self.selected_columns = []
        self.storage = FakeStorage()
        self.tables = {
            "users": [{"id": "user-123", "is_admin": True}],
            "lessons": [
                {
                    "id": "lesson-uuid",
                    "lesson_external_id": "4.1",
                    "title": "What are you doing?",
                    "title_th": "คุณกำลังทำอะไร",
                }
            ],
            "speaking_coach_practice_sets": [
                {
                    "id": 20,
                    "lesson_id": "lesson-uuid",
                    "practice_type": "open",
                    "tip_en": "Use present continuous.",
                    "tip_th": "ใช้ present continuous",
                    "sort_order": 2,
                    "is_active": True,
                    "focus": "private rubric",
                    "content_hash": "practice-20",
                },
                {
                    "id": 10,
                    "lesson_id": "lesson-uuid",
                    "practice_type": "pronunciation",
                    "tip_en": None,
                    "tip_th": None,
                    "sort_order": 1,
                    "is_active": True,
                    "focus": "private rubric",
                    "content_hash": "practice-10",
                },
            ],
            "speaking_coach_questions": [
                {
                    "id": 201,
                    "practice_set_id": 20,
                    "sort_order": 1,
                    "prompt_en": "What are you studying?",
                    "prompt_th": "คุณกำลังเรียนอะไร",
                    "examples": [{"en": "I'm studying Thai.", "th": "..."}],
                    "prompt_audio_key": "4.1_speaking_2.mp3",
                    "target_answers": ["private answer"],
                    "focus": "question-specific open rubric",
                    "focus_items": [
                        {
                            "priority": 1,
                            "instruction": "question-specific open rubric",
                        }
                    ],
                    "is_active": True,
                    "content_hash": "question-201",
                },
                {
                    "id": 101,
                    "practice_set_id": 10,
                    "sort_order": 1,
                    "prompt_en": "I'm eating lunch.",
                    "prompt_th": "ฉันกำลังกินข้าวเที่ยง",
                    "examples": [],
                    "prompt_audio_key": "4.1_speaking_1.mp3",
                    "target_answers": ["private answer"],
                    "focus": "question-specific pronunciation rubric",
                    "focus_items": [
                        {
                            "priority": 2,
                            "instruction": "question-specific pronunciation rubric",
                        }
                    ],
                    "is_active": True,
                    "content_hash": "question-101",
                },
            ],
            "user_speaking_coach_sessions": [],
            "user_speaking_coach_attempts": [],
            "user_speaking_coach_skips": [],
        }

    def table(self, name):
        return FakeQuery(self.tables.get(name, []), self.selected_columns, name)


def _client(monkeypatch, *, authenticated=True):
    app = Flask(__name__)
    app.register_blueprint(module.speaking_coach)
    fake_supabase = FakeSupabase()
    monkeypatch.setattr(module, "supabase_admin", fake_supabase)
    monkeypatch.setattr(module.Config, "SUPABASE_URL", "https://example.supabase.co")
    user = SimpleNamespace(id="user-123") if authenticated else None
    monkeypatch.setattr(
        module,
        "create_auth_client",
        lambda: SimpleNamespace(
            auth=SimpleNamespace(
                get_user=lambda _token: SimpleNamespace(user=user)
            )
        ),
    )
    return app.test_client(), fake_supabase


def _headers():
    return {"Authorization": "Bearer test-token"}


def test_lesson_requires_authentication(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/speaking/lessons/4.1")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Authorization token required"}


def test_cleanup_endpoint_requires_secret(monkeypatch):
    client, _ = _client(monkeypatch)
    monkeypatch.setattr(module.Config, "SPEAKING_COACH_CLEANUP_SECRET", "secret")

    response = client.post("/api/internal/speaking/cleanup")

    assert response.status_code == 401


def test_cleanup_endpoint_runs_retention_pass(monkeypatch):
    client, _ = _client(monkeypatch)
    monkeypatch.setattr(module.Config, "SPEAKING_COACH_CLEANUP_SECRET", "secret")
    monkeypatch.setattr(
        module,
        "run_retention_cleanup",
        lambda: {"audio_deleted": 2, "diagnostics_redacted": 3},
    )

    response = client.post(
        "/api/internal/speaking/cleanup",
        headers={"Authorization": "Bearer secret"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "audio_deleted": 2,
        "diagnostics_redacted": 3,
    }


def test_lesson_rejects_invalid_token(monkeypatch):
    client, _ = _client(monkeypatch, authenticated=False)

    response = client.get("/api/speaking/lessons/4.1", headers=_headers())

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid token"}


def test_admin_can_list_available_speaking_lessons(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/speaking/lessons", headers=_headers())

    assert response.status_code == 200
    assert response.get_json() == {
        "lessons": [
            {
                "id": "lesson-uuid",
                "lesson_external_id": "4.1",
                "title": "What are you doing?",
                "title_th": "คุณกำลังทำอะไร",
                "practice_set_count": 2,
                "question_count": 2,
            }
        ]
    }


def test_non_admin_cannot_list_available_speaking_lessons(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    fake_supabase.tables["users"][0]["is_admin"] = False

    response = client.get("/api/speaking/lessons", headers=_headers())

    assert response.status_code == 403
    assert response.get_json() == {"error": "Admin access required"}


def test_lesson_returns_ordered_display_safe_curriculum(monkeypatch):
    client, fake_supabase = _client(monkeypatch)

    response = client.get("/api/speaking/lessons/4.1", headers=_headers())

    assert response.status_code == 200
    lesson = response.get_json()["lesson"]
    assert lesson["lesson_external_id"] == "4.1"
    assert lesson["practice_set_count"] == 2
    assert lesson["question_count"] == 2
    assert [item["practice_type"] for item in lesson["practice_sets"]] == [
        "pronunciation",
        "open",
    ]
    first_question = lesson["practice_sets"][0]["questions"][0]
    second_question = lesson["practice_sets"][1]["questions"][0]
    assert first_question["position"] == 1
    assert first_question["lesson_position"] == 1
    assert second_question["position"] == 1
    assert second_question["lesson_position"] == 2
    assert first_question["prompt_audio_url"] == (
        "https://example.supabase.co/storage/v1/object/public/"
        "speaking-coach-prompts/4.1_speaking_1.mp3"
    )
    response_text = response.get_data(as_text=True)
    assert "focus" not in response_text
    assert "focus_items" not in response_text
    assert "target_answers" not in response_text
    assert all("focus" not in columns for columns in fake_supabase.selected_columns)
    assert all(
        "target_answers" not in columns
        for columns in fake_supabase.selected_columns
    )


def test_admin_can_request_test_answer_without_exposing_target_answer_list(monkeypatch):
    client, _fake_supabase = _client(monkeypatch)

    response = client.get(
        "/api/speaking/lessons/4.1?include_test_answers=1",
        headers=_headers(),
    )

    assert response.status_code == 200
    first_question = response.get_json()["lesson"]["practice_sets"][0][
        "questions"
    ][0]
    assert first_question["test_answer_en"] == "private answer"
    assert "target_answers" not in first_question


def test_non_admin_cannot_request_test_answer(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    fake_supabase.tables["users"][0]["is_admin"] = False

    response = client.get(
        "/api/speaking/lessons/4.1?include_test_answers=1",
        headers=_headers(),
    )

    assert response.status_code == 200
    first_question = response.get_json()["lesson"]["practice_sets"][0][
        "questions"
    ][0]
    assert "test_answer_en" not in first_question
    assert "target_answers" not in first_question


def test_missing_lesson_returns_404(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/speaking/lessons/9.9", headers=_headers())

    assert response.status_code == 404
    assert response.get_json() == {"error": "Speaking lesson not found"}


def test_session_create_then_resume(monkeypatch):
    client, fake_supabase = _client(monkeypatch)

    created = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    )
    resumed = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    )

    assert created.status_code == 201
    assert resumed.status_code == 200
    assert created.get_json()["session"]["id"] == resumed.get_json()["session"]["id"]
    assert created.get_json()["session"]["current_question_id"] == 101
    assert len(fake_supabase.tables["user_speaking_coach_sessions"]) == 1


def test_session_resume_restores_latest_retry_context(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    created = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "retry-2",
            "session_id": created["id"],
            "question_id": 101,
            "evaluation_sequence": 2,
            "instructional_attempt_number": 2,
            "processing_status": "completed",
            "evaluation_result": "retry",
            "normalized_evaluation": {"status": "retry"},
            "completes_question": False,
        }
    )

    resumed = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    )

    assert resumed.status_code == 200
    session = resumed.get_json()["session"]
    assert session["instructional_attempt_number"] == 2
    assert session["previous_attempt_id"] == "retry-2"


def test_force_new_session_preserves_old_session_as_abandoned(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    original = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]

    response = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1", "force_new": True},
    )

    assert response.status_code == 201
    replacement = response.get_json()["session"]
    assert replacement["id"] != original["id"]
    sessions = fake_supabase.tables["user_speaking_coach_sessions"]
    assert len(sessions) == 2
    assert sessions[0]["status"] == "abandoned"
    assert sessions[1]["status"] == "active"


def test_skip_persists_and_advances_session(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]

    skipped = client.post(
        f"/api/speaking/sessions/{session['id']}/questions/101/skip",
        headers=_headers(),
    )
    resumed = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    )

    assert skipped.status_code == 200
    payload = skipped.get_json()["session"]
    assert payload["current_question_id"] == 201
    assert payload["completed_question_ids"] == []
    assert payload["skipped_question_ids"] == [101]
    assert payload["correct_question_ids"] == []
    assert payload["needs_review_question_ids"] == [101]
    assert resumed.get_json()["session"]["current_question_id"] == 201
    assert fake_supabase.tables["user_speaking_coach_skips"][0]["question_id"] == 101


def test_skipping_final_unresolved_question_completes_session(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "first-attempt",
            "user_id": "user-123",
            "session_id": session["id"],
            "question_id": 101,
            "processing_status": "completed",
            "evaluation_result": "pass",
            "completes_question": True,
            "audio_object_path": "user-123/session/first.m4a",
            "audio_deleted_at": None,
        }
    )

    response = client.post(
        f"/api/speaking/sessions/{session['id']}/questions/201/skip",
        headers=_headers(),
    )
    repeated = client.post(
        f"/api/speaking/sessions/{session['id']}/questions/201/skip",
        headers=_headers(),
    )

    assert response.status_code == 200
    assert repeated.status_code == 200
    payload = response.get_json()["session"]
    assert payload["status"] == "completed"
    assert payload["current_question_id"] is None
    assert payload["skipped_question_ids"] == [201]
    assert payload["correct_question_ids"] == [101]
    assert payload["needs_review_question_ids"] == [201]
    bucket = fake_supabase.storage.buckets[module.LEARNER_AUDIO_BUCKET]
    assert bucket.removed == ["user-123/session/first.m4a"]
    assert len(fake_supabase.tables["user_speaking_coach_skips"]) == 1


def test_evaluation_rejects_a_skipped_question(monkeypatch):
    client, _ = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    client.post(
        f"/api/speaking/sessions/{session['id']}/questions/101/skip",
        headers=_headers(),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session["id"],
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"fake m4a audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json() == {"error": "This speaking question was skipped."}


@pytest.mark.parametrize(
    ("upload", "expected_mime_type"),
    [
        ((b"fake m4a audio", "recording.m4a", "audio/mp4"), "audio/mp4"),
        (
            (b"RIFF\x00\x00\x00\x00WAVEfake", "recording.wav", "application/octet-stream"),
            "audio/wav",
        ),
        (
            (b"RIFF\x00\x00\x00\x00WAVEfake", "recording.wav", "audio/vnd.wave"),
            "audio/wav",
        ),
    ],
)
def test_evaluation_uploads_audio_persists_result_and_advances(
    monkeypatch, upload, expected_mime_type
):
    client, fake_supabase = _client(monkeypatch)
    session_response = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    )
    session_id = session_response.get_json()["session"]["id"]
    evaluation = SpeakingEvaluation.model_validate(
        {
            "status": "pass",
            "transcript": "I'm eating lunch.",
            "content": {
                "meaning_correct": True,
                "relevant": True,
                "target_usage_correct": True,
                "grammar_correct": True,
            },
            "pronunciation": {"intelligible": True, "issues": []},
            "detected_issues": [],
            "displayed_issues": [],
            "corrected_answer": None,
            "feedback_en": "Clear and correct.",
            "feedback_th": "ชัดเจนและถูกต้อง",
            "retry_focus": [],
        }
    )
    captured_evaluator = {}

    def fake_evaluator(**kwargs):
        captured_evaluator.update(kwargs)
        return EvaluatorResult(
            evaluation=evaluation,
            provider="google",
            model="gemini-3.5-flash-lite",
            latency_ms=120,
            usage={"total_token_count": 12},
            provider_metadata={"id": "interaction-1"},
            provider_output_text=evaluation.model_dump_json(),
            evaluation_context={"focus": "private rubric"},
        )

    monkeypatch.setattr(module, "evaluate_speaking_attempt", fake_evaluator)

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "instructional_attempt_number": "1",
            "audio": (BytesIO(upload[0]), upload[1], upload[2]),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["attempt"]["evaluation"]["status"] == "pass"
    debug = payload["attempt"]["debug"]
    assert {key: value for key, value in debug.items() if key != "request_timings_ms"} == {
        "provider": "google",
        "model": "gemini-3.5-flash-lite",
        "latency_ms": 120,
        "usage": {"total_token_count": 12},
        "provider_response": {"id": "interaction-1"},
    }
    assert set(debug["request_timings_ms"]) == {
        "auth",
        "setup",
        "audio_storage",
        "evaluator",
        "persistence",
        "total",
    }
    assert payload["session"]["current_question_id"] == 201
    assert payload["session"]["correct_question_ids"] == [101]
    assert payload["session"]["needs_review_question_ids"] == []
    attempt = fake_supabase.tables["user_speaking_coach_attempts"][0]
    assert attempt["processing_status"] == "completed"
    assert attempt["evaluation_result"] == "pass"
    assert attempt["client_submission_id"] == SUBMISSION_ID
    assert attempt["normalized_evaluation"]["status"] == "pass"
    assert attempt["evaluation_context"]["focus"] == "private rubric"
    capture_diagnostics = attempt["evaluation_context"]["capture_diagnostics"]
    assert capture_diagnostics["byte_count"] == len(upload[0])
    assert capture_diagnostics["mime_type"] == expected_mime_type
    assert capture_diagnostics["looks_like_wav"] is (
        expected_mime_type == "audio/wav"
    )
    assert captured_evaluator["audio_mime_type"] == expected_mime_type
    assert captured_evaluator["focus"] == "question-specific pronunciation rubric"
    assert captured_evaluator["focus_items"] == [
        {
            "priority": 2,
            "instruction": "question-specific pronunciation rubric",
        }
    ]
    uploads = fake_supabase.storage.buckets[module.LEARNER_AUDIO_BUCKET].uploads
    assert len(uploads) == 1
    assert uploads[0][0].endswith(
        ".wav" if expected_mime_type == "audio/wav" else ".m4a"
    )
    assert uploads[0][2]["content-type"] == expected_mime_type


def test_completed_submission_is_replayed_without_another_provider_call(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    evaluation = SpeakingEvaluation.model_validate(
        {
            "status": "pass",
            "transcript": "I'm eating lunch.",
            "content": {},
            "pronunciation": {"intelligible": True, "issues": []},
            "feedback_en": "Good.",
            "feedback_th": "ดี",
        }
    )
    provider_calls = []

    def fake_evaluator(**_kwargs):
        provider_calls.append(True)
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model="speech-to-text-short-v1",
            latency_ms=50,
            usage={},
            provider_metadata={},
            provider_output_text="{}",
            evaluation_context={},
        )

    monkeypatch.setattr(module, "evaluate_speaking_attempt", fake_evaluator)

    def submit():
        return client.post(
            "/api/speaking/evaluate",
            headers=_headers(),
            data={
                "session_id": session_id,
                "question_id": "101",
                "client_submission_id": SUBMISSION_ID,
                "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
            },
            content_type="multipart/form-data",
        )

    original = submit()
    replay = submit()

    assert original.status_code == 200
    assert replay.status_code == 200
    assert replay.get_json()["attempt"]["replayed"] is True
    assert replay.get_json()["attempt"]["id"] == original.get_json()["attempt"]["id"]
    assert len(provider_calls) == 1
    assert len(fake_supabase.tables["user_speaking_coach_attempts"]) == 1
    assert len(fake_supabase.storage.buckets[module.LEARNER_AUDIO_BUCKET].uploads) == 1


def test_session_reports_consecutive_unclear_audio_and_usable_result_resets_count(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    attempts = fake_supabase.tables["user_speaking_coach_attempts"]
    for sequence in range(1, 4):
        attempts.append(
            {
                "id": f"unclear-{sequence}",
                "session_id": session["id"],
                "question_id": 101,
                "evaluation_sequence": sequence,
                "instructional_attempt_number": 1,
                "processing_status": "completed",
                "evaluation_result": "unclear_audio",
                "normalized_evaluation": {"status": "unclear_audio"},
                "completes_question": False,
            }
        )

    resumed = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    assert resumed["consecutive_unclear_audio_count"] == 3
    assert resumed["unclear_audio_retry_limit"] == 5

    attempts.append(
        {
            "id": "usable-retry",
            "session_id": session["id"],
            "question_id": 101,
            "evaluation_sequence": 4,
            "instructional_attempt_number": 1,
            "processing_status": "completed",
            "evaluation_result": "retry",
            "normalized_evaluation": {"status": "retry"},
            "completes_question": False,
        }
    )
    resumed_after_usable_result = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    assert resumed_after_usable_result["consecutive_unclear_audio_count"] == 0


def test_sixth_consecutive_unclear_audio_submission_is_blocked(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    attempts = fake_supabase.tables["user_speaking_coach_attempts"]
    for sequence in range(1, 6):
        attempts.append(
            {
                "id": f"unclear-{sequence}",
                "session_id": session["id"],
                "question_id": 101,
                "client_submission_id": f"00000000-0000-4000-8000-{sequence:012d}",
                "evaluation_sequence": sequence,
                "instructional_attempt_number": 1,
                "processing_status": "completed",
                "evaluation_result": "unclear_audio",
                "normalized_evaluation": {"status": "unclear_audio"},
                "completes_question": False,
            }
        )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session["id"],
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 429
    payload = response.get_json()
    assert payload["code"] == "unclear_audio_limit_reached"
    assert payload["session"]["consecutive_unclear_audio_count"] == 5
    assert len(attempts) == 5


def test_same_submission_reports_in_progress_without_provider_call(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "processing-attempt",
            "session_id": session_id,
            "question_id": 101,
            "client_submission_id": SUBMISSION_ID,
            "evaluation_sequence": 1,
            "instructional_attempt_number": 1,
            "processing_status": "evaluating",
            "completes_question": False,
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "submission_in_progress"
    assert len(fake_supabase.tables["user_speaking_coach_attempts"]) == 1


def test_different_submission_is_rejected_while_question_is_processing(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "processing-attempt",
            "session_id": session_id,
            "question_id": 101,
            "client_submission_id": SUBMISSION_ID,
            "evaluation_sequence": 1,
            "instructional_attempt_number": 1,
            "processing_status": "evaluating",
            "completes_question": False,
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": "22222222-2222-4222-8222-222222222222",
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "question_evaluation_in_progress"
    assert len(fake_supabase.tables["user_speaking_coach_attempts"]) == 1


def test_failed_submission_is_replayed_as_failure_without_provider_call(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "failed-attempt",
            "session_id": session_id,
            "question_id": 101,
            "client_submission_id": SUBMISSION_ID,
            "evaluation_sequence": 1,
            "instructional_attempt_number": 1,
            "processing_status": "failed",
            "failure_code": "azure_timeout",
            "completes_question": False,
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: pytest.fail("provider must not be called"),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "submission_failed"
    assert response.get_json()["failure_code"] == "azure_timeout"


def test_submission_id_cannot_be_reused_for_another_question(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "original-attempt",
            "session_id": session_id,
            "question_id": 101,
            "client_submission_id": SUBMISSION_ID,
            "evaluation_sequence": 1,
            "instructional_attempt_number": 1,
            "processing_status": "completed",
            "evaluation_result": "pass",
            "normalized_evaluation": {"status": "pass"},
            "completes_question": True,
        }
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "201",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "submission_id_conflict"


def test_evaluation_omits_debug_diagnostics_for_non_admin(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    fake_supabase.tables["users"][0]["is_admin"] = False
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]
    evaluation = SpeakingEvaluation.model_validate(
        {
            "status": "pass",
            "transcript": "I'm eating lunch.",
            "content": {},
            "pronunciation": {"intelligible": True, "issues": []},
            "feedback_en": "Good.",
            "feedback_th": "ดี",
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model="speech-to-text-short-v1",
            latency_ms=50,
            usage={},
            provider_metadata={"azure": {"response": {"secret": "diagnostic"}}},
            provider_output_text="{}",
            evaluation_context={},
        ),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "debug" not in response.get_json()["attempt"]


def test_evaluation_returns_422_for_malformed_audio(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session_id = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]["id"]

    def fail_evaluator(**_kwargs):
        raise EvaluatorError("audio_invalid", "malformed media")

    monkeypatch.setattr(module, "evaluate_speaking_attempt", fail_evaluator)

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session_id,
            "question_id": "101",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"bad audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 422
    assert response.get_json() == {
        "error": "Audio recording could not be processed",
        "code": "audio_invalid",
    }
    attempt = fake_supabase.tables["user_speaking_coach_attempts"][0]
    assert attempt["processing_status"] == "failed"
    assert attempt["failure_code"] == "audio_invalid"


def test_completing_session_deletes_its_recordings(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    session = client.post(
        "/api/speaking/sessions",
        headers=_headers(),
        json={"lesson_external_id": "4.1"},
    ).get_json()["session"]
    fake_supabase.tables["user_speaking_coach_attempts"].append(
        {
            "id": "first-attempt",
            "user_id": "user-123",
            "session_id": session["id"],
            "question_id": 101,
            "evaluation_sequence": 1,
            "instructional_attempt_number": 1,
            "processing_status": "completed",
            "evaluation_result": "pass",
            "normalized_evaluation": {"status": "pass"},
            "completes_question": True,
            "audio_object_path": "user-123/session/first.m4a",
            "audio_deleted_at": None,
        }
    )
    evaluation = SpeakingEvaluation.model_validate(
        {
            "status": "pass",
            "transcript": "I'm studying Thai.",
            "content": {
                "meaning_correct": True,
                "relevant": True,
                "target_usage_correct": True,
                "grammar_correct": True,
            },
            "pronunciation": {"intelligible": True, "issues": []},
            "detected_issues": [],
            "displayed_issues": [],
            "corrected_answer": None,
            "feedback_en": "Clear and correct.",
            "feedback_th": "ชัดเจนและถูกต้อง",
            "retry_focus": [],
        }
    )
    monkeypatch.setattr(
        module,
        "evaluate_speaking_attempt",
        lambda **_kwargs: EvaluatorResult(
            evaluation=evaluation,
            provider="google",
            model="gemini-3.5-flash-lite",
            latency_ms=100,
            usage={},
            provider_metadata={},
            provider_output_text=evaluation.model_dump_json(),
            evaluation_context={},
        ),
    )

    response = client.post(
        "/api/speaking/evaluate",
        headers=_headers(),
        data={
            "session_id": session["id"],
            "question_id": "201",
            "client_submission_id": SUBMISSION_ID,
            "audio": (BytesIO(b"fake m4a audio"), "recording.m4a", "audio/mp4"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert response.get_json()["session"]["status"] == "completed"
    bucket = fake_supabase.storage.buckets[module.LEARNER_AUDIO_BUCKET]
    assert "user-123/session/first.m4a" in bucket.removed
    assert len(bucket.removed) == 2
    attempts = fake_supabase.tables["user_speaking_coach_attempts"]
    assert all(attempt["audio_deleted_at"] for attempt in attempts)

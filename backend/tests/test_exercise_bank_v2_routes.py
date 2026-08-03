from types import SimpleNamespace
from importlib import import_module

from flask import Flask

module = import_module("app.exercise_bank_v2")


class FakeQuery:
    def __init__(self, rows):
        self.rows = [dict(row) for row in rows]
        self.filters = []
        self.order_column = None
        self.limit_count = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.filters.append(("in", column, set(values)))
        return self

    def order(self, column, **_kwargs):
        self.order_column = column
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = self.rows
        for operation, column, value in self.filters:
            if operation == "eq":
                rows = [row for row in rows if row.get(column) == value]
            else:
                rows = [row for row in rows if row.get(column) in value]
        if self.order_column:
            rows = sorted(
                rows,
                key=lambda row: (
                    row.get(self.order_column) is None,
                    row.get(self.order_column),
                ),
            )
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        return SimpleNamespace(data=rows)


class FakeSupabase:
    def __init__(self, table_rows):
        self.table_rows = table_rows
        self.queries = []
        self.rpc_calls = []
        self.rpc_result = {
            "topic_id": 9,
            "question_id": 601,
            "set_number": 1,
            "set_position": 1,
            "attempt_count": 1,
            "has_answered_correctly": True,
            "topic_complete": False,
            "first_completed_at": None,
            "completed_content_version": None,
        }

    def table(self, name):
        query = FakeQuery(self.table_rows.get(name, []))
        self.queries.append((name, query))
        return query

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(data=dict(self.rpc_result))
        )


def _topic(**overrides):
    row = {
        "id": 9,
        "topic": "To-be: am, are, is",
        "display_title": "Pailin is hungry",
        "category": "verbs_and_tenses",
        "sub_category": "present_tense",
        "lesson_external_id": "1.6",
        "sort_order": 1,
        "is_featured": True,
        "featured_sort_order": None,
        "content_version": 2,
        "is_active": True,
    }
    row.update(overrides)
    return row


def _tables():
    questions = []
    for number in range(1, 7):
        content = {
            "text": f"Question {number} _____",
            "accepted_answers": ["secret"],
            "raw_answers": ["secret"],
            "blanks": [
                {
                    "id": "b1",
                    "min_len": 5,
                    "answer": "nested secret",
                }
            ],
        }
        if number == 2:
            content = {
                "text": "Choose one",
                "options": [
                    {"label": "A", "text": "Safe", "is_correct": True},
                    {"label": "B", "text": "Also safe", "is_correct": False},
                ],
                "correct_option": "A",
            }
        questions.append(
            {
                "id": 600 + number,
                "exercise_id": 90,
                "source_number": str(number),
                "content": content,
                "practice_order": number,
                "is_active": True,
                "is_example": False,
            }
        )
    questions.extend(
        [
            {
                "id": 700,
                "exercise_id": 90,
                "source_number": "example",
                "content": {
                    "text": "Example _____",
                    "accepted_answers": ["example answer"],
                    "raw_answers": ["example answer"],
                },
                "sort_order": 1,
                "practice_order": None,
                "is_active": True,
                "is_example": True,
            },
            {
                "id": 701,
                "exercise_id": 90,
                "source_number": "7",
                "content": {"accepted_answers": ["inactive"]},
                "practice_order": 7,
                "is_active": False,
                "is_example": False,
            },
        ]
    )
    states = [
        {
            "topic_id": 9,
            "question_id": 600 + number,
            "set_number": 1 if number <= 5 else 2,
            "set_position": ((number - 1) % 5) + 1,
            "attempt_count": 1,
            "has_answered_correctly": number <= 5,
            "last_attempted_at": "2026-08-01T00:00:00Z",
            "assigned_content_version": 1 if number <= 5 else 2,
            "user_id": "user-123",
        }
        for number in range(1, 7)
    ]
    return {
        "exercise_bank_topics": [
            _topic(),
            _topic(id=1, is_active=False, source_document_id="old-document"),
        ],
        "exercise_bank_exercises": [
            {
                "id": 90,
                "topic_id": 9,
                "exercise_type": "fill_blank",
                "display_type": "Fill in the blank",
                "prompt": "Complete the sentence",
                "keywords": ["am", "are", "is"],
                "sort_order": 1,
                "is_active": True,
            },
            {
                "id": 91,
                "topic_id": 9,
                "exercise_type": "fill_blank",
                "display_type": "Inactive",
                "prompt": "Inactive",
                "keywords": None,
                "sort_order": 2,
                "is_active": False,
            },
        ],
        "exercise_bank_questions": questions,
        "user_exercise_bank_question_state": states,
        "user_exercise_bank_topic_progress": [
            {
                "user_id": "user-123",
                "topic_id": 9,
                "first_completed_at": "2026-07-20T00:00:00Z",
                "completed_content_version": 1,
                "version_completed_at": "2026-07-20T00:00:00Z",
            }
        ],
    }


def _client(monkeypatch, *, authenticated=True):
    app = Flask(__name__)
    app.register_blueprint(module.exercise_bank_v2)
    fake_supabase = FakeSupabase(_tables())
    monkeypatch.setattr(module, "supabase_admin", fake_supabase)
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


def test_topics_require_authentication(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/exercise-bank-v2/topics")

    assert response.status_code == 401
    assert response.get_json() == {"error": "Authorization token required"}


def test_topics_reject_invalid_token(monkeypatch):
    client, _ = _client(monkeypatch, authenticated=False)

    response = client.get("/api/exercise-bank-v2/topics", headers=_headers())

    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid token"}


def test_topic_summaries_include_sets_and_user_progress(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/exercise-bank-v2/topics", headers=_headers())

    assert response.status_code == 200
    topics = response.get_json()["topics"]
    assert len(topics) == 1
    assert topics[0]["id"] == 9
    assert topics[0]["progress"] == {
        "completed_content_version": 1,
        "completed_sets": 1,
        "first_completed_at": "2026-07-20T00:00:00Z",
        "has_new_content": True,
        "is_completed": True,
        "is_current_version_completed": False,
        "mastered_questions": 5,
        "total_questions": 6,
        "total_sets": 2,
        "version_completed_at": "2026-07-20T00:00:00Z",
    }


def test_topic_detail_returns_set_summaries_and_resume_target(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/exercise-bank-v2/topics/9", headers=_headers())

    assert response.status_code == 200
    topic = response.get_json()["topic"]
    assert topic["next_incomplete_set"] == 2
    assert topic["sets"] == [
        {
            "attempted_questions": 5,
            "is_complete": True,
            "mastered_questions": 5,
            "question_count": 5,
            "set_number": 1,
        },
        {
            "attempted_questions": 1,
            "is_complete": False,
            "mastered_questions": 0,
            "question_count": 1,
            "set_number": 2,
        },
    ]


def test_set_returns_five_sanitized_questions(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get(
        "/api/exercise-bank-v2/topics/9/sets/1", headers=_headers()
    )

    assert response.status_code == 200
    payload = response.get_json()
    questions = payload["set"]["questions"]
    assert len(questions) == 5
    assert [question["set_position"] for question in questions] == [1, 2, 3, 4, 5]
    assert questions[0]["content"] == {
        "text": "Question 1 _____",
        "blanks": [{"id": "b1", "min_len": 5}],
    }
    assert questions[1]["content"] == {
        "text": "Choose one",
        "options": [
            {"label": "A", "text": "Safe"},
            {"label": "B", "text": "Also safe"},
        ],
    }
    assert questions[0]["exercise"]["examples"] == [
        {
            "id": 700,
            "content": {
                "text": "Example _____",
                "example_answer": "example answer",
            },
        }
    ]
    serialized = response.get_data(as_text=True).lower()
    for secret_key in (
        "accepted_answers",
        "raw_answers",
        "correct_option",
        "is_correct",
        "nested secret",
    ):
        assert secret_key not in serialized


def test_set_not_found_does_not_leak_other_questions(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get(
        "/api/exercise-bank-v2/topics/9/sets/3", headers=_headers()
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "Exercise set not found"}


def test_exact_fill_blank_is_graded_deterministically_and_persisted(monkeypatch):
    client, fake_supabase = _client(monkeypatch)

    response = client.post(
        "/api/exercise-bank-v2/questions/601/answer",
        headers=_headers(),
        json={"user_answer": "secret"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["correct"] is True
    assert payload["grading_method"] == "deterministic"
    assert payload["progress"]["attempt_count"] == 1
    assert fake_supabase.rpc_calls == [
        (
            "record_exercise_bank_v2_attempt",
            {
                "p_user_id": "user-123",
                "p_question_id": 601,
                "p_user_answer": "secret",
                "p_is_correct": True,
                "p_grading_method": "deterministic",
                "p_ai_score": None,
                "p_ai_feedback_en": None,
                "p_ai_feedback_th": None,
                "p_ai_model": None,
            },
        )
    ]


def test_multiple_choice_is_graded_without_ai(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    fake_supabase.table_rows["exercise_bank_exercises"][0]["exercise_type"] = (
        "multiple_choice"
    )

    response = client.post(
        "/api/exercise-bank-v2/questions/602/answer",
        headers=_headers(),
        json={"user_answer": {"label": "b"}},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["correct"] is False
    assert payload["grading_method"] == "deterministic"
    assert fake_supabase.rpc_calls[0][1]["p_is_correct"] is False


def test_non_exact_fill_blank_uses_ai_and_hides_expected_answer(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    monkeypatch.setattr(
        module,
        "evaluate_with_gpt",
        lambda **_kwargs: {
            "correct": False,
            "score": 0.25,
            "feedback_en": "The learner should use secret here.",
            "feedback_th": "ควรใช้ secret",
        },
    )

    response = client.post(
        "/api/exercise-bank-v2/questions/601/answer",
        headers=_headers(),
        json={"user_answer": "different"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["correct"] is False
    assert payload["grading_method"] == "ai"
    assert "secret" not in response.get_data(as_text=True).lower()
    rpc_params = fake_supabase.rpc_calls[0][1]
    assert rpc_params["p_grading_method"] == "ai"
    assert rpc_params["p_ai_score"] == 0.25
    assert rpc_params["p_ai_model"] == "gpt-4o-mini"


def test_correct_or_incorrect_question_requires_correct_judgment(monkeypatch):
    client, fake_supabase = _client(monkeypatch)
    fake_supabase.table_rows["exercise_bank_exercises"][0]["exercise_type"] = (
        "sentence_transform"
    )
    fake_supabase.table_rows["exercise_bank_questions"][0]["content"] = {
        "stem": "How come didn't she answer?",
        "is_correct": False,
        "accepted_answers": ["how come she didnt answer"],
    }

    response = client.post(
        "/api/exercise-bank-v2/questions/601/answer",
        headers=_headers(),
        json={
            "user_answer": {
                "marked_as_correct": False,
                "rewrite": "how come she didnt answer",
            }
        },
    )

    assert response.status_code == 200
    assert response.get_json()["correct"] is True
    assert response.get_json()["grading_method"] == "deterministic"


def test_ai_failure_does_not_persist_attempt(monkeypatch):
    client, fake_supabase = _client(monkeypatch)

    def fail_ai(**_kwargs):
        raise RuntimeError("AI unavailable")

    monkeypatch.setattr(module, "evaluate_with_gpt", fail_ai)

    response = client.post(
        "/api/exercise-bank-v2/questions/601/answer",
        headers=_headers(),
        json={"user_answer": "different"},
    )

    assert response.status_code == 502
    assert response.get_json() == {"error": "Unable to grade this answer right now"}
    assert fake_supabase.rpc_calls == []


def test_answer_submission_rejects_missing_answer(monkeypatch):
    client, fake_supabase = _client(monkeypatch)

    response = client.post(
        "/api/exercise-bank-v2/questions/601/answer",
        headers=_headers(),
        json={},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "user_answer is required"}
    assert fake_supabase.rpc_calls == []

from importlib import import_module
from types import SimpleNamespace

from flask import Flask

from app.tools.parser import GoogleDocsParser


module = import_module("app.practice_review_answers")


def test_review_answer_directive_is_preserved_without_changing_grading_answer():
    exercise = GoogleDocsParser().parse_practice([
        "TYPE: sentence_transform",
        "ITEM: 1",
        "TEXT: I've looked nowhere for my passport, but I can't find it!",
        "ANSWER: ive looked everywhere",
        "REVIEW_ANSWER: I've looked everywhere…",
    ])[0]
    item = exercise["items"][0]
    assert item["answer"] == "ive looked everywhere"
    assert item["review_answer"] == "I've looked everywhere…"


def test_display_answer_directive_is_preserved_without_changing_grading_answer():
    exercise = GoogleDocsParser().parse_practice([
        "TYPE: sentence_transform",
        "QUESTION: 1",
        "STEM: Have a big dog over there.",
        "ANSWER: theres a big dog",
        "DISPLAY_ANSWER: There’s a big dog over there.",
    ])[0]
    item = exercise["items"][0]
    assert item["answer"] == "theres a big dog"
    assert item["display_answer"] == "There’s a big dog over there."


class FakeTable:
    def __init__(self, data):
        self.data = data
        self.writes = []
        self.name = ""

    def table(self, name):
        self.name = name
        return self

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def single(self):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.data[self.name])

    def upsert(self, value, **_kwargs):
        self.writes.append(value)
        return self


def _client(monkeypatch, exercise, cached=None):
    db = FakeTable({"practice_exercises": exercise,
                    "practice_review_answer_cache": cached or []})
    monkeypatch.setattr(module, "supabase_admin", db)
    monkeypatch.setattr(module, "create_auth_client", lambda: SimpleNamespace(
        auth=SimpleNamespace(get_user=lambda _token: SimpleNamespace(user=SimpleNamespace(id="user")))
    ))
    app = Flask(__name__)
    app.register_blueprint(module.practice_review_answers)
    return app.test_client(), db


def test_authored_answer_takes_priority_over_cache_and_ai(monkeypatch):
    exercise = {"id": "exercise", "kind": "sentence_transform", "prompt_md": "Rewrite",
                "items": [{"answer": "ive looked everywhere", "review_answer": "I've looked everywhere…"}]}
    client, db = _client(monkeypatch, exercise)
    monkeypatch.setattr(module, "_generate_review_answer", lambda *_: (_ for _ in ()).throw(AssertionError("AI called")))
    response = client.post("/api/lessons/practice/review-answer",
                           headers={"Authorization": "Bearer token"},
                           json={"exercise_id": "exercise", "item_key": "exercise-1"})
    assert response.status_code == 200
    assert response.json["review_answer"] == "I've looked everywhere…"
    assert not db.writes


def test_first_reveal_generates_and_caches_then_reuses(monkeypatch):
    item = {"answer": "ive looked everywhere", "text": "I've looked nowhere for my passport."}
    exercise = {"id": "exercise", "kind": "sentence_transform", "prompt_md": "Rewrite",
                "items": [item]}
    client, db = _client(monkeypatch, exercise)
    calls = []
    monkeypatch.setattr(module, "_generate_review_answer", lambda *_: calls.append(1) or "I've looked everywhere…")
    payload = {"exercise_id": "exercise", "item_key": "exercise-1"}
    headers = {"Authorization": "Bearer token"}
    first = client.post("/api/lessons/practice/review-answer", headers=headers, json=payload)
    assert first.status_code == 200
    assert first.json["source"] == "generated"
    assert db.writes[0]["review_answer"] == "I've looked everywhere…"

    db.data["practice_review_answer_cache"] = [db.writes[0]]
    second = client.post("/api/lessons/practice/review-answer", headers=headers, json=payload)
    assert second.json["source"] == "cache"
    assert len(calls) == 1

    item["answer"] = "ive searched everywhere"
    third = client.post("/api/lessons/practice/review-answer", headers=headers, json=payload)
    assert third.json["source"] == "generated"
    assert len(calls) == 2

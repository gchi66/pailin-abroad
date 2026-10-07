from importlib import import_module
from types import SimpleNamespace

from flask import Flask


routes_module = import_module("app.routes")


class FakeQuery:
    def __init__(self, result):
        self.result = result

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def execute(self):
        return self.result


class FakeDatabase:
    def __init__(self, results):
        self.results = {table: list(table_results) for table, table_results in results.items()}

    def table(self, name):
        return FakeQuery(self.results[name].pop(0))


def make_client():
    app = Flask(__name__)
    app.register_blueprint(routes_module.routes)
    return app.test_client()


def test_guest_audio_signs_standard_snippets_for_first_lesson(monkeypatch):
    lesson = {
        "id": "lesson-1-1",
        "stage": "Beginner",
        "level": 1,
        "lesson_order": 1,
        "lesson_external_id": "1.1",
        "conversation_audio_url": "Beginner/L1/Conversations/1.1.mp3",
    }
    fake_database = FakeDatabase({
        "lessons": [
            SimpleNamespace(data=[lesson]),
            SimpleNamespace(data=[{"id": lesson["id"]}]),
        ],
        "audio_snippets": [SimpleNamespace(data=[{
            "audio_key": "1.1_prepare_1",
            "section": "prepare",
            "seq": 1,
            "storage_path": "Beginner/L1/Prepare/1.1_prepare_1.mp3",
        }])],
        "lesson_phrases": [SimpleNamespace(data=[])],
    })
    monkeypatch.setattr(routes_module, "supabase_admin", fake_database)
    monkeypatch.setattr(routes_module, "_sign_audio_path", lambda path: f"signed:{path}")
    routes_module._try_audio_cache.clear()

    response = make_client().get(f"/api/lessons/{lesson['id']}/audio-url")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["conversation"]["signed_url"] == "signed:Beginner/L1/Conversations/1.1.mp3"
    assert payload["snippets"] == [{
        "audio_key": "1.1_prepare_1",
        "section": "prepare",
        "seq": 1,
        "storage_path": "Beginner/L1/Prepare/1.1_prepare_1.mp3",
        "signed_url": "signed:Beginner/L1/Prepare/1.1_prepare_1.mp3",
    }]


def test_guest_audio_rejects_lesson_that_is_not_first_in_level(monkeypatch):
    lesson = {
        "id": "lesson-1-2",
        "stage": "Beginner",
        "level": 1,
        "lesson_order": 2,
        "lesson_external_id": "1.2",
        "conversation_audio_url": "Beginner/L1/Conversations/1.2.mp3",
    }
    fake_database = FakeDatabase({
        "lessons": [
            SimpleNamespace(data=[lesson]),
            SimpleNamespace(data=[{"id": "lesson-1-1"}]),
        ],
    })
    monkeypatch.setattr(routes_module, "supabase_admin", fake_database)
    routes_module._try_audio_cache.clear()

    response = make_client().get(f"/api/lessons/{lesson['id']}/audio-url")

    assert response.status_code == 403
    assert response.get_json() == {"error": "Not allowed"}

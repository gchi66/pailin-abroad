from types import SimpleNamespace
from datetime import datetime
from importlib import import_module
from zoneinfo import ZoneInfo

from flask import Flask

routes_module = import_module("app.routes")


class FakeQuery:
    def __init__(self, result):
        self.result = result
        self.select_args = None
        self.filters = []

    def select(self, *args, **kwargs):
        self.select_args = (args, kwargs)
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def single(self):
        return self

    def execute(self):
        return self.result


class FakeSupabase:
    def __init__(self, table_results, user_id="user-123"):
        self.auth = SimpleNamespace(
            get_user=lambda _token: SimpleNamespace(
                user=SimpleNamespace(id=user_id)
            )
        )
        self.table_results = table_results
        self.queries = {}

    def table(self, name):
        query = FakeQuery(self.table_results[name])
        self.queries.setdefault(name, []).append(query)
        return query


def make_client():
    app = Flask(__name__)
    app.register_blueprint(routes_module.routes)
    return app.test_client()


def test_user_profile_keeps_response_contract_and_uses_narrow_select(monkeypatch, capsys):
    fake_supabase = FakeSupabase(
        {
            "users": SimpleNamespace(
                data=[
                    {
                        "id": "user-123",
                        "username": "Pailin",
                        "email": "pailin@example.com",
                        "avatar_image": "avatar.webp",
                        "is_admin": False,
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            ),
            "user_lesson_progress": SimpleNamespace(data=[{"id": 1}], count=1),
        }
    )
    monkeypatch.setattr(routes_module, "supabase", fake_supabase)

    response = make_client().get(
        "/api/user/profile",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "profile": {
            "avatar_image": "avatar.webp",
            "created_at": "2026-01-01T00:00:00Z",
            "email": "pailin@example.com",
            "id": "user-123",
            "is_admin": False,
            "lessons_complete": 1,
            "name": "Pailin",
            "username": "Pailin",
        }
    }
    assert fake_supabase.queries["users"][0].select_args[0] == (
        "id, username, email, avatar_image, is_admin, created_at",
    )
    assert fake_supabase.queries["user_lesson_progress"][0].select_args == (
        ("id",),
        {"count": "exact"},
    )
    assert "[user-profile]" in capsys.readouterr().out


def test_completed_lessons_keeps_nested_lesson_payload(monkeypatch, capsys):
    completed_rows = [
        {
            "id": 9,
            "lesson_id": "lesson-1",
            "is_completed": True,
            "lessons": {"id": "lesson-1", "title": "Hello"},
        }
    ]
    fake_supabase = FakeSupabase(
        {"user_lesson_progress": SimpleNamespace(data=completed_rows)}
    )
    monkeypatch.setattr(routes_module, "supabase", fake_supabase)

    response = make_client().get(
        "/api/user/completed-lessons",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"completed_lessons": completed_rows}
    assert fake_supabase.queries["user_lesson_progress"][0].select_args[0] == (
        "*, lessons(*)",
    )
    assert "[completed-lessons]" in capsys.readouterr().out


def test_daily_streak_keeps_response_contract(monkeypatch, capsys):
    today = datetime.now(ZoneInfo("Asia/Bangkok")).date().isoformat()
    fake_supabase = FakeSupabase({})
    fake_admin = FakeSupabase(
        {
            "users": SimpleNamespace(
                data={
                    "daily_streak": 4,
                    "last_checkin_date": today,
                    "daily_streak_timezone": "Asia/Bangkok",
                }
            )
        }
    )
    monkeypatch.setattr(routes_module, "supabase", fake_supabase)
    monkeypatch.setattr(routes_module, "supabase_admin", fake_admin)

    response = make_client().get(
        "/api/app/user/daily-streak",
        headers={
            "Authorization": "Bearer test-token",
            "X-Timezone": "Asia/Bangkok",
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "checked_in_today": True,
        "daily_streak": 4,
        "last_checkin_date": today,
        "opened_on": today,
        "timezone": "Asia/Bangkok",
    }
    assert "[daily-streak]" in capsys.readouterr().out

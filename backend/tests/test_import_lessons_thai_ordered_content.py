from types import SimpleNamespace

from app.tools import import_lessons


def _content(*tokens):
    return {
        "version": 1,
        "blocks": [{"type": "paragraph", "tokens": list(tokens)}],
    }


class _FakeQuery:
    def __init__(self, owner):
        self.owner = owner
        self.operation = None
        self.payload = None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def single(self):
        return self

    def execute(self):
        if self.operation == "select":
            return SimpleNamespace(data={"items": self.owner.english_items})
        if self.operation == "update":
            self.owner.updates.append(self.payload)
            return SimpleNamespace(data=[self.payload])
        return SimpleNamespace(data=[])


class _FakeSupabase:
    def __init__(self, english_items=None):
        self.english_items = english_items or []
        self.updates = []

    def table(self, _name):
        return _FakeQuery(self)


def test_thai_importer_preserves_valid_ordered_item_and_option_content(monkeypatch):
    item_content = _content(
        {"type": "text", "text": "English"},
        {"type": "line_break"},
        {"type": "text", "text": "ไทย"},
    )
    option_content = _content(
        {"type": "text", "text": "Option"},
        {"type": "line_break"},
        {"type": "text", "text": "ตัวเลือก"},
    )
    exercise = {
        "kind": "multiple_choice",
        "sort_order": 1,
        "thai_document_content_version": 1,
        "items": [{"number": "1"}],
        "items_th": [{
            "number": "1",
            "text": "ไทย",
            "content": item_content,
            "options": [{"label": "A", "text": "ตัวเลือก", "content": option_content}],
        }],
    }
    fake = _FakeSupabase(english_items=[{"number": "1"}])
    monkeypatch.setattr(import_lessons, "supabase", fake)

    import_lessons.upsert_practice_exercises(
        "lesson-id", [exercise], lang="th"
    )

    [patch] = fake.updates
    assert patch["items_th"][0]["content"] == item_content
    assert patch["items_th"][0]["options"][0]["content"] == option_content


def test_thai_importer_strips_entire_ordered_contract_when_validation_fails(monkeypatch):
    exercise = {
        "kind": "fill_blank",
        "sort_order": 1,
        "thai_document_content_version": 1,
        "items": [{"number": "1"}],
        "items_th": [{
            "number": "1",
            "text": "English _____\nไทย —",
            "content": _content({"type": "blank", "id": "b1", "min_len": 0}),
            "options": [{
                "label": "A",
                "text": "legacy option",
                "content": _content({"type": "text", "text": "ordered option"}),
            }],
        }],
    }
    fake = _FakeSupabase(english_items=[{"number": "1"}])
    monkeypatch.setattr(import_lessons, "supabase", fake)

    import_lessons.upsert_practice_exercises(
        "lesson-id", [exercise], lang="th"
    )

    [patch] = fake.updates
    [item] = patch["items_th"]
    assert "content" not in item
    assert "content" not in item["options"][0]
    assert item["text"] == "English _____\nไทย —"


def test_ordered_contract_rejects_blanks_outside_fill_blank():
    errors = import_lessons._validate_thai_document_contract(
        {
            "kind": "open",
            "items": [{"number": "1"}],
        },
        [{
            "number": "1",
            "content": _content({"type": "blank", "id": "b1", "min_len": 5}),
        }],
    )

    assert any("blank is not allowed" in error for error in errors)

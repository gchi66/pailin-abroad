import json
from types import SimpleNamespace

from app.tools.lesson_translation_generate import generate_translations
from app.tools.lesson_translation_manifest import build_manifest


def _paragraph(text, start, *, style="NORMAL_TEXT"):
    return {
        "startIndex": start,
        "endIndex": start + len(text) + 1,
        "paragraph": {
            "elements": [
                {
                    "startIndex": start,
                    "endIndex": start + len(text) + 1,
                    "textRun": {"content": text + "\n", "textStyle": {}},
                }
            ],
            "paragraphStyle": {"namedStyleType": style},
        },
    }


class _FakeCompletions:
    def create(self, **kwargs):
        payload = json.loads(kwargs["messages"][1]["content"])
        translations = [
            {"key": item["key"], "translated_text": f"คำแปล {item['key']}"}
            for item in payload["items"]
        ]
        message = SimpleNamespace(content=json.dumps({"translations": translations}))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_generate_translations_populates_only_required_parts_and_statuses():
    doc = {
        "documentId": "copy",
        "title": "Test",
        "body": {
            "content": [
                _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
                _paragraph("BACKSTORY", 30),
                _paragraph("Story text.", 50),
                _paragraph("PREPARE", 80),
                _paragraph("Removed text.", 100),
            ]
        },
        "lists": {},
    }
    source = build_manifest(doc)
    client = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))

    completed = generate_translations(source, client=client, model="test", max_source_chars=20)

    required = [
        part
        for unit in completed["units"]
        for part in unit["translation_parts"]
        if part["recommended_action"] in {"translate", "localize", "bilingual"}
    ]
    removed = next(unit for unit in completed["units"] if unit["role"] == "prepare_content")
    assert all(part["translated_text"].startswith("คำแปล ") for part in required)
    assert removed["translation_parts"][0]["translated_text"] is None
    assert removed["translation"]["status"] == "not_required"

from copy import deepcopy
import json
from pathlib import Path

from app.tools.speaking_coach_importer import import_data, prepare_import


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict:
    return {
        "schema_version": "speaking-coach-parser-v1",
        "document": {"document_id": "doc-1", "title": "Speaking"},
        "issues": [],
        "lessons": [
            {
                "source_key": "lesson-key",
                "lesson_external_id": "4.1",
                "sort_order": 1,
                "practice_sets": [
                    {
                        "source_key": "practice-key",
                        "lesson_source_key": "lesson-key",
                        "practice_type": "translation",
                        "source_practice_type": "translate",
                        "sort_order": 1,
                        "focus": "Accept natural translations.",
                        "tip": {"en": None, "th": None},
                        "source": {
                            "document_id": "doc-1",
                            "tab_id": "tab-1",
                            "tab_title": "Tab 1",
                            "tab_order": 1,
                            "paragraph_index": 2,
                        },
                        "questions": [
                            {
                                "source_key": "question-key",
                                "practice_set_source_key": "practice-key",
                                "source_number": "1",
                                "sort_order": 1,
                                "prompt": {"en": None, "th": "ฉันเหนื่อย"},
                                "target_answers": ["I'm tired."],
                                "examples": [],
                                "source": {"paragraph_index": 5},
                            }
                        ],
                    }
                ],
            }
        ],
    }


class _Response:
    def __init__(self, data):
        self.data = data


class _LessonQuery:
    def __init__(self, client):
        self.client = client

    def select(self, _columns):
        return self

    def in_(self, column, values):
        assert column == "lesson_external_id"
        self.client.looked_up = list(values)
        return self

    def execute(self):
        return _Response(
            [
                {"id": "lesson-uuid", "lesson_external_id": external_id}
                for external_id in self.client.looked_up
            ]
        )


class _DryRunClient:
    def __init__(self):
        self.looked_up = []
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        assert name == "lessons"
        return _LessonQuery(self)


def test_prepares_current_parser_output() -> None:
    payload = json.loads(
        (BACKEND_ROOT / "data" / "speaking_coach.json").read_text(encoding="utf-8")
    )

    data, errors = prepare_import(payload)

    assert errors == []
    assert data is not None
    assert data.lesson_external_ids == ["4.1", "4.9"]
    assert len(data.practice_sets) == 4
    assert len(data.questions) == 13
    assert len(data.practice_sets[0]["content_hash"]) == 64
    assert len(data.questions[0]["content_hash"]) == 64
    assert data.questions[0]["focus_items"] == [
        {
            "priority": 1,
            "instruction": data.questions[0]["focus"],
        }
    ]
    questions_by_lesson = {
        lesson_id: [
            row["prompt_audio_key"]
            for row in data.questions
            if row["_practice_set_source_key"]
            in {
                practice["source_key"]
                for practice in data.practice_sets
                if practice["_lesson_external_id"] == lesson_id
            }
        ]
        for lesson_id in data.lesson_external_ids
    }
    assert questions_by_lesson["4.1"] == [
        *(f"4.1_speaking_{position}.mp3" for position in range(1, 7))
    ]
    assert any(key is None for key in questions_by_lesson["4.9"])

    practice_type_by_source_key = {
        row["source_key"]: row["practice_type"] for row in data.practice_sets
    }
    for question in data.questions:
        practice_type = practice_type_by_source_key[
            question["_practice_set_source_key"]
        ]
        if practice_type == "translation":
            assert question["prompt_audio_key"] is None
        else:
            assert question["prompt_audio_key"] is not None


def test_refuses_parser_errors() -> None:
    payload = _payload()
    payload["issues"] = [{"severity": "error", "message": "bad source"}]

    data, errors = prepare_import(payload)

    assert data is None
    assert any("Parser output contains" in error for error in errors)


def test_rejects_question_with_wrong_parent() -> None:
    payload = _payload()
    question = payload["lessons"][0]["practice_sets"][0]["questions"][0]
    question["practice_set_source_key"] = "some-other-practice"

    data, errors = prepare_import(payload)

    assert data is None
    assert any("containing practice set" in error for error in errors)


def test_question_edit_changes_question_and_parent_hashes() -> None:
    original, original_errors = prepare_import(_payload())
    changed_payload = deepcopy(_payload())
    changed_payload["lessons"][0]["practice_sets"][0]["questions"][0][
        "target_answers"
    ].append("I feel tired.")
    changed, changed_errors = prepare_import(changed_payload)

    assert original_errors == []
    assert changed_errors == []
    assert original is not None and changed is not None
    assert original.questions[0]["content_hash"] != changed.questions[0]["content_hash"]
    assert (
        original.practice_sets[0]["content_hash"]
        != changed.practice_sets[0]["content_hash"]
    )


def test_question_focus_is_imported_and_changes_content_hashes() -> None:
    payload = _payload()
    payload["schema_version"] = "speaking-coach-parser-v2"
    practice = payload["lessons"][0]["practice_sets"][0]
    practice["focus"] = None
    practice["questions"][0]["focus"] = "Require a natural translation."

    original, original_errors = prepare_import(payload)
    changed_payload = deepcopy(payload)
    changed_payload["lessons"][0]["practice_sets"][0]["questions"][0][
        "focus"
    ] = "Require the negation marker."
    changed, changed_errors = prepare_import(changed_payload)

    assert original_errors == []
    assert changed_errors == []
    assert original is not None and changed is not None
    assert original.questions[0]["focus"] == "Require a natural translation."
    assert original.questions[0]["focus_items"] == [
        {"priority": 1, "instruction": "Require a natural translation."}
    ]
    assert original.practice_sets[0]["focus"] == "Require a natural translation."
    assert original.questions[0]["content_hash"] != changed.questions[0]["content_hash"]
    assert original.practice_sets[0]["content_hash"] != changed.practice_sets[0]["content_hash"]


def test_v3_focus_items_are_imported_and_change_content_hashes() -> None:
    payload = _payload()
    payload["schema_version"] = "speaking-coach-parser-v3"
    practice = payload["lessons"][0]["practice_sets"][0]
    question = practice["questions"][0]
    question["focus"] = (
        "[P1] Preserve the meaning.\n"
        "[P1] Include the required negation.\n"
        "[P2] Use natural English."
    )
    question["focus_items"] = [
        {"priority": 1, "instruction": "Preserve the meaning."},
        {"priority": 1, "instruction": "Include the required negation."},
        {"priority": 2, "instruction": "Use natural English."},
    ]

    original, original_errors = prepare_import(payload)
    priority_changed_payload = deepcopy(payload)
    priority_changed_payload["lessons"][0]["practice_sets"][0]["questions"][0][
        "focus_items"
    ][1]["priority"] = 2
    priority_changed, priority_changed_errors = prepare_import(
        priority_changed_payload
    )
    order_changed_payload = deepcopy(payload)
    order_changed_items = order_changed_payload["lessons"][0]["practice_sets"][0][
        "questions"
    ][0]["focus_items"]
    order_changed_items[0], order_changed_items[1] = (
        order_changed_items[1],
        order_changed_items[0],
    )
    order_changed, order_changed_errors = prepare_import(order_changed_payload)

    assert original_errors == []
    assert priority_changed_errors == []
    assert order_changed_errors == []
    assert original is not None
    assert priority_changed is not None
    assert order_changed is not None
    assert original.questions[0]["focus_items"] == question["focus_items"]
    assert (
        original.questions[0]["content_hash"]
        != priority_changed.questions[0]["content_hash"]
    )
    assert (
        original.questions[0]["content_hash"]
        != order_changed.questions[0]["content_hash"]
    )
    assert (
        original.practice_sets[0]["content_hash"]
        != priority_changed.practice_sets[0]["content_hash"]
    )
    assert (
        original.practice_sets[0]["content_hash"]
        != order_changed.practice_sets[0]["content_hash"]
    )


def test_v3_rejects_missing_empty_or_invalid_focus_items() -> None:
    cases = [
        (None, "focus_items must be an array"),
        ([], "focus_items must contain at least one focus item"),
        (
            [{"priority": 4, "instruction": "Check this."}],
            "priority must be the integer 1, 2, or 3",
        ),
        (
            [{"priority": True, "instruction": "Check this."}],
            "priority must be the integer 1, 2, or 3",
        ),
        (
            [{"priority": 1, "instruction": "   "}],
            "instruction must be a non-empty string",
        ),
    ]

    for focus_items, expected_error in cases:
        payload = _payload()
        payload["schema_version"] = "speaking-coach-parser-v3"
        question = payload["lessons"][0]["practice_sets"][0]["questions"][0]
        question["focus"] = "[P1] Check this."
        if focus_items is not None:
            question["focus_items"] = focus_items

        data, errors = prepare_import(payload)

        assert data is None
        assert any(expected_error in error for error in errors)


def test_dry_run_only_resolves_lessons_and_never_writes() -> None:
    data, errors = prepare_import(_payload())
    assert errors == []
    assert data is not None
    client = _DryRunClient()

    summary = import_data(data, client=client)

    assert client.tables == ["lessons"]
    assert client.looked_up == ["4.1"]
    assert summary == {
        "lessons": 1,
        "practice_sets": 1,
        "questions": 1,
        "deactivated_practice_sets": 0,
        "deactivated_questions": 0,
    }

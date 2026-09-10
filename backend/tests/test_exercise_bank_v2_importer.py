from copy import deepcopy

from app.tools.exercise_bank_v2_importer import (
    import_data,
    prepare_import,
    prepare_thai_import,
)


def _payload():
    return {
        "document": {"document_id": "doc-1"},
        "issues": [],
        "topics": [{
            "source_key": "topic-key",
            "source_document_id": "doc-1",
            "source_tab_id": "tab-1",
            "source_tab_title": "Tab",
            "source_tab_order": 1,
            "topic": "To be",
            "display_title": "Pailin is hungry",
            "category": "verbs",
            "sub_category": None,
            "lesson_external_id": "1.6",
            "sort_order": 1,
        }],
        "exercises": [{
            "source_key": "exercise-key",
            "topic_source_key": "topic-key",
            "difficulty": None,
            "exercise_type": "fill_blank",
            "display_type": "Fill in the blank",
            "prompt": "Choose a word.",
            "keywords": None,
            "source": {"exercise_order": 1},
            "questions": [{
                "source_key": "question-key",
                "exercise_source_key": "exercise-key",
                "source_number": "1",
                "is_example": False,
                "sort_order": 1,
                "content": {"text": "I ___ here.", "accepted_answers": ["am"]},
            }],
        }],
    }


def test_prepare_import_flattens_questions_and_preserves_null_optionals():
    data, errors = prepare_import(_payload())
    assert errors == []
    assert data is not None
    assert data.topics[0]["sub_category"] is None
    assert data.exercises[0]["difficulty"] is None
    assert data.exercises[0]["_topic_source_key"] == "topic-key"
    assert data.questions[0]["_exercise_source_key"] == "exercise-key"
    assert data.questions[0]["content"]["accepted_answers"] == ["am"]


def test_prepare_import_refuses_parser_errors():
    payload = _payload()
    payload["issues"] = [{"severity": "error", "message": "bad source"}]
    data, errors = prepare_import(payload)
    assert data is None
    assert any("Parser output contains" in error for error in errors)


def test_prepare_import_rejects_unknown_parent():
    payload = _payload()
    payload["exercises"][0]["topic_source_key"] = "missing"
    data, errors = prepare_import(payload)
    assert data is None
    assert any("unknown topic_source_key" in error for error in errors)


def test_prepare_import_rejects_duplicate_question_keys():
    payload = _payload()
    duplicate = deepcopy(payload["exercises"][0]["questions"][0])
    duplicate["source_number"] = "2"
    payload["exercises"][0]["questions"].append(duplicate)
    data, errors = prepare_import(payload)
    assert data is None
    assert any("Duplicate question source_key" in error for error in errors)


def test_prepare_thai_import_maps_to_english_source_keys():
    thai_payload = [{
        "category": "verbs",
        "section": {
            "title_en": "To be",
            "title_th": "คำกริยา to be",
            "description": "",
        },
        "exercises": [{
            "kind": "fill_blank",
            "title": {
                "en": "FILL IN THE BLANK",
                "th": "เติมคำในช่องว่าง",
            },
            "prompt": {"en": "", "th": "เลือกคำที่ถูกต้อง"},
            "items": [],
            "items_th": [{
                "number": "1",
                "text": "I ___ here.\nฉันอยู่ที่นี่",
                "answer": "am",
            }],
        }],
    }]

    data, errors = prepare_thai_import(thai_payload, _payload())

    assert errors == []
    assert data is not None
    assert data.unmatched_thai == []
    assert data.unmatched_english == []
    assert data.topics == [{
        "source_key": "topic-key",
        "topic_th": "คำกริยา to be",
        "display_title_th": "คำกริยา to be",
    }]
    assert data.exercises[0]["source_key"] == "exercise-key"
    assert data.exercises[0]["prompt_th"] == "เลือกคำที่ถูกต้อง"
    assert data.questions == [{
        "source_key": "question-key",
        "content_th": {"text": "I ___ here.\nฉันอยู่ที่นี่"},
    }]


def test_prepare_thai_import_skips_extra_examples():
    thai_payload = [{
        "category": "verbs",
        "section": {"title_en": "To be", "title_th": "คำกริยา to be"},
        "exercises": [{
            "kind": "fill_blank",
            "title": {"en": "FILL IN THE BLANK", "th": "เติมคำในช่องว่าง"},
            "prompt": {"th": "เลือกคำที่ถูกต้อง"},
            "items_th": [
                {"number": "example", "text": "She ___ here.\nเธออยู่ที่นี่", "answer": "is"},
                {"number": "1", "text": "I ___ here.\nฉันอยู่ที่นี่", "answer": "am"},
            ],
        }],
    }]

    data, errors = prepare_thai_import(thai_payload, _payload())

    assert errors == []
    assert data is not None
    assert len(data.skipped_thai_examples) == 1
    assert data.unmatched_thai == []
    assert data.unmatched_english == []


def test_english_dry_run_summary_remains_unchanged():
    data, errors = prepare_import(_payload())
    assert errors == []
    assert data is not None

    assert import_data(data, dry_run=True) == {
        "topics": 1,
        "exercises": 1,
        "questions": 1,
        "deactivated": 0,
    }

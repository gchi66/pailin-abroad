from copy import deepcopy

from app.tools.exercise_bank_v2_parser import parse_document
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


def test_parser_handles_soft_break_schema_and_title_prompt_fallback():
    soft_break_source = (
        "TOPIC: Test topic\u000b"
        "DISPLAY_TITLE: A useful example\u000b"
        "CATEGORY: grammar\u000b"
        "LESSON: 1.1\u000b"
        "TYPE: multiple_choice\u000b"
        "TITLE: Choose the correct form\u000b"
        "DISPLAY_TYPE: Choose\u000b"
        "QUESTION: 1\u000b"
        "TEXT: Pick one.\u000b"
        "OPTIONS:\u000bA. First\u000bB. Second\u000bANSWER: B\n"
    )
    document = {
        "documentId": "doc-1",
        "title": "Exercise Bank",
        "body": {
            "content": [{
                "paragraph": {
                    "elements": [{
                        "textRun": {"content": soft_break_source, "textStyle": {}}
                    }]
                }
            }]
        },
    }

    parsed = parse_document(document)

    assert parsed["summary"]["error_count"] == 0
    [exercise] = parsed["exercises"]
    assert exercise["title"] == "Choose the correct form"
    assert exercise["prompt"] == "Choose the correct form"
    assert exercise["questions"][0]["content"]["correct_option"] == "B"
    assert "prompt_fallback_from_title" in {
        issue["code"] for issue in parsed["issues"]
    }


def test_parser_normalizes_repeated_topic_metadata_within_a_tab():
    lines = [
        "TOPIC: Canonical topic",
        "DISPLAY_TITLE: Example",
        "CATEGORY: grammar",
        "LESSON: 1.1",
        "TYPE: fill_blank",
        "DISPLAY_TYPE: Fill",
        "PROMPT: Fill it.",
        "ITEM: 1",
        "TEXT: ____",
        "ANSWER: first",
        "TOPIC: Alternate punctuation: topic",
        "TYPE: fill_blank",
        "DISPLAY_TYPE: Fill",
        "PROMPT: Fill it.",
        "ITEM: 1",
        "TEXT: ____",
        "ANSWER: second",
    ]
    document = {
        "documentId": "doc-1",
        "title": "Exercise Bank",
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{
                            "textRun": {"content": f"{line}\n", "textStyle": {}}
                        }]
                    }
                }
                for line in lines
            ]
        },
    }

    parsed = parse_document(document)

    assert parsed["summary"]["error_count"] == 0
    assert [exercise["topic"] for exercise in parsed["exercises"]] == [
        "Canonical topic",
        "Canonical topic",
    ]
    assert "normalized_topic_metadata" in {
        issue["code"] for issue in parsed["issues"]
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
    assert data.questions[0]["practice_order"] == 1


def test_prepare_import_assigns_stable_topic_wide_practice_order_excluding_examples():
    payload = _payload()
    first_exercise = payload["exercises"][0]
    example = deepcopy(first_exercise["questions"][0])
    example.update({"source_key": "example-key", "source_number": "Example", "is_example": True})
    first_exercise["questions"].append(example)

    second_exercise = deepcopy(first_exercise)
    second_exercise.update({
        "source_key": "exercise-key-2",
        "exercise_type": "multiple_choice",
        "source": {"exercise_order": 2},
    })
    second_exercise["questions"] = []
    for number in range(2, 5):
        question = deepcopy(first_exercise["questions"][0])
        question.update({
            "source_key": f"question-key-{number}",
            "exercise_source_key": "exercise-key-2",
            "source_number": str(number),
            "sort_order": number,
        })
        second_exercise["questions"].append(question)
    payload["exercises"].append(second_exercise)

    first, first_errors = prepare_import(deepcopy(payload))
    second, second_errors = prepare_import(deepcopy(payload))

    assert first_errors == second_errors == []
    assert first is not None and second is not None
    first_orders = {row["source_key"]: row["practice_order"] for row in first.questions}
    second_orders = {row["source_key"]: row["practice_order"] for row in second.questions}
    assert first_orders == second_orders
    assert first_orders["example-key"] is None
    assert sorted(order for order in first_orders.values() if order is not None) == [1, 2, 3, 4]


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


def test_prepare_thai_import_aligns_v2_parser_output_by_document_order():
    english_payload = _payload()
    thai_payload = deepcopy(english_payload)
    thai_payload["document"]["document_id"] = "doc-th"
    thai_payload["topics"][0].update({
        "source_key": "topic-key-th",
        "source_document_id": "doc-th",
    })
    thai_payload["exercises"][0].update({
        "source_key": "exercise-key-th",
        "topic_source_key": "topic-key-th",
        "prompt": "เลือกคำที่ถูกต้อง",
        "source": {"exercise_order": 1},
    })
    thai_payload["exercises"][0]["questions"][0].update({
        "source_key": "question-key-th",
        "exercise_source_key": "exercise-key-th",
        "content": {
            "text": "I ___ here.\nฉันอยู่ที่นี่",
            "accepted_answers": ["am"],
        },
    })

    data, errors = prepare_thai_import(thai_payload, english_payload)

    assert errors == []
    assert data is not None
    assert data.topics == []
    assert data.exercises == [{
        "source_key": "exercise-key",
        "display_type_th": "🧩 เติมคำในช่องว่าง",
        "prompt_th": "เลือกคำที่ถูกต้อง",
    }]
    assert data.questions == [{
        "source_key": "question-key",
        "content_th": {"text": "I ___ here.\nฉันอยู่ที่นี่"},
    }]
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

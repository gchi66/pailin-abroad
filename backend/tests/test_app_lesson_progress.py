from app.app_lesson_progress import _build_app_lesson_expectations_from_rows


def _source_rows(conversation_audio_url=None):
    return {
        "lessons": [
            {
                "id": "lesson-1",
                "conversation_audio_url": conversation_audio_url,
            }
        ],
        "sections": [
            {
                "lesson_id": "lesson-1",
                "id": "prepare-1",
                "type": "prepare",
                "sort_order": 1,
                "content_jsonb": [],
                "content_jsonb_th": [],
            }
        ],
        "transcript": [],
        "questions": [],
        "exercises": [],
        "lesson_phrases": [],
        "phrases": [],
    }


def test_listen_is_expected_when_conversation_audio_exists():
    expectation = _build_app_lesson_expectations_from_rows(
        ["lesson-1"],
        _source_rows("conversations/lesson-1.mp3"),
    )["lesson-1"]

    assert expectation["unit_keys"] == ["app:page:prepare", "app:page:listen"]


def test_listen_is_not_expected_without_conversation_audio():
    expectation = _build_app_lesson_expectations_from_rows(
        ["lesson-1"],
        _source_rows("  "),
    )["lesson-1"]

    assert expectation["unit_keys"] == ["app:page:prepare"]


def test_extra_practice_is_optional_and_excluded_from_required_units():
    source_rows = _source_rows()
    source_rows["exercises"] = [
        {
            "lesson_id": "lesson-1",
            "id": "core-1",
            "title": "Core",
            "sort_order": 1,
            "practice_priority": "core",
        },
        {
            "lesson_id": "lesson-1",
            "id": "extra-1",
            "title": "Extra",
            "sort_order": 2,
            "practice_priority": "extra",
        },
    ]

    expectation = _build_app_lesson_expectations_from_rows(
        ["lesson-1"],
        source_rows,
    )["lesson-1"]

    assert "app:page:practice" in expectation["unit_keys"]
    assert "app:exercise:core-1" in expectation["unit_keys"]
    assert "app:exercise:extra-1" not in expectation["unit_keys"]

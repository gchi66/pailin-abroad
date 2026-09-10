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

import json
from pathlib import Path

from app.tools.speaking_coach_parser import parse_document


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _paragraph(text: str) -> dict:
    return {
        "paragraph": {
            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
            "elements": [{"textRun": {"content": f"{text}\n"}}],
        }
    }


def _legacy_document(*lines: str) -> dict:
    return {
        "documentId": "test-speaking-document",
        "title": "Speaking parser test",
        "body": {"content": [_paragraph(line) for line in lines]},
    }


def _issue_codes(result: dict, severity: str) -> list[str]:
    return [
        issue["code"]
        for issue in result["issues"]
        if issue["severity"] == severity
    ]


def test_parses_saved_speaking_coach_document() -> None:
    raw_path = BACKEND_ROOT / "data" / "speaking_coach_raw.json"
    document = json.loads(raw_path.read_text(encoding="utf-8"))

    result = parse_document(document)

    assert result["summary"] == {
        "lesson_count": 2,
        "practice_set_count": 4,
        "question_count": 13,
        "error_count": 0,
        "warning_count": 1,
        "practice_types": {
            "open": 1,
            "pronunciation": 2,
            "translation": 1,
        },
    }
    assert _issue_codes(result, "warning") == ["duplicate_focus_prefix"]

    lesson_41 = result["lessons"][0]
    assert lesson_41["lesson_external_id"] == "4.1"
    pronunciation, open_practice = lesson_41["practice_sets"]
    assert "1. Structure Check:" in pronunciation["focus"]
    assert pronunciation["questions"][0]["prompt"] == {
        "en": "I’m eating lunch.",
        "th": "ฉันกำลังกินข้าวเที่ยงอยู่",
    }
    assert open_practice["tip"] == {
        "en": "Use present continuous tense in your answer",
        "th": "ใช้ present continuous tense ในคำตอบ",
    }

    translation = result["lessons"][1]["practice_sets"][1]
    assert translation["practice_type"] == "translation"
    assert translation["questions"][0]["target_answers"] == [
        "I have a stomach ache.",
        "My stomach hurts.",
    ]


def test_supports_multiline_focus_and_legacy_document_body() -> None:
    result = parse_document(
        _legacy_document(
            "LESSON: 1.1",
            "PRACTICE_TYPE: pronunciation",
            "FOCUS: Check the target sentence.",
            "1. Listen for the final consonant.",
            "2. Do not penalize the learner's accent.",
            "QUESTION: 1",
            "REPEAT_ENGLISH: I work late.",
            "REPEAT_THAI: ฉันทำงานดึก",
        )
    )

    assert result["summary"]["error_count"] == 0
    assert result["summary"]["warning_count"] == 0
    practice = result["lessons"][0]["practice_sets"][0]
    assert practice["focus"] == (
        "Check the target sentence.\n"
        "1. Listen for the final consonant.\n"
        "2. Do not penalize the learner's accent."
    )


def test_reports_missing_type_specific_fields() -> None:
    result = parse_document(
        _legacy_document(
            "LESSON: 1.1",
            "PRACTICE_TYPE: pronunciation",
            "FOCUS: Check pronunciation.",
            "QUESTION: 1",
            "REPEAT_ENGLISH: I work late.",
        )
    )

    assert result["summary"]["error_count"] == 1
    assert _issue_codes(result, "error") == ["missing_required_question_field"]
    assert result["issues"][0]["message"] == (
        "Question is missing required REPEAT_THAI."
    )


def test_accepts_dynamic_translation_answers_and_warns_on_number_gaps() -> None:
    result = parse_document(
        _legacy_document(
            "LESSON: 1.2",
            "PRACTICE_TYPE: translate",
            "FOCUS: Accept natural translations.",
            "QUESTION: 1",
            "TRANSLATE_THAI: ฉันเหนื่อย",
            "ANSWER_1: I’m tired.",
            "ANSWER_3: I feel tired.",
        )
    )

    question = result["lessons"][0]["practice_sets"][0]["questions"][0]
    assert question["target_answers"] == ["I’m tired.", "I feel tired."]
    assert _issue_codes(result, "warning") == [
        "non_contiguous_answer_numbers"
    ]


def test_reports_duplicate_question_numbers_within_a_practice_set() -> None:
    result = parse_document(
        _legacy_document(
            "LESSON: 1.3",
            "PRACTICE_TYPE: open",
            "FOCUS: Check relevance.",
            "QUESTION: 1",
            "OPEN_ENGLISH: What are you doing?",
            "OPEN_THAI: คุณกำลังทำอะไร",
            "EXAMPLE_ENGLISH: I’m working.",
            "EXAMPLE_THAI: ฉันกำลังทำงาน",
            "QUESTION: 1",
            "OPEN_ENGLISH: What are they doing?",
            "OPEN_THAI: พวกเขากำลังทำอะไร",
            "EXAMPLE_ENGLISH: They’re eating.",
            "EXAMPLE_THAI: พวกเขากำลังกินข้าว",
        )
    )

    assert "duplicate_question_number" in _issue_codes(result, "error")


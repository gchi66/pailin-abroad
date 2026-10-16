import copy

from app.tools.lesson_translation_manifest import build_manifest
from app.tools.lesson_translation_validator import validate_manifest


def _paragraph(text, start, *, style="NORMAL_TEXT", text_style=None):
    return {
        "startIndex": start,
        "endIndex": start + len(text) + 1,
        "paragraph": {
            "elements": [
                {
                    "startIndex": start,
                    "endIndex": start + len(text) + 1,
                    "textRun": {"content": text + "\n", "textStyle": text_style or {}},
                }
            ],
            "paragraphStyle": {"namedStyleType": style},
        },
    }


def _source_manifest():
    doc = {
        "documentId": "destination-copy",
        "title": "Test copy",
        "body": {
            "content": [
                _paragraph("LESSON 14.1: An odd title", 1, style="HEADING_3"),
                _paragraph("BACKSTORY", 40),
                _paragraph("An intentionally wierd backstory.", 55),
                _paragraph("CONVERSATION", 100),
                _paragraph("Pailin: Keep this. [audio:test_1]", 120),
                _paragraph("UNDERSTAND", 180, style="HEADING_4"),
                _paragraph("Use [verb] [X] in this structure.", 200),
                _paragraph("PREPARE", 250, style="HEADING_4"),
                _paragraph("Word: ความหมาย", 270),
            ]
        },
        "lists": {},
    }
    return build_manifest(doc)


def _complete(source):
    completed = copy.deepcopy(source)
    translations = {
        "lesson_heading": "ชื่อบทเรียนภาษาไทย",
        "lesson_backstory": "เรื่องราวเบื้องหลังภาษาไทย",
        "conversation_line": "ไพลิน: เก็บประโยคนี้ไว้",
        "instructional_explanation": "ใช้ [คำกริยา] [X] ในโครงสร้างนี้",
    }
    for unit in completed["units"]:
        if unit["role"] in translations:
            for part in unit["translation_parts"]:
                if part["recommended_action"] in {"translate", "localize", "bilingual"}:
                    part["translated_text"] = translations[unit["role"]]
            unit["translation"]["status"] = "complete"
    return completed


def test_valid_completed_manifest_passes_against_immutable_source():
    source = _source_manifest()
    completed = _complete(source)

    result = validate_manifest(completed, source_manifest=source)

    assert result["valid"] is True
    assert result["summary"]["error_count"] == 0
    assert result["summary"]["completed_translation_part_count"] == 4


def test_missing_translation_and_pending_status_fail():
    source = _source_manifest()
    completed = _complete(source)
    backstory = next(unit for unit in completed["units"] if unit["role"] == "lesson_backstory")
    backstory["translation_parts"][0]["translated_text"] = None
    backstory["translation"]["status"] = "pending"

    result = validate_manifest(completed, source_manifest=source)
    codes = [issue["code"] for issue in result["issues"]]

    assert result["valid"] is False
    assert "missing-translation" in codes


def test_mutating_authoritative_source_is_rejected():
    source = _source_manifest()
    completed = _complete(source)
    conversation = next(
        unit for unit in completed["units"] if unit["role"] == "conversation_line"
    )
    conversation["source_text"] = "Pailin: silently corrected source."

    result = validate_manifest(completed, source_manifest=source)

    assert any(issue["code"] == "source-unit-mutated" for issue in result["issues"])
    assert any(issue["code"] == "part-source-mismatch" for issue in result["issues"])


def test_reordering_units_or_mutating_manifest_metadata_is_rejected():
    source = _source_manifest()
    completed = _complete(source)
    completed["units"][0], completed["units"][1] = (
        completed["units"][1],
        completed["units"][0],
    )
    completed["summary"]["unit_count"] = 999

    result = validate_manifest(completed, source_manifest=source)
    codes = [issue["code"] for issue in result["issues"]]

    assert "unit-order-mutated" in codes
    assert "source-header-mutated" in codes


def test_localized_replacement_must_preserve_exact_tokens():
    source = _source_manifest()
    completed = _complete(source)
    explanation = next(
        unit for unit in completed["units"] if unit["role"] == "instructional_explanation"
    )
    explanation["translation_parts"][0]["translated_text"] = "ใช้คำกริยาในโครงสร้างนี้"

    result = validate_manifest(completed, source_manifest=source)

    assert any(issue["code"] == "protected-token-mismatch" for issue in result["issues"])


def test_bilingual_companion_cannot_duplicate_audio_or_complete_source():
    source = _source_manifest()
    completed = _complete(source)
    conversation = next(
        unit for unit in completed["units"] if unit["role"] == "conversation_line"
    )
    conversation["translation_parts"][0]["translated_text"] = (
        "Pailin: Keep this. [audio:test_1] ไพลิน: เก็บประโยคนี้ไว้"
    )

    result = validate_manifest(completed, source_manifest=source)
    codes = [issue["code"] for issue in result["issues"]]

    assert "duplicated-protected-token" in codes
    assert "source-duplicated-in-translation" in codes


def test_control_artifacts_and_non_thai_output_are_rejected():
    source = _source_manifest()
    completed = _complete(source)
    heading = next(unit for unit in completed["units"] if unit["role"] == "lesson_heading")
    translated_part = next(
        part
        for part in heading["translation_parts"]
        if part["recommended_action"] == "bilingual"
    )
    translated_part["translated_text"] = "```json translated_text: hello```"

    result = validate_manifest(completed, source_manifest=source)
    codes = [issue["code"] for issue in result["issues"]]

    assert "thai-script-missing" in codes
    assert "control-artifact" in codes


def test_localized_explanation_must_retain_quoted_english_teaching_text():
    doc = {
        "documentId": "destination-copy",
        "title": "Test copy",
        "body": {
            "content": [
                _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
                _paragraph("UNDERSTAND", 40, style="HEADING_4"),
                _paragraph("‘I mean’ gives you time to clarify.", 60),
            ]
        },
        "lists": {},
    }
    source = build_manifest(doc)
    completed = copy.deepcopy(source)
    explanation = next(
        unit for unit in completed["units"] if unit["role"] == "instructional_explanation"
    )
    assert explanation["translation_parts"][0]["protected_english_spans"] == ["I mean"]
    explanation["translation_parts"][0]["translated_text"] = "ช่วยให้คุณมีเวลาชี้แจง"
    explanation["translation"]["status"] = "complete"

    result = validate_manifest(completed, source_manifest=source)

    assert any(issue["code"] == "protected-english-missing" for issue in result["issues"])


def test_localized_lesson_focus_must_retain_named_english_target():
    doc = {
        "documentId": "destination-copy",
        "title": "Test copy",
        "body": {
            "content": [
                _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
                _paragraph("FOCUS", 40, style="HEADING_4"),
                _paragraph("How to use discourse markers", 60),
            ]
        },
        "lists": {},
    }
    source = build_manifest(doc)
    completed = copy.deepcopy(source)
    focus = next(unit for unit in completed["units"] if unit["role"] == "lesson_focus")
    assert focus["translation_parts"][0]["protected_english_spans"] == [
        "discourse markers"
    ]
    focus["translation_parts"][0]["translated_text"] = "วิธีใช้คำเชื่อมในบทสนทนา"
    focus["translation"]["status"] = "complete"

    result = validate_manifest(completed, source_manifest=source)

    assert any(issue["code"] == "protected-english-missing" for issue in result["issues"])


def test_reviewed_name_question_and_apply_response_rules_are_enforced():
    doc = {
        "documentId": "destination-copy",
        "title": "Test copy",
        "body": {
            "content": [
                _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
                _paragraph("CONVERSATION", 40, style="HEADING_4"),
                _paragraph("Luke: Are you ready? [audio:q_1]", 60),
                _paragraph("APPLY", 110, style="HEADING_4"),
                _paragraph("RESPONSE: I think so.", 130),
            ]
        },
        "lists": {},
    }
    source = build_manifest(doc)
    completed = copy.deepcopy(source)
    for unit in completed["units"]:
        for part in unit["translation_parts"]:
            if part["recommended_action"] not in {"translate", "localize", "bilingual"}:
                continue
            if unit["role"] == "lesson_heading":
                part["translated_text"] = "ทดสอบ"
            elif unit["role"] == "conversation_line":
                part["translated_text"] = "ลุค: พร้อมหรือยัง"
            elif unit["role"] == "apply_example_or_response":
                part["translated_text"] = "คำตอบ: ฉันคิดว่าใช่"
        if any(
            part["recommended_action"] in {"translate", "localize", "bilingual"}
            for part in unit["translation_parts"]
        ):
            unit["translation"]["status"] = "complete"

    result = validate_manifest(completed, source_manifest=source)
    codes = {issue["code"] for issue in result["issues"]}

    assert "luke-name-spelling" in codes
    assert "thai-question-mark-missing" in codes
    assert "duplicated-thai-response-label" in codes


def test_reviewed_quote_bracket_definition_and_blue_mapping_rules_are_enforced():
    blue = {
        "foregroundColor": {
            "color": {"rgbColor": {"red": 0.05, "green": 0.3, "blue": 0.8}}
        }
    }
    doc = {
        "documentId": "destination-copy",
        "title": "Test copy",
        "body": {
            "content": [
                _paragraph("LESSON 14.3: Test", 1, style="HEADING_3"),
                _paragraph("UNDERSTAND", 40, style="HEADING_4"),
                _paragraph("must be [adjective]", 60),
                _paragraph("PHRASES & VERBS", 100, style="HEADING_4"),
                _paragraph("Deal / agree [audio:phrases_verbs_deal_1]", 130),
                _paragraph(
                    "That sounds like a deal. [audio:deal_2]",
                    180,
                    text_style=blue,
                ),
            ]
        },
        "lists": {},
    }
    source = build_manifest(doc)
    completed = copy.deepcopy(source)
    for unit in completed["units"]:
        for part in unit["translation_parts"]:
            if part["recommended_action"] not in {"translate", "localize", "bilingual"}:
                continue
            if unit["role"] == "lesson_heading":
                part["translated_text"] = "ทดสอบ"
            elif unit["role"] == "instructional_explanation":
                part["translated_text"] = "must be [adjective] ใช้บอกสภาพ"
            elif unit["role"] == "phrase_term_audio":
                part["translated_text"] = "ตกลง / เห็นด้วย"
            elif unit["role"] == "phrase_example":
                part["translated_text"] = "ฟังดูเป็น 'deal' ที่ดี"
        if any(
            part["recommended_action"] in {"translate", "localize", "bilingual"}
            for part in unit["translation_parts"]
        ):
            unit["translation"]["status"] = "complete"

    result = validate_manifest(completed, source_manifest=source)
    codes = {issue["code"] for issue in result["issues"]}

    assert "bracket-word-not-translated" in codes
    assert "phrase-definition-slash" in codes
    assert "quoted-english-term" in codes
    assert "blue-thai-style-missing" in codes

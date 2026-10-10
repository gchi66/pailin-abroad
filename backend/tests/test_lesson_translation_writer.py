import copy

import pytest

from app.tools.lesson_translation_manifest import build_manifest
from app.tools.lesson_translation_writer import (
    _bilingual_prefix,
    _range_text,
    build_write_plan,
    verify_live_source,
)


def test_bulleted_phrase_companions_use_soft_break_and_term_gloss_is_inline():
    assert _bilingual_prefix(
        {"role": "phrase_example", "paragraph": {"bullet": {"listId": "list-1"}}},
        {"separator_after": ""},
    ) == "\u000b"
    assert _bilingual_prefix(
        {"role": "phrase_term_audio", "paragraph": {"bullet": {"listId": "list-1"}}},
        {"separator_after": ""},
    ) == " "


def _paragraph(text, start, *, style="NORMAL_TEXT"):
    return {
        "startIndex": start,
        "endIndex": start + len(text) + 1,
        "paragraph": {
            "elements": [
                {
                    "startIndex": start,
                    "endIndex": start + len(text) + 1,
                    "textRun": {
                        "content": text + "\n",
                        "textStyle": {"bold": style.startswith("HEADING")},
                    },
                }
            ],
            "paragraphStyle": {"namedStyleType": style},
        },
    }


def _source_and_completed():
    content = [
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("BACKSTORY", 30),
        _paragraph("Odd source text.", 50),
        _paragraph("CONVERSATION", 80),
        _paragraph("Pailin: Hello.", 100),
        _paragraph("PREPARE", 130),
        _paragraph("Removed.", 150),
        _paragraph("UNDERSTAND", 180),
        _paragraph("Use ‘I mean’ carefully.", 200),
    ]
    doc = {
        "documentId": "allowed-copy",
        "revisionId": "rev-1",
        "title": "Test",
        "body": {"content": content},
        "lists": {},
    }
    source = build_manifest(doc)
    completed = copy.deepcopy(source)
    translations = {
        "lesson_heading": "ทดสอบ",
        "lesson_backstory": "ข้อความต้นฉบับที่ตั้งใจเขียนแบบนี้",
        "conversation_line": "ไพลิน: สวัสดี",
        "instructional_explanation": "ใช้ I mean อย่างระมัดระวัง",
    }
    for unit in completed["units"]:
        for part in unit["translation_parts"]:
            if part["recommended_action"] in {"translate", "localize", "bilingual"}:
                part["translated_text"] = translations[unit["role"]]
        if any(
            part["recommended_action"] in {"translate", "localize", "bilingual"}
            for part in unit["translation_parts"]
        ):
            unit["translation"]["status"] = "complete"
    return doc, source, completed


def test_plan_is_reverse_ordered_and_has_expected_edit_types():
    _, source, completed = _source_and_completed()

    plan = build_write_plan(
        completed,
        source_manifest=source,
        destination_doc_id="allowed-copy",
        allowed_doc_id="allowed-copy",
    )

    starts = [group["start_index"] for group in plan["groups"]]
    assert starts == sorted(starts, reverse=True)
    assert plan["summary"] == {
        "edit_group_count": 5,
        "google_request_count": 11,
        "replacement_count": 2,
        "bilingual_insertion_count": 2,
        "prepare_removal_count": 1,
        "header_image_removal_count": 0,
    }
    heading = next(group for group in plan["groups"] if group["unit_id"] == "14.1.none.1")
    assert heading["requests"][0]["insertText"]["text"].startswith(" ")
    conversation = next(
        group for group in plan["groups"] if group["unit_id"] == "14.1.conversation.100"
    )
    assert conversation["requests"][0]["insertText"]["text"].startswith("\n")


def test_destination_must_match_allowlist_and_manifest_document():
    _, source, completed = _source_and_completed()
    with pytest.raises(ValueError, match="allowlist"):
        build_write_plan(
            completed,
            source_manifest=source,
            destination_doc_id="wrong",
            allowed_doc_id="allowed-copy",
        )
    with pytest.raises(ValueError, match="used to build"):
        build_write_plan(
            completed,
            source_manifest=source,
            destination_doc_id="other",
            allowed_doc_id="other",
        )


def test_live_source_range_verification_detects_document_drift():
    doc, _, completed = _source_and_completed()
    assert verify_live_source(
        doc, completed_manifest=completed, destination_doc_id="allowed-copy"
    ) == []
    changed = copy.deepcopy(doc)
    changed["body"]["content"][2]["paragraph"]["elements"][0]["textRun"][
        "content"
    ] = "Changed source.\n"

    errors = verify_live_source(
        changed, completed_manifest=completed, destination_doc_id="allowed-copy"
    )

    assert any("live source range differs" in error for error in errors)


def test_utf16_range_reader_handles_astral_characters():
    doc = {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {
                                "startIndex": 1,
                                "endIndex": 5,
                                "textRun": {"content": "A😀B"},
                            }
                        ]
                    }
                }
            ]
        }
    }
    assert _range_text(doc, 2, 4) == "😀"


def test_plan_applies_inline_style_to_translated_span_only():
    _, source, completed = _source_and_completed()
    unit = next(unit for unit in completed["units"] if unit["role"] == "lesson_backstory")
    part = unit["translation_parts"][0]
    anchor = "ต้นฉบับ"
    anchor_start = part["translated_text"].index(anchor)
    part["translated_style_spans"] = [
        {
            "start": anchor_start,
            "end": anchor_start + len(anchor),
            "text": anchor,
            "style": {"link": {"url": "https://pa.invalid/example"}},
        }
    ]

    plan = build_write_plan(
        completed,
        source_manifest=source,
        destination_doc_id="allowed-copy",
        allowed_doc_id="allowed-copy",
    )

    group = next(group for group in plan["groups"] if group["unit_id"] == unit["unit_id"])
    link_request = next(
        request["updateTextStyle"]
        for request in group["requests"]
        if request.get("updateTextStyle", {}).get("textStyle", {}).get("link")
    )
    translated_start = group["start_index"]
    assert link_request["range"] == {
        "startIndex": translated_start + len(part["translated_text"][:anchor_start]),
        "endIndex": translated_start + len(part["translated_text"][: anchor_start + len(anchor)]),
    }
    assert link_request["fields"] == "link"

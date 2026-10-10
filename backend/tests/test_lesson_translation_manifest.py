from app.tools.lesson_translation_manifest import (
    _protected_english_spans,
    build_manifest,
    render_report,
)


def _paragraph(text, start, *, style="NORMAL_TEXT", text_style=None):
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
                        "textStyle": text_style or {},
                    },
                }
            ],
            "paragraphStyle": {"namedStyleType": style},
        },
    }


def _doc(*content):
    return {
        "documentId": "destination-copy",
        "title": "L14 copy",
        "body": {"content": list(content)},
        "lists": {},
    }


def test_manifest_presumes_source_is_authoritative_and_classifies_core_sections():
    doc = _doc(
        _paragraph("LESSON 14.1: Deliberately wierd title", 1, style="HEADING_3"),
        _paragraph("CONVERSATION", 45, style="HEADING_4"),
        _paragraph("Pailin: I ain't changing this.", 60),
        _paragraph("PREPARE", 100, style="HEADING_4"),
        _paragraph("Odd: source [audio:keep_me]", 110),
        _paragraph("COMPREHENSION", 150, style="HEADING_4"),
        _paragraph("1. Why did she say that?", 170),
        _paragraph("A. Because she meant it.", 200),
        _paragraph("Answer key: A", 230),
    )

    parsed = [{"lesson": {"external_id": "14.1"}}]
    manifest = build_manifest(doc, parsed=parsed)
    units = {unit["source_text"]: unit for unit in manifest["units"]}

    title = units["LESSON 14.1: Deliberately wierd title"]
    assert title["source_authoritative"] is True
    assert title["recommended_action"] == "mixed"
    assert title["translation_parts"][0]["source_text"] == "LESSON 14.1: "
    assert title["translation_parts"][0]["recommended_action"] == "preserve"
    assert title["translation_parts"][1]["source_text"] == "Deliberately wierd title"
    assert title["translation_parts"][1]["start"] == len("LESSON 14.1: ")
    assert units["Pailin: I ain't changing this."]["recommended_action"] == "bilingual"
    assert units["PREPARE"]["recommended_action"] == "remove"
    assert units["Odd: source [audio:keep_me]"]["recommended_action"] == "remove"
    assert units["1. Why did she say that?"]["recommended_action"] == "translate"
    assert units["A. Because she meant it."]["recommended_action"] == "mixed"
    assert units["Answer key: A"]["recommended_action"] == "preserve"
    assert units["Odd: source [audio:keep_me]"]["protected_tokens"] == [
        {
            "kind": "audio",
            "text": "[audio:keep_me]",
            "start": 12,
            "end": 27,
            "preserve_exactly": True,
        }
    ]
    assert manifest["planned_removals"] == [
        {
            "lesson_id": "14.1",
            "section": "PREPARE",
            "start_index": 100,
            "end_index": 150,
            "start_body_index": 3,
            "end_body_index_exclusive": 5,
            "reason": "Thai lesson documents omit PREPARE in all paired Levels 1-13.",
        }
    ]
    assert not manifest["validation_issues"]
    assert manifest["write_readiness"]["ready"] is False
    assert any("revisionId" in blocker for blocker in manifest["write_readiness"]["blockers"])


def test_header_image_marker_is_removed_but_regular_image_marker_is_preserved():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("[header_img:pailin_chloe]", 30),
        _paragraph("FOCUS", 60, style="HEADING_4"),
        _paragraph("[img:keep_in_thai_doc]", 80),
    )

    manifest = build_manifest(doc)
    units = {unit["source_text"]: unit for unit in manifest["units"]}

    assert units["[header_img:pailin_chloe]"]["recommended_action"] == "remove"
    assert units["[img:keep_in_thai_doc]"]["recommended_action"] == "preserve"
    assert manifest["planned_removals"] == [
        {
            "lesson_id": "14.1",
            "section": "HEADER_IMAGE",
            "start_index": 30,
            "end_index": 56,
            "start_body_index": None,
            "end_body_index_exclusive": None,
            "reason": "Thai lesson documents omit the English document lesson banner marker.",
        }
    ]
    assert manifest["summary"]["header_image_removal_count"] == 1


def test_table_cell_units_inherit_current_lesson_and_section():
    table = {
        "startIndex": 100,
        "endIndex": 180,
        "table": {
            "tableRows": [
                {
                    "tableCells": [
                        {
                            "content": [
                                _paragraph("A. Keep the English", 110),
                            ]
                        }
                    ]
                }
            ]
        },
    }
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("COMPREHENSION", 30, style="HEADING_4"),
        table,
    )

    manifest = build_manifest(doc)
    option = next(unit for unit in manifest["units"] if unit["source_text"] == "A. Keep the English")
    assert option["lesson_id"] == "14.1"
    assert option["section"] == "COMPREHENSION"
    assert option["location"]["container"] == "table_cell"
    assert option["recommended_action"] == "mixed"


def test_comprehension_table_labels_are_structural():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("COMPREHENSION", 30, style="HEADING_4"),
        _paragraph("Prompt", 50),
        _paragraph("Options", 60),
    )

    manifest = build_manifest(doc)
    units = {unit["source_text"]: unit for unit in manifest["units"]}
    assert units["Prompt"]["recommended_action"] == "preserve"
    assert units["Options"]["recommended_action"] == "preserve"
    assert units["Prompt"]["role"] == "comprehension_table_label"
    assert not units["Options"]["warnings"]


def test_comprehension_option_translates_content_without_repeating_choice_label():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("COMPREHENSION", 30, style="HEADING_4"),
        _paragraph("A. An English choice", 50),
    )

    option = next(
        unit for unit in build_manifest(doc)["units"] if unit["role"] == "comprehension_option"
    )

    assert option["recommended_action"] == "mixed"
    assert [part["source_text"] for part in option["translation_parts"]] == [
        "A. ",
        "An English choice",
    ]
    assert [part["recommended_action"] for part in option["translation_parts"]] == [
        "preserve",
        "bilingual",
    ]


def test_blank_multiple_choice_options_stay_english_but_meaning_choices_are_bilingual():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("PRACTICE", 30, style="HEADING_4"),
        _paragraph("TYPE: multiple_choice", 50),
        _paragraph("QUESTION: 1", 80),
        _paragraph("TEXT: We ____ leave now.", 100),
        _paragraph("OPTIONS:", 130),
        _paragraph("A. should", 145),
        _paragraph("B. should to", 160),
        _paragraph("QUESTION: 2", 180),
        _paragraph("TEXT: What does it express?", 200),
        _paragraph("OPTIONS:", 235),
        _paragraph("A. giving advice", 250),
        _paragraph("B. stating a fact", 275),
    )

    options = [
        unit for unit in build_manifest(doc)["units"] if unit["role"] == "practice_option"
    ]

    assert [unit["recommended_action"] for unit in options] == [
        "preserve",
        "preserve",
        "mixed",
        "mixed",
    ]
    assert options[2]["translation_parts"][0]["source_text"] == "A. "
    assert options[2]["translation_parts"][1]["source_text"] == "giving advice"


def test_practice_text_translates_without_repeating_directive_or_dialogue_label():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("PRACTICE", 30, style="HEADING_4"),
        _paragraph("TEXT: A: Did you call?", 50),
        _paragraph("B: Not yet.", 80),
    )

    units = build_manifest(doc)["units"]
    text = next(unit for unit in units if unit["role"] == "practice_text")
    reply = next(unit for unit in units if unit["role"] == "practice_content")

    assert [part["source_text"] for part in text["translation_parts"]] == [
        "TEXT: A: ",
        "Did you call?",
    ]
    assert [part["source_text"] for part in reply["translation_parts"]] == [
        "B: ",
        "Not yet.",
    ]


def test_phrase_term_gloss_is_inserted_before_audio_token():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("PHRASES & VERBS", 30, style="HEADING_4"),
        _paragraph("Deal [audio:phrases_verbs_deal_1]", 50),
    )

    term = next(
        unit for unit in build_manifest(doc)["units"] if unit["role"] == "phrase_term_audio"
    )

    assert term["recommended_action"] == "mixed"
    assert [part["source_text"] for part in term["translation_parts"]] == [
        "Deal",
        " [audio:phrases_verbs_deal_1]",
    ]
    assert [part["recommended_action"] for part in term["translation_parts"]] == [
        "bilingual",
        "preserve",
    ]


def test_example_and_explanation_in_one_paragraph_receive_mixed_actions():
    text = (
        "Pailin: I mean, it was okay. [audio:14.1_understand_1]"
        "\u000b‘I mean’ softens the opinion."
    )
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("UNDERSTAND", 30, style="HEADING_4"),
        _paragraph(text, 50),
    )

    manifest = build_manifest(doc)
    unit = next(unit for unit in manifest["units"] if unit["source_text"] == text)
    assert unit["recommended_action"] == "mixed"
    assert unit["preserve_source_in_output"] is False
    assert [part["recommended_action"] for part in unit["translation_parts"]] == [
        "bilingual",
        "localize",
    ]
    assert unit["translation_parts"][0]["preserve_source_in_output"] is True
    assert unit["translation_parts"][1]["preserve_source_in_output"] is False


def test_two_speaker_lines_in_one_paragraph_remain_bilingual():
    text = "Luke: Are you free? [audio:test]\u000bPailin: Yes, I am."
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("UNDERSTAND", 30, style="HEADING_4"),
        _paragraph(text, 50),
    )

    manifest = build_manifest(doc)
    unit = next(unit for unit in manifest["units"] if unit["source_text"] == text)
    assert unit["recommended_action"] == "bilingual"
    assert all(
        part["recommended_action"] == "bilingual"
        for part in unit["translation_parts"]
    )


def test_equal_adjacent_text_styles_are_merged_without_changing_source():
    paragraph = {
        "startIndex": 50,
        "endIndex": 61,
        "paragraph": {
            "elements": [
                {
                    "startIndex": 50,
                    "endIndex": 55,
                    "textRun": {"content": "inten", "textStyle": {"bold": True}},
                },
                {
                    "startIndex": 55,
                    "endIndex": 61,
                    "textRun": {"content": "tion\n", "textStyle": {"bold": True}},
                },
            ],
            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
        },
    }
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("BACKSTORY", 30),
        paragraph,
    )

    manifest = build_manifest(doc)
    unit = next(unit for unit in manifest["units"] if unit["source_text"] == "intention")
    assert unit["style_segments"] == [
        {
            "text": "intention",
            "start_index": 50,
            "end_index": 60,
            "style": {"bold": True},
        }
    ]


def test_parsed_inventory_mismatch_is_a_validation_error_and_reported():
    doc = _doc(_paragraph("LESSON 14.1: Test", 1, style="HEADING_3"))
    manifest = build_manifest(doc, parsed=[{"lesson": {"external_id": "14.2"}}])

    assert manifest["summary"]["validation_issue_count"] == 1
    assert "Raw/parsed lesson IDs differ" in manifest["validation_issues"][0]
    assert "ERROR:" in render_report(manifest)


def test_plain_paragraph_mentioning_another_lesson_is_not_a_boundary():
    doc = _doc(
        _paragraph("LESSON 14.1: Test", 1, style="HEADING_3"),
        _paragraph("UNDERSTAND", 30, style="HEADING_4"),
        _paragraph("Lesson 14.11 will go more in-depth with this.", 50),
        _paragraph("LESSON 14.2: Next", 110, style="HEADING_3"),
    )
    parsed = [
        {"lesson": {"external_id": "14.1"}},
        {"lesson": {"external_id": "14.2"}},
    ]

    manifest = build_manifest(doc, parsed=parsed)
    mention = next(
        unit
        for unit in manifest["units"]
        if unit["source_text"] == "Lesson 14.11 will go more in-depth with this."
    )

    assert manifest["inventory"]["detected_lesson_ids"] == ["14.1", "14.2"]
    assert mention["lesson_id"] == "14.1"
    assert mention["recommended_action"] == "localize"
    assert not manifest["validation_issues"]


def test_protected_english_span_handles_curly_apostrophes_inside_quote():
    spans = _protected_english_spans(
        "It is like saying, ‘I’m not exaggerating.’",
        role="instructional_explanation",
        action="localize",
    )

    assert spans == ["I’m not exaggerating."]

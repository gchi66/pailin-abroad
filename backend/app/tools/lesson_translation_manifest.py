"""Build a read-only translation manifest from a raw Google Docs response.

This module does not call Google APIs and cannot modify a document. It turns a
saved ``documents.get`` response into stable translation units that retain Docs
indexes, inline styles, protected tokens, lesson/section context, and a
recommended localization action.

Example:

    python -m app.tools.lesson_translation_manifest \
      --raw data/level_14_translation_target.raw.json \
      --parsed data/level_14.json \
      --lesson 14.1 \
      --out data/level_14_translation_pilot_14_1.manifest.json \
      --report data/level_14_translation_pilot_14_1.report.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1

LESSON_RE = re.compile(r"^\s*LESSON\s+(\d+)\.(\d+)\b", re.IGNORECASE)
CHECKPOINT_RE = re.compile(r"^\s*CHECKPOINT\s+(\d+)\b", re.IGNORECASE)
LESSON_TITLE_PREFIX_RE = re.compile(
    r"^\s*(?:LESSON\s+\d+\.\d+|CHECKPOINT\s+\d+)\s*:\s*",
    re.IGNORECASE,
)
SPEAKER_RE = re.compile(r"^[^:\n]{1,50}:\s+\S")
QUESTION_RE = re.compile(r"^\s*\d+[.)]\s+\S")
OPTION_RE = re.compile(r"^\s*[A-Z][.)]\s+\S")
OPTION_PREFIX_RE = re.compile(r"^\s*[A-Z][.)]\s+")
PRACTICE_TEXT_PREFIX_RE = re.compile(r"^\s*TEXT\s*:\s*(?:[A-Z]\s*:\s*)?", re.IGNORECASE)
PRACTICE_SPEAKER_PREFIX_RE = re.compile(r"^\s*[A-Z]\s*:\s+")
PHRASE_TERM_AUDIO_RE = re.compile(
    r"^(?P<term>.*?)(?P<audio>\s+\[audio:phrases_verbs_[^\]]+_1\])$",
    re.IGNORECASE,
)
ANSWER_KEY_RE = re.compile(r"^\s*ANSWER\s+KEY\s*:", re.IGNORECASE)
DIRECTIVE_RE = re.compile(
    r"^\s*(TYPE|PRACTICE_PRIORITY|TITLE|PROMPT|PARAGRAPH|ITEM|QUESTION|"
    r"TEXT|STEM|CORRECT|ANSWER|DISPLAY_ANSWER|REVIEW_ANSWER|OPTIONS|"
    r"KEYWORDS|INPUTS|CHARACTERS)\s*:",
    re.IGNORECASE,
)
PRESERVE_DIRECTIVES = {
    "TYPE",
    "PRACTICE_PRIORITY",
    "ITEM",
    "QUESTION",
    "ANSWER",
    "DISPLAY_ANSWER",
    "REVIEW_ANSWER",
    "OPTIONS",
    "KEYWORDS",
    "INPUTS",
    "CHARACTERS",
}

SECTION_HEADERS = {
    "FOCUS",
    "BACKSTORY",
    "CONVERSATION",
    "PREPARE",
    "COMPREHENSION",
    "APPLY",
    "UNDERSTAND",
    "EXTRA TIPS",
    "COMMON MISTAKES",
    "PHRASES & VERBS",
    "CULTURE NOTE",
    "PRACTICE",
    "PINNED COMMENT",
    "TAGS",
}

TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("audio", re.compile(r"\[audio:\s*[^\]]+\]", re.IGNORECASE)),
    ("image", re.compile(r"\[img:\s*[^\]]+\]", re.IGNORECASE)),
    ("header_image", re.compile(r"\[header_img:\s*[^\]]+\]", re.IGNORECASE)),
    ("bracket_token", re.compile(r"\[[A-Za-z_][^\]\n]{0,100}\]")),
    ("blank", re.compile(r"_{2,}")),
    ("url", re.compile(r"https?://[^\s<>()]+")),
)


def _normalized_header(text: str) -> str:
    return " ".join(text.strip().rstrip(":").upper().split())


def _lesson_id(text: str) -> str | None:
    if match := LESSON_RE.match(text):
        return f"{int(match.group(1))}.{int(match.group(2))}"
    if match := CHECKPOINT_RE.match(text):
        return f"{int(match.group(1))}.chp"
    return None


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    return "".join(
        element.get("textRun", {}).get("content", "")
        for element in paragraph.get("elements", [])
    )


def _source_text(raw_text: str) -> str:
    # A terminal newline is the paragraph delimiter in the Docs model, not
    # authored paragraph text. Preserve all other whitespace byte-for-byte.
    return raw_text[:-1] if raw_text.endswith("\n") else raw_text


def _is_heading(paragraph: dict[str, Any]) -> bool:
    named_style = paragraph.get("paragraphStyle", {}).get("namedStyleType", "")
    return isinstance(named_style, str) and named_style.startswith("HEADING_")


def _style_key(style: dict[str, Any]) -> str:
    return json.dumps(style, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _style_segments(paragraph: dict[str, Any]) -> list[dict[str, Any]]:
    """Return semantic style segments while merging arbitrary equal run splits."""
    segments: list[dict[str, Any]] = []
    for element in paragraph.get("elements", []):
        text_run = element.get("textRun")
        if not text_run:
            continue
        text = text_run.get("content", "")
        start_index = element.get("startIndex")
        end_index = element.get("endIndex")
        style = text_run.get("textStyle", {})

        if text.endswith("\n"):
            text = text[:-1]
            if isinstance(end_index, int):
                end_index -= 1
        if not text:
            continue

        if (
            segments
            and _style_key(segments[-1]["style"]) == _style_key(style)
            and segments[-1].get("end_index") == start_index
        ):
            segments[-1]["text"] += text
            segments[-1]["end_index"] = end_index
            continue

        segments.append(
            {
                "text": text,
                "start_index": start_index,
                "end_index": end_index,
                "style": style,
            }
        )
    return segments


def _text_range(paragraph: dict[str, Any]) -> dict[str, int | None]:
    text_elements = [
        element
        for element in paragraph.get("elements", [])
        if element.get("textRun") is not None
    ]
    if not text_elements:
        return {"start_index": None, "end_index": None}

    start_index = text_elements[0].get("startIndex")
    last = text_elements[-1]
    end_index = last.get("endIndex")
    last_content = last.get("textRun", {}).get("content", "")
    if last_content.endswith("\n") and isinstance(end_index, int):
        end_index -= 1
    return {"start_index": start_index, "end_index": end_index}


def _protected_tokens(text: str) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = set()
    for kind, pattern in TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if span in occupied:
                continue
            occupied.add(span)
            tokens.append(
                {
                    "kind": kind,
                    "text": match.group(0),
                    "start": span[0],
                    "end": span[1],
                    "preserve_exactly": True,
                }
            )

    if directive := DIRECTIVE_RE.match(text):
        prefix_end = directive.end()
        tokens.append(
            {
                "kind": "parser_directive",
                "text": text[:prefix_end],
                "start": 0,
                "end": prefix_end,
                "preserve_exactly": True,
            }
        )

    return sorted(tokens, key=lambda token: (token["start"], token["end"], token["kind"]))


QUOTED_ENGLISH_PATTERNS = (
    # A right single quote is also used as an apostrophe. Treat it as part of
    # the quoted phrase when followed by an ASCII letter (for example, I'm).
    re.compile(r"‘(?=[^‘\n]*[A-Za-z])((?:[^’\n]|’(?=[A-Za-z]))+)’"),
    re.compile(r"“(?=[^“\n]*[A-Za-z])([^”\n]+)”"),
)
FOCUS_TARGET_RE = re.compile(r"^How to use\s+(.+?)\s*$", re.IGNORECASE)


def _protected_english_spans(text: str, *, role: str, action: str) -> list[str]:
    """Return high-confidence English teaching objects that must survive localization.

    This deliberately stays narrow. Existing Thai lessons consistently retain
    quoted English forms inside localized explanations, while ordinary prose is
    often freely reauthored. Lesson-focus text also names the teaching target in
    the stable ``How to use ...`` form.
    """
    if action != "localize":
        return []

    matches = [
        (match.start(), match.group(1))
        for pattern in QUOTED_ENGLISH_PATTERNS
        for match in pattern.finditer(text)
    ]
    spans = [span for _, span in sorted(matches)]
    if role == "lesson_focus" and (match := FOCUS_TARGET_RE.match(text)):
        spans.append(match.group(1))
    return list(dict.fromkeys(spans))


def _paragraph_metadata(paragraph: dict[str, Any]) -> dict[str, Any]:
    paragraph_style = paragraph.get("paragraphStyle", {})
    bullet = paragraph.get("bullet")
    return {
        "named_style": paragraph_style.get("namedStyleType"),
        "paragraph_style": paragraph_style,
        "bullet": bullet,
    }


def _classify(
    text: str,
    *,
    lesson_id: str | None,
    section: str | None,
    is_heading: bool,
) -> tuple[str, str, list[str]]:
    """Return ``(action, role, warnings)`` for one authored paragraph."""
    normalized = _normalized_header(text)
    warnings: list[str] = []

    if is_heading and _lesson_id(text):
        return "bilingual", "lesson_heading", warnings
    if normalized in SECTION_HEADERS:
        if normalized == "PREPARE":
            return "remove", "prepare_section_heading", warnings
        return "preserve", "section_heading", warnings
    if not lesson_id:
        return "preserve", "document_preamble", warnings
    if re.fullmatch(r"\[header_img:[^\]]+\]", text.strip(), re.IGNORECASE):
        return "remove", "lesson_banner_marker", warnings
    if re.fullmatch(r"\[img:[^\]]+\]", text.strip(), re.IGNORECASE):
        return "preserve", "asset_marker", warnings
    if section == "PREPARE":
        return "remove", "prepare_content", warnings
    if section == "FOCUS":
        return "localize", "lesson_focus", warnings
    if section == "BACKSTORY":
        return "translate", "lesson_backstory", warnings
    if section == "CONVERSATION":
        return "bilingual", "conversation_line", warnings

    if section == "COMPREHENSION":
        if normalized in {"PROMPT", "OPTIONS"}:
            return "preserve", "comprehension_table_label", warnings
        if ANSWER_KEY_RE.match(text):
            return "preserve", "comprehension_answer_key", warnings
        if OPTION_RE.match(text):
            return "bilingual", "comprehension_option", warnings
        if QUESTION_RE.match(text):
            return "translate", "comprehension_prompt", warnings
        warnings.append("Comprehension role inferred from surrounding structure; review classification.")
        return "translate", "comprehension_content", warnings

    if section == "APPLY":
        if SPEAKER_RE.match(text) or normalized.startswith("RESPONSE"):
            return "bilingual", "apply_example_or_response", warnings
        return "translate", "apply_instruction", warnings

    if section in {"UNDERSTAND", "EXTRA TIPS", "COMMON MISTAKES"}:
        if section == "COMMON MISTAKES":
            warnings.append("Source may contain intentional errors; preserve every English contrast exactly.")
        if is_heading:
            return "bilingual", "instructional_subheading", warnings
        if SPEAKER_RE.match(text) or "[audio:" in text.lower():
            return "bilingual", "instructional_example", warnings
        return "localize", "instructional_explanation", warnings

    if section == "PHRASES & VERBS":
        if is_heading:
            return "bilingual", "phrase_heading", warnings
        if PHRASE_TERM_AUDIO_RE.match(text):
            return "bilingual", "phrase_term_audio", warnings
        if SPEAKER_RE.match(text) or "[audio:" in text.lower():
            return "bilingual", "phrase_example", warnings
        return "localize", "phrase_explanation", warnings

    if section == "CULTURE NOTE":
        if is_heading:
            return "bilingual", "culture_subheading", warnings
        return "translate", "culture_explanation", warnings

    if section == "PRACTICE":
        directive = DIRECTIVE_RE.match(text)
        if directive:
            label = directive.group(1).upper()
            if label in PRESERVE_DIRECTIVES:
                return "preserve", f"practice_directive_{label.lower()}", warnings
            if label == "TITLE":
                return "bilingual", "practice_title", warnings
            if label in {"PROMPT", "PARAGRAPH"}:
                return "localize", f"practice_{label.lower()}", warnings
            if label in {"TEXT", "STEM", "CORRECT"}:
                return "bilingual", f"practice_{label.lower()}", warnings
        if OPTION_RE.match(text):
            return "bilingual", "practice_option", warnings
        return "bilingual", "practice_content", warnings

    if section == "PINNED COMMENT":
        return "translate", "pinned_comment", warnings
    if section == "TAGS":
        return "translate", "tags", warnings

    warnings.append("No section-specific rule matched; preserve until reviewed.")
    return "preserve", "unclassified", warnings


def _translation_parts(
    text: str,
    *,
    action: str,
    role: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Split mixed example/explanation paragraphs at authored soft breaks.

    Existing Thai documents often retain and translate an English example, but
    replace the explanation after a vertical-tab soft break with Thai. Keeping
    this distinction explicit prevents a writer from duplicating the English
    explanation merely because it shares a Docs paragraph with the example.
    """
    if role == "lesson_heading" and (match := LESSON_TITLE_PREFIX_RE.match(text)):
        prefix = text[: match.end()]
        title = text[match.end() :]
        if title:
            return "mixed", [
                {
                    "part_id": "p1",
                    "source_text": prefix,
                    "start": 0,
                    "end": len(prefix),
                    "separator_after": "",
                    "recommended_action": "preserve",
                    "preserve_source_in_output": True,
                    "protected_tokens": _protected_tokens(prefix),
                    "protected_english_spans": [],
                    "translated_text": None,
                },
                {
                    "part_id": "p2",
                    "source_text": title,
                    "start": match.end(),
                    "end": len(text),
                    "separator_after": "",
                    "recommended_action": action,
                    "preserve_source_in_output": True,
                    "protected_tokens": _protected_tokens(title),
                    "protected_english_spans": [],
                    "translated_text": None,
                }
            ]

    if role == "phrase_term_audio" and (match := PHRASE_TERM_AUDIO_RE.match(text)):
        term = match.group("term")
        audio = match.group("audio")
        return "mixed", [
            {
                "part_id": "p1",
                "source_text": term,
                "start": 0,
                "end": len(term),
                "separator_after": "",
                "recommended_action": "bilingual",
                "preserve_source_in_output": True,
                "protected_tokens": _protected_tokens(term),
                "protected_english_spans": [],
                "translated_text": None,
            },
            {
                "part_id": "p2",
                "source_text": audio,
                "start": len(term),
                "end": len(text),
                "separator_after": "",
                "recommended_action": "preserve",
                "preserve_source_in_output": True,
                "protected_tokens": _protected_tokens(audio),
                "protected_english_spans": [],
                "translated_text": None,
            },
        ]

    prefix_match = None
    if role in {"comprehension_option", "practice_option"}:
        prefix_match = OPTION_PREFIX_RE.match(text)
    elif role == "practice_text":
        prefix_match = PRACTICE_TEXT_PREFIX_RE.match(text)
    elif role == "practice_content":
        prefix_match = PRACTICE_SPEAKER_PREFIX_RE.match(text)
    if prefix_match and prefix_match.end() < len(text):
        prefix = text[: prefix_match.end()]
        content = text[prefix_match.end() :]
        return "mixed", [
            {
                "part_id": "p1",
                "source_text": prefix,
                "start": 0,
                "end": len(prefix),
                "separator_after": "",
                "recommended_action": "preserve",
                "preserve_source_in_output": True,
                "protected_tokens": _protected_tokens(prefix),
                "protected_english_spans": [],
                "translated_text": None,
            },
            {
                "part_id": "p2",
                "source_text": content,
                "start": prefix_match.end(),
                "end": len(text),
                "separator_after": "",
                "recommended_action": action,
                "preserve_source_in_output": action in {"preserve", "bilingual"},
                "protected_tokens": _protected_tokens(content),
                "protected_english_spans": _protected_english_spans(
                    content, role=role, action=action
                ),
                "translated_text": None,
            },
        ]

    raw_parts = text.split("\u000b")
    parts: list[dict[str, Any]] = []
    cursor = 0
    for index, part_text in enumerate(raw_parts):
        part_action = action
        if role in {"instructional_example", "phrase_example"} and len(raw_parts) > 1:
            if index == 0 or SPEAKER_RE.match(part_text) or "[audio:" in part_text.lower():
                part_action = "bilingual"
            else:
                part_action = "localize"

        parts.append(
            {
                "part_id": f"p{index + 1}",
                "source_text": part_text,
                "start": cursor,
                "end": cursor + len(part_text),
                "separator_after": "\u000b" if index < len(raw_parts) - 1 else "",
                "recommended_action": part_action,
                "preserve_source_in_output": part_action in {"preserve", "bilingual"},
                "protected_tokens": _protected_tokens(part_text),
                "protected_english_spans": _protected_english_spans(
                    part_text,
                    role=role,
                    action=part_action,
                ),
                "translated_text": None,
            }
        )
        cursor += len(part_text) + (1 if index < len(raw_parts) - 1 else 0)

    part_actions = {part["recommended_action"] for part in parts}
    unit_action = "mixed" if len(part_actions) > 1 else action
    return unit_action, parts


def _iter_table_paragraphs(
    table: dict[str, Any],
    *,
    base_path: str,
) -> Iterable[tuple[dict[str, Any], str, dict[str, int]]]:
    for row_index, row in enumerate(table.get("tableRows", [])):
        for cell_index, cell in enumerate(row.get("tableCells", [])):
            cell_path = f"{base_path}.rows[{row_index}].cells[{cell_index}]"
            for content_index, element in enumerate(cell.get("content", [])):
                path = f"{cell_path}.content[{content_index}]"
                if paragraph := element.get("paragraph"):
                    yield paragraph, path, {
                        "start_index": element.get("startIndex"),
                        "end_index": element.get("endIndex"),
                    }
                elif nested_table := element.get("table"):
                    yield from _iter_table_paragraphs(nested_table, base_path=f"{path}.table")


def _top_level_markers(doc: dict[str, Any]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    current_lesson: str | None = None
    for body_index, element in enumerate(doc.get("body", {}).get("content", [])):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _source_text(_paragraph_text(paragraph)).strip()
        if _is_heading(paragraph) and (new_lesson := _lesson_id(text)):
            current_lesson = new_lesson
            markers.append(
                {
                    "kind": "lesson",
                    "lesson_id": current_lesson,
                    "section": None,
                    "body_index": body_index,
                    "start_index": element.get("startIndex"),
                    "end_index": element.get("endIndex"),
                    "text": text,
                }
            )
            continue
        normalized = _normalized_header(text)
        if normalized in SECTION_HEADERS:
            markers.append(
                {
                    "kind": "section",
                    "lesson_id": current_lesson,
                    "section": normalized,
                    "body_index": body_index,
                    "start_index": element.get("startIndex"),
                    "end_index": element.get("endIndex"),
                    "text": text,
                }
            )
    return markers


def _prepare_removals(doc: dict[str, Any]) -> list[dict[str, Any]]:
    markers = _top_level_markers(doc)
    document_end = doc.get("body", {}).get("content", [{}])[-1].get("endIndex")
    removals: list[dict[str, Any]] = []
    for marker_index, marker in enumerate(markers):
        if marker.get("section") != "PREPARE":
            continue
        end_index = document_end
        end_body_index = None
        for next_marker in markers[marker_index + 1 :]:
            if next_marker.get("kind") in {"lesson", "section"}:
                end_index = next_marker.get("start_index")
                end_body_index = next_marker.get("body_index")
                break
        removals.append(
            {
                "lesson_id": marker.get("lesson_id"),
                "section": "PREPARE",
                "start_index": marker.get("start_index"),
                "end_index": end_index,
                "start_body_index": marker.get("body_index"),
                "end_body_index_exclusive": end_body_index,
                "reason": "Thai lesson documents omit PREPARE in all paired Levels 1-13.",
            }
        )
    return removals


def _header_image_removals(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    removals: list[dict[str, Any]] = []
    for unit in units:
        if unit.get("role") != "lesson_banner_marker":
            continue
        location = unit.get("location", {})
        start = location.get("element_start_index")
        end = location.get("element_end_index")
        if isinstance(start, int) and isinstance(end, int) and start < end:
            removals.append(
                {
                    "lesson_id": unit.get("lesson_id"),
                    "section": "HEADER_IMAGE",
                    "start_index": start,
                    "end_index": end,
                    "start_body_index": None,
                    "end_body_index_exclusive": None,
                    "reason": "Thai lesson documents omit the English document lesson banner marker.",
                }
            )
    return removals


def _apply_practice_option_policy(units: list[dict[str, Any]]) -> None:
    """Keep fill-in-the-blank answer choices English-only.

    Paired Thai documents translate the surrounding stem but retain the English
    choices when those choices are the language forms being tested. Meaning or
    interpretation choices can remain bilingual.
    """
    practice_type: str | None = None
    question_has_blank = False
    for unit in units:
        if unit.get("section") != "PRACTICE":
            continue
        source = unit.get("source_text", "")
        role = unit.get("role")
        if role == "practice_directive_type":
            practice_type = source.partition(":")[2].strip().lower()
            question_has_blank = False
        elif role == "practice_directive_question":
            question_has_blank = False
        elif role in {"practice_text", "practice_content", "practice_stem"}:
            question_has_blank = question_has_blank or bool(re.search(r"_{2,}", source))
        elif (
            role == "practice_option"
            and practice_type == "multiple_choice"
            and question_has_blank
        ):
            unit["recommended_action"] = "preserve"
            unit["preserve_source_in_output"] = True
            for part in unit.get("translation_parts", []):
                part["recommended_action"] = "preserve"
                part["preserve_source_in_output"] = True
                part["translated_text"] = None
            unit["translation"]["status"] = "not_required"


def _make_unit(
    paragraph: dict[str, Any],
    *,
    path: str,
    container: str,
    element_range: dict[str, int | None],
    lesson_id: str | None,
    section: str | None,
) -> dict[str, Any] | None:
    raw_text = _paragraph_text(paragraph)
    text = _source_text(raw_text)
    if not text.strip():
        return None

    heading = _is_heading(paragraph)
    action, role, warnings = _classify(
        text,
        lesson_id=lesson_id,
        section=section,
        is_heading=heading,
    )
    action, translation_parts = _translation_parts(text, action=action, role=role)
    text_range = _text_range(paragraph)
    stable_start = text_range.get("start_index") or element_range.get("start_index") or 0
    lesson_part = lesson_id or "preamble"
    section_part = (section or "none").lower().replace(" ", "_").replace("&", "and")
    unit_id = f"{lesson_part}.{section_part}.{stable_start}"

    return {
        "unit_id": unit_id,
        "lesson_id": lesson_id,
        "section": section,
        "role": role,
        "recommended_action": action,
        "source_text": text,
        "source_authoritative": True,
        "preserve_source_in_output": action in {"preserve", "bilingual"},
        "location": {
            "container": container,
            "path": path,
            "element_start_index": element_range.get("start_index"),
            "element_end_index": element_range.get("end_index"),
            **text_range,
        },
        "paragraph": _paragraph_metadata(paragraph),
        "style_segments": _style_segments(paragraph),
        "protected_tokens": _protected_tokens(text),
        "translation_parts": translation_parts,
        "warnings": warnings,
        "translation": {
            "status": "not_required" if action in {"preserve", "remove"} else "pending"
        },
    }


def _parsed_lesson_ids(parsed: Any) -> list[str]:
    if not isinstance(parsed, list):
        return []
    lesson_ids: list[str] = []
    for lesson in parsed:
        if not isinstance(lesson, dict):
            continue
        external_id = lesson.get("lesson", {}).get("external_id")
        if isinstance(external_id, str):
            lesson_ids.append(external_id)
    return lesson_ids


def build_manifest(
    doc: dict[str, Any],
    *,
    raw_sha256: str | None = None,
    parsed: Any = None,
    lesson_filter: str | None = None,
) -> dict[str, Any]:
    current_lesson: str | None = None
    current_section: str | None = None
    detected_lessons: list[str] = []
    units: list[dict[str, Any]] = []
    structural_counts: Counter[str] = Counter()

    for body_index, element in enumerate(doc.get("body", {}).get("content", [])):
        element_range = {
            "start_index": element.get("startIndex"),
            "end_index": element.get("endIndex"),
        }
        paragraph = element.get("paragraph")
        if paragraph:
            text = _source_text(_paragraph_text(paragraph)).strip()
            if _is_heading(paragraph) and (new_lesson := _lesson_id(text)):
                current_lesson = new_lesson
                current_section = None
                if new_lesson not in detected_lessons:
                    detected_lessons.append(new_lesson)
            else:
                normalized = _normalized_header(text)
                if normalized in SECTION_HEADERS:
                    current_section = normalized

            if lesson_filter is None or current_lesson == lesson_filter:
                unit = _make_unit(
                    paragraph,
                    path=f"body.content[{body_index}].paragraph",
                    container="body",
                    element_range=element_range,
                    lesson_id=current_lesson,
                    section=current_section,
                )
                if unit:
                    units.append(unit)
            continue

        if table := element.get("table"):
            structural_counts["tables"] += 1
            if lesson_filter is None or current_lesson == lesson_filter:
                for nested_paragraph, path, nested_range in _iter_table_paragraphs(
                    table,
                    base_path=f"body.content[{body_index}].table",
                ):
                    unit = _make_unit(
                        nested_paragraph,
                        path=path,
                        container="table_cell",
                        element_range=nested_range,
                        lesson_id=current_lesson,
                        section=current_section,
                    )
                    if unit:
                        units.append(unit)
            continue

        if "sectionBreak" in element:
            structural_counts["section_breaks"] += 1
        elif "tableOfContents" in element:
            structural_counts["table_of_contents"] += 1
        else:
            structural_counts["other"] += 1

    removals = [
        removal
        for removal in _prepare_removals(doc)
        if lesson_filter is None or removal.get("lesson_id") == lesson_filter
    ]
    removals.extend(_header_image_removals(units))
    removals.sort(key=lambda removal: removal["start_index"])
    _apply_practice_option_policy(units)

    parsed_lessons = _parsed_lesson_ids(parsed)
    validation_issues: list[str] = []
    if not doc.get("documentId"):
        validation_issues.append("Raw document has no documentId.")
    if parsed is not None and detected_lessons != parsed_lessons:
        validation_issues.append(
            "Raw/parsed lesson IDs differ: "
            f"raw={detected_lessons!r}, parsed={parsed_lessons!r}."
        )
    if lesson_filter and lesson_filter not in detected_lessons:
        validation_issues.append(f"Requested lesson {lesson_filter!r} was not found.")

    action_counts = Counter(unit["recommended_action"] for unit in units)
    role_counts = Counter(unit["role"] for unit in units)
    warning_count = sum(len(unit["warnings"]) for unit in units)
    write_blockers = ["This manifest was generated in read-only mode."]
    if not doc.get("revisionId"):
        write_blockers.append(
            "The Docs response has no revisionId; refetch after editor access is granted before planning writes."
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "read_only_translation_plan",
        "source": {
            "document_id": doc.get("documentId"),
            "title": doc.get("title"),
            "revision_id": doc.get("revisionId"),
            "raw_sha256": raw_sha256,
            "suggestions_view_mode": doc.get("suggestionsViewMode"),
        },
        "policy": {
            "specification": "docs/thai-google-doc-translation-spec.md",
            "source_is_authoritative": True,
            "writes_allowed": False,
        },
        "selection": {"lesson": lesson_filter},
        "inventory": {
            "detected_lesson_ids": detected_lessons,
            "parsed_lesson_ids": parsed_lessons,
            "body_element_count": len(doc.get("body", {}).get("content", [])),
            "list_definition_count": len(doc.get("lists", {})),
            "structural_counts": dict(sorted(structural_counts.items())),
        },
        "summary": {
            "unit_count": len(units),
            "action_counts": dict(sorted(action_counts.items())),
            "role_counts": dict(sorted(role_counts.items())),
            "prepare_removal_count": sum(
                removal.get("section") == "PREPARE" for removal in removals
            ),
            "header_image_removal_count": sum(
                removal.get("section") == "HEADER_IMAGE" for removal in removals
            ),
            "warning_count": warning_count,
            "validation_issue_count": len(validation_issues),
        },
        "validation_issues": validation_issues,
        "write_readiness": {
            "ready": False,
            "blockers": write_blockers,
        },
        "planned_removals": removals,
        "units": units,
    }


def render_report(manifest: dict[str, Any]) -> str:
    source = manifest["source"]
    summary = manifest["summary"]
    selection = manifest["selection"]
    lines = [
        "# Thai lesson translation dry-run report",
        "",
        "This report is read-only. No translation has been generated and no Google Doc write was attempted.",
        "",
        "## Source",
        "",
        f"- Document: `{source.get('title')}`",
        f"- Document ID: `{source.get('document_id')}`",
        f"- Raw SHA-256: `{source.get('raw_sha256')}`",
        f"- Lesson selection: `{selection.get('lesson') or 'all'}`",
        "- Source-authority rule: enabled",
        "- Writes allowed: no",
        "",
        "## Validation",
        "",
    ]

    issues = manifest.get("validation_issues", [])
    if issues:
        lines.extend(f"- ERROR: {issue}" for issue in issues)
    else:
        lines.append("- Raw and parsed lesson inventories match.")

    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Translation units: {summary['unit_count']}",
            f"- PREPARE ranges planned for removal: {summary['prepare_removal_count']}",
            f"- Header-image markers planned for removal: {summary['header_image_removal_count']}",
            f"- Classification warnings: {summary['warning_count']}",
            "",
            "### Units by recommended action",
            "",
            "| Action | Units |",
            "| --- | ---: |",
        ]
    )
    for action, count in manifest["summary"]["action_counts"].items():
        lines.append(f"| `{action}` | {count} |")

    by_lesson: dict[str, Counter[str]] = defaultdict(Counter)
    by_section: dict[str, Counter[str]] = defaultdict(Counter)
    for unit in manifest.get("units", []):
        lesson = unit.get("lesson_id") or "preamble"
        section = unit.get("section") or "none"
        by_lesson[lesson][unit["recommended_action"]] += 1
        by_section[section][unit["recommended_action"]] += 1

    all_actions = sorted(manifest["summary"]["action_counts"])
    lines.extend(["", "### Units by lesson", ""])
    lines.append("| Lesson | " + " | ".join(all_actions) + " | Total |")
    lines.append("| --- | " + " | ".join("---:" for _ in all_actions) + " | ---: |")
    for lesson, counts in by_lesson.items():
        values = [str(counts.get(action, 0)) for action in all_actions]
        lines.append(f"| `{lesson}` | " + " | ".join(values) + f" | {sum(counts.values())} |")

    lines.extend(["", "### Units by section", ""])
    lines.append("| Section | " + " | ".join(all_actions) + " | Total |")
    lines.append("| --- | " + " | ".join("---:" for _ in all_actions) + " | ---: |")
    for section, counts in by_section.items():
        values = [str(counts.get(action, 0)) for action in all_actions]
        lines.append(f"| `{section}` | " + " | ".join(values) + f" | {sum(counts.values())} |")

    lines.extend(["", "## Planned removals", ""])
    removals = manifest.get("planned_removals", [])
    if removals:
        lines.extend(
            [
                "| Lesson | Start index | End index |",
                "| --- | ---: | ---: |",
            ]
        )
        for removal in removals:
            lines.append(
                f"| `{removal.get('lesson_id')}` | {removal.get('start_index')} | "
                f"{removal.get('end_index')} |"
            )
    else:
        lines.append("None.")

    lines.extend(["", "## Write readiness", ""])
    for blocker in manifest.get("write_readiness", {}).get("blockers", []):
        lines.append(f"- BLOCKED: {blocker}")

    warning_units = [unit for unit in manifest.get("units", []) if unit.get("warnings")]
    lines.extend(["", "## Classification warnings", ""])
    if warning_units:
        lines.append("Warnings are review markers, not permission to change source content.")
        lines.append("")
        for unit in warning_units:
            preview = unit["source_text"].replace("\n", " ↵ ")[:120]
            lines.append(
                f"- `{unit['unit_id']}` ({unit['role']}): "
                f"{' '.join(unit['warnings'])} Source: `{preview}`"
            )
    else:
        lines.append("None.")

    lines.extend(
        [
            "",
            "## Next gate",
            "",
            "Review classifications and protected tokens, populate translations for one complete lesson, "
            "then validate the completed manifest. Google Docs write support remains out of scope for this phase.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a read-only English-to-Thai Google Docs translation manifest."
    )
    parser.add_argument("--raw", required=True, type=Path, help="Saved Google Docs API JSON.")
    parser.add_argument("--parsed", type=Path, help="Optional parsed lesson JSON for inventory checks.")
    parser.add_argument("--lesson", help="Optional lesson ID, for example 14.1 or 14.chp.")
    parser.add_argument("--out", required=True, type=Path, help="Manifest JSON output path.")
    parser.add_argument("--report", required=True, type=Path, help="Markdown report output path.")
    args = parser.parse_args()

    raw_bytes = args.raw.read_bytes()
    doc = json.loads(raw_bytes.decode("utf-8"))
    parsed = _read_json(args.parsed) if args.parsed else None
    manifest = build_manifest(
        doc,
        raw_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        parsed=parsed,
        lesson_filter=args.lesson,
    )

    _write_json(args.out, manifest)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(manifest), encoding="utf-8")

    print(f"Wrote {manifest['summary']['unit_count']} units to {args.out}")
    print(f"Wrote dry-run report to {args.report}")
    if manifest["validation_issues"]:
        for issue in manifest["validation_issues"]:
            print(f"ERROR: {issue}")
        raise SystemExit(2)


if __name__ == "__main__":
    main()

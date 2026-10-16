"""Replace one already-translated lesson with a newly translated source version.

The normal writer intentionally requires an untouched English destination. This
tool handles the narrower retranslation case: the destination already contains
an older Thai rendering, while a separately saved English source has changed.
It diffs rendered paragraphs, replaces only changed blocks, and leaves later
lessons and unchanged formatted paragraphs in place.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from .lesson_translation_manifest import _protected_tokens
from .lesson_translation_validator import validate_manifest
from .lesson_translation_writer import (
    DOCS_WRITE_SCOPE,
    REQUIRED_ACTIONS,
    WRITABLE_INLINE_STYLE_FIELDS,
    WRITABLE_TEXT_STYLE_FIELDS,
    _bilingual_prefix,
    _dominant_writable_style,
    _link_inventory,
    _utf16_len,
)


LESSON_HEADING_RE = re.compile(r"^LESSON\s+(\d+\.\d+)\s*:", re.IGNORECASE)
CHECKPOINT_HEADING_RE = re.compile(r"^CHECKPOINT\s+(\d+)\b", re.IGNORECASE)
WRITABLE_PARAGRAPH_STYLE_FIELDS = {
    "alignment",
    "avoidWidowAndOrphan",
    "borderBetween",
    "borderBottom",
    "borderLeft",
    "borderRight",
    "borderTop",
    "direction",
    "indentEnd",
    "indentFirstLine",
    "indentStart",
    "keepLinesTogether",
    "keepWithNext",
    "lineSpacing",
    "namedStyleType",
    "pageBreakBefore",
    "shading",
    "spaceAbove",
    "spaceBelow",
    "spacingMode",
}
BOOLEAN_TEXT_STYLE_FIELDS = {
    "bold",
    "italic",
    "smallCaps",
    "strikethrough",
    "underline",
}


@dataclass(frozen=True)
class Paragraph:
    text: str
    start_index: int
    end_index: int
    paragraph_style: dict[str, Any]
    text_style: dict[str, Any]
    bullet: dict[str, Any] | None
    complex_text_style: bool
    style_spans: list[dict[str, Any]]


@dataclass(frozen=True)
class ReplacementGroup:
    tag: str
    before_start: int
    before_end: int
    desired_start: int
    desired_end: int
    start_index: int
    end_index: int
    before_texts: list[str]
    desired_texts: list[str]
    requests: list[dict[str, Any]]


def _paragraph_link_inventory(paragraphs: list[Paragraph]) -> Counter[str]:
    inventory: Counter[str] = Counter()
    for paragraph in paragraphs:
        seen: set[tuple[int, int, str]] = set()
        for span in paragraph.style_spans:
            url = span.get("style", {}).get("link", {}).get("url")
            key = (span.get("start", 0), span.get("end", 0), url or "")
            if url and key not in seen:
                inventory[url] += 1
                seen.add(key)
    return inventory


def _paragraph_link_spans(paragraphs: list[Paragraph]) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    for paragraph in paragraphs:
        spans: list[dict[str, Any]] = []
        seen: set[tuple[int, int, str]] = set()
        for span in paragraph.style_spans:
            link = span.get("style", {}).get("link", {})
            url = link.get("url")
            key = (span.get("start", 0), span.get("end", 0), url or "")
            if not url or key in seen:
                continue
            seen.add(key)
            spans.append({"start": key[0], "end": key[1], "link": link})
        result.append(spans)
    return result


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _paragraph_text(paragraph: dict[str, Any]) -> str:
    text = "".join(
        element.get("textRun", {}).get("content", "")
        for element in paragraph.get("elements", [])
    )
    return text[:-1] if text.endswith("\n") else text


def _normalized_text_style(style: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: value for key, value in style.items() if key in WRITABLE_TEXT_STYLE_FIELDS
    }
    for key in BOOLEAN_TEXT_STYLE_FIELDS:
        result.setdefault(key, False)
    result.setdefault("baselineOffset", "NONE")
    return result


def _raw_paragraph(element: dict[str, Any]) -> Paragraph:
    paragraph = element["paragraph"]
    styles = []
    for child in paragraph.get("elements", []):
        run = child.get("textRun")
        if not run:
            continue
        style = {
            key: value
            for key, value in run.get("textStyle", {}).items()
            if key in WRITABLE_TEXT_STYLE_FIELDS
        }
        if run.get("content", "").rstrip("\n"):
            styles.append(json.dumps(style, sort_keys=True))
    dominant = {}
    weighted = []
    for child in paragraph.get("elements", []):
        run = child.get("textRun")
        if run:
            style = {
                key: value
                for key, value in run.get("textStyle", {}).items()
                if key in WRITABLE_TEXT_STYLE_FIELDS
            }
            weighted.append((_utf16_len(run.get("content", "").rstrip("\n")), style))
    if weighted:
        dominant = max(weighted, key=lambda item: item[0])[1]
    paragraph_start = element["startIndex"]
    style_spans: list[dict[str, Any]] = []
    for child in paragraph.get("elements", []):
        run = child.get("textRun")
        child_start = child.get("startIndex")
        if not run or not isinstance(child_start, int):
            continue
        text = run.get("content", "").rstrip("\n")
        style = {
            key: value
            for key, value in run.get("textStyle", {}).items()
            if key in WRITABLE_INLINE_STYLE_FIELDS
        }
        if text and style:
            relative_start = child_start - paragraph_start
            style_spans.append(
                {
                    "start": relative_start,
                    "end": relative_start + _utf16_len(text),
                    "style": style,
                }
            )
    return Paragraph(
        text=_paragraph_text(paragraph),
        start_index=element["startIndex"],
        end_index=element["endIndex"],
        paragraph_style={
            key: value
            for key, value in paragraph.get("paragraphStyle", {}).items()
            if key in WRITABLE_PARAGRAPH_STYLE_FIELDS
        },
        text_style=_normalized_text_style(dominant),
        bullet=paragraph.get("bullet"),
        complex_text_style=len(set(styles)) > 1,
        style_spans=style_spans,
    )


def _lesson_paragraphs(document: dict[str, Any], lesson: str) -> list[Paragraph]:
    selected = _lesson_elements(document, lesson)
    non_paragraphs = [element for element in selected if "paragraph" not in element]
    if non_paragraphs:
        raise ValueError(
            f"Lesson {lesson} contains non-paragraph structures; safe block replacement is unavailable"
        )
    return [_raw_paragraph(element) for element in selected]


def _lesson_elements(document: dict[str, Any], lesson: str) -> list[dict[str, Any]]:
    body = document.get("body", {}).get("content", [])
    start = None
    end = None
    for index, element in enumerate(body):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        match = LESSON_HEADING_RE.match(_paragraph_text(paragraph))
        checkpoint = CHECKPOINT_HEADING_RE.match(_paragraph_text(paragraph))
        boundary = match.group(1) if match else (
            f"{checkpoint.group(1)}.chp" if checkpoint else None
        )
        if boundary == lesson:
            start = index
        elif start is not None and boundary is not None:
            end = index
            break
    if start is None:
        raise ValueError(f"Lesson {lesson} heading was not found")
    end = len(body) if end is None else end
    return body[start:end]


def _nested_paragraphs(value: Any) -> list[Paragraph]:
    paragraphs: list[Paragraph] = []
    if isinstance(value, dict):
        if "paragraph" in value and "startIndex" in value:
            paragraphs.append(_raw_paragraph(value))
        else:
            for key, child in value.items():
                if key not in {"startIndex", "endIndex"}:
                    paragraphs.extend(_nested_paragraphs(child))
    elif isinstance(value, list):
        for child in value:
            paragraphs.extend(_nested_paragraphs(child))
    return paragraphs


def _lesson_all_paragraphs(document: dict[str, Any], lesson: str) -> list[Paragraph]:
    return _nested_paragraphs(_lesson_elements(document, lesson))


def _render_unit_text(unit: dict[str, Any]) -> str:
    rendered = ""
    for part in unit.get("translation_parts", []):
        action = part.get("recommended_action")
        source = part.get("source_text", "")
        separator = part.get("separator_after", "")
        translated = part.get("translated_text")
        if action == "preserve":
            rendered += source + separator
        elif action == "remove":
            rendered += separator
        elif action == "bilingual":
            if not isinstance(translated, str):
                raise ValueError(f"Missing translation for {unit.get('unit_id')}")
            rendered += source + _bilingual_prefix(unit, part) + translated + separator
        elif action in {"translate", "localize"}:
            if not isinstance(translated, str):
                raise ValueError(f"Missing translation for {unit.get('unit_id')}")
            rendered += translated + separator
        else:
            raise ValueError(f"Unsupported action {action!r}")
    return rendered


def render_desired_paragraphs(
    source_document: dict[str, Any], completed_manifest: dict[str, Any], lesson: str
) -> list[Paragraph]:
    source = _lesson_paragraphs(source_document, lesson)
    return _render_source_paragraphs(source, completed_manifest)


def _render_source_paragraphs(
    source: list[Paragraph], completed_manifest: dict[str, Any]
) -> list[Paragraph]:
    units = {
        unit.get("location", {}).get("start_index"): unit
        for unit in completed_manifest.get("units", [])
    }
    removals = completed_manifest.get("planned_removals", [])
    desired: list[Paragraph] = []
    for paragraph in source:
        if any(
            paragraph.start_index >= removal["start_index"]
            and paragraph.end_index <= removal["end_index"]
            for removal in removals
        ):
            continue
        unit = units.get(paragraph.start_index)
        rendered = paragraph.text if unit is None else _render_unit_text(unit)
        style = paragraph.text_style
        if unit is not None:
            style = _normalized_text_style(_dominant_writable_style(unit))
        pieces = rendered.split("\n")
        for piece in pieces:
            style_spans: list[dict[str, Any]] = list(paragraph.style_spans)
            if unit is not None:
                style_spans = []
                search_from = 0
                for segment in unit.get("style_segments", []):
                    segment_text = segment.get("text", "")
                    segment_style = {
                        key: value
                        for key, value in segment.get("style", {}).items()
                        if key in WRITABLE_INLINE_STYLE_FIELDS
                    }
                    found = piece.find(segment_text, search_from)
                    if segment_text and found >= 0 and segment_style:
                        start = _utf16_len(piece[:found])
                        style_spans.append(
                            {
                                "start": start,
                                "end": start + _utf16_len(segment_text),
                                "style": segment_style,
                            }
                        )
                        search_from = found + len(segment_text)
                for part in unit.get("translation_parts", []):
                    translated = part.get("translated_text")
                    if not isinstance(translated, str):
                        continue
                    translated_at = piece.find(translated)
                    if translated_at < 0:
                        continue
                    translated_start = _utf16_len(piece[:translated_at])
                    for span in part.get("translated_style_spans", []):
                        span_start = span.get("start")
                        span_end = span.get("end")
                        if not isinstance(span_start, int) or not isinstance(span_end, int):
                            continue
                        span_style = {
                            key: value
                            for key, value in span.get("style", {}).items()
                            if key in WRITABLE_INLINE_STYLE_FIELDS
                        }
                        style_spans.append(
                            {
                                "start": translated_start
                                + _utf16_len(translated[:span_start]),
                                "end": translated_start
                                + _utf16_len(translated[:span_end]),
                                "style": span_style,
                            }
                        )
            desired.append(
                Paragraph(
                    text=piece,
                    start_index=0,
                    end_index=0,
                    paragraph_style=paragraph.paragraph_style,
                    text_style=style,
                    bullet=paragraph.bullet,
                    complex_text_style=paragraph.complex_text_style,
                    style_spans=style_spans,
                )
            )
    for index, paragraph in enumerate(desired):
        if not paragraph.text.startswith("LESSON FOCUS "):
            continue
        while index + 1 < len(desired) and not desired[index + 1].text:
            del desired[index + 1]
        break
    return desired


def _diff_region(
    before: list[Paragraph],
    desired: list[Paragraph],
    before_offset: int,
    desired_offset: int,
) -> list[tuple[str, int, int, int, int]]:
    matcher = SequenceMatcher(
        a=[paragraph.text for paragraph in before],
        b=[paragraph.text for paragraph in desired],
        autojunk=False,
    )
    return [
        (tag, i1 + before_offset, i2 + before_offset, j1 + desired_offset, j2 + desired_offset)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]


def _style_requests(start: int, paragraphs: list[Paragraph]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    cursor = start
    for paragraph in paragraphs:
        text_end = cursor + _utf16_len(paragraph.text)
        paragraph_end = text_end + 1
        if paragraph.paragraph_style:
            requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": cursor, "endIndex": paragraph_end},
                        "paragraphStyle": paragraph.paragraph_style,
                        "fields": ",".join(sorted(paragraph.paragraph_style)),
                    }
                }
            )
        if paragraph.text and paragraph.text_style:
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": cursor, "endIndex": text_end},
                        "textStyle": paragraph.text_style,
                        "fields": ",".join(sorted(paragraph.text_style)),
                    }
                }
            )
        for span in paragraph.style_spans:
            if span["end"] <= span["start"] or not span["style"]:
                continue
            requests.append(
                {
                    "updateTextStyle": {
                        "range": {
                            "startIndex": cursor + span["start"],
                            "endIndex": cursor + span["end"],
                        },
                        "textStyle": span["style"],
                        "fields": ",".join(sorted(span["style"])),
                    }
                }
            )
        cursor = paragraph_end
    return requests


def _bullet_requests(start: int, paragraphs: list[Paragraph]) -> list[dict[str, Any]]:
    if not paragraphs:
        return []
    offsets: list[tuple[int, int, bool]] = []
    cursor = start
    for paragraph in paragraphs:
        end = cursor + _utf16_len(paragraph.text) + 1
        offsets.append((cursor, end, bool(paragraph.bullet)))
        cursor = end
    requests: list[dict[str, Any]] = [
        {
            "deleteParagraphBullets": {
                "range": {"startIndex": start, "endIndex": cursor}
            }
        }
    ]
    run_start: int | None = None
    run_end: int | None = None
    for paragraph_start, paragraph_end, is_bullet in offsets + [(cursor, cursor, False)]:
        if is_bullet:
            run_start = paragraph_start if run_start is None else run_start
            run_end = paragraph_end
        elif run_start is not None and run_end is not None:
            requests.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": run_start, "endIndex": run_end},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
            )
            run_start = None
            run_end = None
    return requests


def _table_aware_plan(
    source_document: dict[str, Any],
    destination_document: dict[str, Any],
    completed_manifest: dict[str, Any],
    validation: dict[str, Any],
    *,
    lesson: str,
    destination_doc_id: str,
) -> dict[str, Any]:
    source_elements = _lesson_elements(source_document, lesson)
    destination_elements = _lesson_elements(destination_document, lesson)
    source_tables = [element for element in source_elements if "table" in element]
    destination_tables = [element for element in destination_elements if "table" in element]
    if len(source_tables) != len(destination_tables):
        raise ValueError("Source and destination table counts differ")

    def segments(elements: list[dict[str, Any]]) -> list[list[Paragraph]]:
        result: list[list[Paragraph]] = [[]]
        for element in elements:
            if "table" in element:
                result.append([])
            elif "paragraph" in element:
                result[-1].append(_raw_paragraph(element))
            else:
                raise ValueError("Unsupported non-paragraph lesson structure")
        return result

    source_segments = segments(source_elements)
    destination_segments = segments(destination_elements)
    desired_segments = [
        _render_source_paragraphs(segment, completed_manifest)
        for segment in source_segments
    ]
    groups: list[ReplacementGroup] = []
    expected: list[Paragraph] = []
    before_all: list[Paragraph] = []

    for index, (before, desired) in enumerate(
        zip(destination_segments, desired_segments, strict=True)
    ):
        before_all.extend(before)
        expected.extend(desired)
        if not before and not desired:
            continue
        segment_end = (
            destination_tables[index]["startIndex"]
            if index < len(destination_tables)
            else before[-1].end_index
        )
        opcodes = _diff_region(before, desired, 0, 0)
        for tag, i1, i2, j1, j2 in opcodes:
            replacement = desired[j1:j2]
            start = before[i1].start_index if i1 < len(before) else segment_end
            end = before[i2 - 1].end_index if i2 > i1 else start
            preserves_table_boundary = (
                index < len(destination_tables)
                and i2 == len(before)
                and end == segment_end
                and end > start
            )
            if preserves_table_boundary:
                end -= 1
            requests: list[dict[str, Any]] = []
            if end > start:
                requests.append(
                    {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}
                )
            inserted = "".join(paragraph.text + "\n" for paragraph in replacement)
            if preserves_table_boundary and inserted.endswith("\n"):
                inserted = inserted[:-1]
            if inserted:
                requests.append({"insertText": {"location": {"index": start}, "text": inserted}})
                requests.extend(_bullet_requests(start, replacement))
                requests.extend(_style_requests(start, replacement))
            groups.append(
                ReplacementGroup(
                    tag=tag,
                    before_start=i1,
                    before_end=i2,
                    desired_start=j1,
                    desired_end=j2,
                    start_index=start,
                    end_index=end,
                    before_texts=[paragraph.text for paragraph in before[i1:i2]],
                    desired_texts=[paragraph.text for paragraph in replacement],
                    requests=requests,
                )
            )
        if index >= len(source_tables):
            continue
        source_nested = _nested_paragraphs(source_tables[index])
        destination_nested = _nested_paragraphs(destination_tables[index])
        desired_nested = _render_source_paragraphs(source_nested, completed_manifest)
        if len(destination_nested) != len(desired_nested):
            raise ValueError("Translated table paragraph count changed")
        before_all.extend(destination_nested)
        expected.extend(desired_nested)
        for before_paragraph, desired_paragraph in zip(
            destination_nested, desired_nested, strict=True
        ):
            start = before_paragraph.start_index
            end = before_paragraph.end_index - 1
            requests = []
            if end > start:
                requests.append(
                    {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}
                )
            if desired_paragraph.text:
                requests.append(
                    {"insertText": {"location": {"index": start}, "text": desired_paragraph.text}}
                )
                requests.extend(_style_requests(start, [desired_paragraph]))
            groups.append(
                ReplacementGroup(
                    tag="table_cell",
                    before_start=0,
                    before_end=1,
                    desired_start=0,
                    desired_end=1,
                    start_index=start,
                    end_index=end,
                    before_texts=[before_paragraph.text],
                    desired_texts=[desired_paragraph.text],
                    requests=requests,
                )
            )

    groups.sort(key=lambda group: (group.start_index, group.end_index), reverse=True)
    requests = [request for group in groups for request in group.requests]
    before_links = _link_inventory(destination_document)
    expected_links = Counter(before_links)
    expected_links.subtract(_paragraph_link_inventory(before_all))
    expected_links.update(_paragraph_link_inventory(expected))
    expected_links = Counter({url: count for url, count in expected_links.items() if count})
    return {
        "schema_version": 1,
        "mode": "translated_lesson_replacement",
        "lesson": lesson,
        "contains_tables": True,
        "source_document_id": source_document.get("documentId"),
        "destination_document_id": destination_doc_id,
        "before_revision_id": destination_document.get("revisionId"),
        "expected_before_paragraphs": [paragraph.text for paragraph in before_all],
        "expected_after_paragraphs": [paragraph.text for paragraph in expected],
        "expected_unchanged_tail": _document_tail_texts(destination_document, lesson),
        "before_link_inventory": dict(before_links),
        "expected_link_inventory": dict(expected_links),
        "expected_link_spans": _paragraph_link_spans(expected),
        "expected_paragraph_formats": [
            {
                "paragraph_style": paragraph.paragraph_style,
                "text_style": paragraph.text_style,
                "style_spans": paragraph.style_spans,
            }
            for paragraph in expected
        ],
        "summary": {
            "replacement_group_count": len(groups),
            "google_request_count": len(requests),
            "before_paragraph_count": len(before_all),
            "after_paragraph_count": len(expected),
            "validation": validation["summary"],
        },
        "groups": [asdict(group) for group in groups],
        "requests": requests,
    }


def build_replacement_plan(
    source_document: dict[str, Any],
    destination_document: dict[str, Any],
    completed_manifest: dict[str, Any],
    source_manifest: dict[str, Any],
    *,
    lesson: str,
    destination_doc_id: str,
    allowed_doc_id: str,
) -> dict[str, Any]:
    if destination_doc_id != allowed_doc_id:
        raise ValueError("Destination document ID must exactly match the allowlist")
    if destination_document.get("documentId") != destination_doc_id:
        raise ValueError("Destination snapshot document ID does not match the allowlist")
    if source_document.get("documentId") != completed_manifest.get("source", {}).get(
        "document_id"
    ):
        raise ValueError("Source snapshot does not match the completed manifest")
    validation = validate_manifest(completed_manifest, source_manifest=source_manifest)
    if not validation["valid"]:
        raise ValueError("Completed manifest failed validation")

    if any("table" in element for element in _lesson_elements(source_document, lesson)):
        return _table_aware_plan(
            source_document,
            destination_document,
            completed_manifest,
            validation,
            lesson=lesson,
            destination_doc_id=destination_doc_id,
        )

    before = _lesson_paragraphs(destination_document, lesson)
    desired = render_desired_paragraphs(source_document, completed_manifest, lesson)
    before_texts = [paragraph.text for paragraph in before]
    desired_texts = [paragraph.text for paragraph in desired]

    try:
        before_practice = before_texts.index("PRACTICE")
        before_pinned = before_texts.index("PINNED COMMENT", before_practice)
        desired_practice = desired_texts.index("PRACTICE")
        desired_pinned = desired_texts.index("PINNED COMMENT", desired_practice)
    except ValueError as exc:
        raise ValueError("PRACTICE/PINNED COMMENT boundaries are required") from exc

    opcodes = _diff_region(
        before[: before_practice + 1],
        desired[: desired_practice + 1],
        0,
        0,
    )
    opcodes.append(
        (
            "replace",
            before_practice + 1,
            before_pinned,
            desired_practice + 1,
            desired_pinned,
        )
    )
    opcodes.extend(
        _diff_region(
            before[before_pinned:],
            desired[desired_pinned:],
            before_pinned,
            desired_pinned,
        )
    )

    lesson_end = before[-1].end_index
    groups: list[ReplacementGroup] = []
    for tag, i1, i2, j1, j2 in opcodes:
        replacement = desired[j1:j2]
        start = before[i1].start_index if i1 < len(before) else lesson_end
        end = before[i2 - 1].end_index if i2 > i1 else start
        requests: list[dict[str, Any]] = []
        if end > start:
            requests.append(
                {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}
            )
        inserted = "".join(paragraph.text + "\n" for paragraph in replacement)
        if inserted:
            requests.append({"insertText": {"location": {"index": start}, "text": inserted}})
            requests.extend(_bullet_requests(start, replacement))
            requests.extend(_style_requests(start, replacement))
        groups.append(
            ReplacementGroup(
                tag=tag,
                before_start=i1,
                before_end=i2,
                desired_start=j1,
                desired_end=j2,
                start_index=start,
                end_index=end,
                before_texts=before_texts[i1:i2],
                desired_texts=desired_texts[j1:j2],
                requests=requests,
            )
        )
    groups.sort(key=lambda group: (group.start_index, group.end_index), reverse=True)
    requests = [request for group in groups for request in group.requests]
    before_links = _link_inventory(destination_document)
    expected_links = Counter(before_links)
    expected_links.subtract(_paragraph_link_inventory(before))
    expected_links.update(_paragraph_link_inventory(desired))
    expected_links = Counter({url: count for url, count in expected_links.items() if count})
    return {
        "schema_version": 1,
        "mode": "translated_lesson_replacement",
        "lesson": lesson,
        "source_document_id": source_document.get("documentId"),
        "destination_document_id": destination_doc_id,
        "before_revision_id": destination_document.get("revisionId"),
        "expected_before_paragraphs": before_texts,
        "expected_after_paragraphs": desired_texts,
        "expected_unchanged_tail": _document_tail_texts(destination_document, lesson),
        "before_link_inventory": dict(before_links),
        "expected_link_inventory": dict(expected_links),
        "expected_link_spans": _paragraph_link_spans(desired),
        "expected_paragraph_formats": [
            {
                "paragraph_style": paragraph.paragraph_style,
                "text_style": paragraph.text_style,
                "style_spans": paragraph.style_spans,
            }
            for paragraph in desired
        ],
        "summary": {
            "replacement_group_count": len(groups),
            "google_request_count": len(requests),
            "before_paragraph_count": len(before),
            "after_paragraph_count": len(desired),
            "validation": validation["summary"],
        },
        "groups": [asdict(group) for group in groups],
        "requests": requests,
    }


def _document_tail_texts(document: dict[str, Any], lesson: str) -> list[str]:
    found = False
    texts: list[str] = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        text = _paragraph_text(paragraph)
        match = LESSON_HEADING_RE.match(text) or CHECKPOINT_HEADING_RE.match(text)
        if found:
            texts.append(text)
        elif match and match.group(1) == lesson:
            found = True
    lesson_count = sum(
        1
        for text in texts
        if LESSON_HEADING_RE.match(text) or CHECKPOINT_HEADING_RE.match(text)
    )
    if lesson_count:
        first_next = next(
            index
            for index, text in enumerate(texts)
            if LESSON_HEADING_RE.match(text) or CHECKPOINT_HEADING_RE.match(text)
        )
        return texts[first_next:]
    return []


def _token_inventory(texts: list[str]) -> Counter[tuple[str, str]]:
    return Counter(
        (token["kind"], token["text"])
        for text in texts
        for token in _protected_tokens(text)
    )


def _google_docs_service(credentials_path: Path):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        credentials_path, scopes=[DOCS_WRITE_SCOPE]
    )
    return build("docs", "v1", credentials=credentials, cache_discovery=False)


def execute_replacement_plan(
    plan: dict[str, Any], credentials_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    service = _google_docs_service(credentials_path)
    document_id = plan["destination_document_id"]
    before = service.documents().get(documentId=document_id).execute()
    paragraph_reader = (
        _lesson_all_paragraphs if plan.get("contains_tables") else _lesson_paragraphs
    )
    live_texts = [p.text for p in paragraph_reader(before, plan["lesson"])]
    if before.get("revisionId") != plan.get("before_revision_id"):
        raise ValueError("Destination revision changed after planning")
    if live_texts != plan["expected_before_paragraphs"]:
        raise ValueError("Destination lesson changed after planning")

    responses: list[dict[str, Any]] = []
    request_chunks: list[list[dict[str, Any]]] = []
    pending: list[dict[str, Any]] = []
    for group in plan["groups"]:
        group_requests = group["requests"]
        if pending and len(pending) + len(group_requests) > 400:
            request_chunks.append(pending)
            pending = []
        pending.extend(group_requests)
    grouped_request_count = sum(len(group["requests"]) for group in plan["groups"])
    for request in plan["requests"][grouped_request_count:]:
        if len(pending) >= 400:
            request_chunks.append(pending)
            pending = []
        pending.append(request)
    if pending:
        request_chunks.append(pending)

    required_revision = before["revisionId"]
    for chunk in request_chunks:
        response = (
            service.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": chunk,
                    "writeControl": {"requiredRevisionId": required_revision},
                },
            )
            .execute()
        )
        responses.append(response)
        required_revision = (
            response.get("writeControl", {}).get("requiredRevisionId")
            or service.documents().get(documentId=document_id).execute()["revisionId"]
        )
    intermediate = service.documents().get(documentId=document_id).execute()
    rendered = paragraph_reader(intermediate, plan["lesson"])
    if [paragraph.text for paragraph in rendered] == plan["expected_after_paragraphs"]:
        format_requests: list[dict[str, Any]] = []
        for paragraph, expected_format in zip(
            rendered, plan.get("expected_paragraph_formats", []), strict=True
        ):
            paragraph_style = expected_format["paragraph_style"]
            format_requests.append(
                {
                    "updateParagraphStyle": {
                        "range": {
                            "startIndex": paragraph.start_index,
                            "endIndex": paragraph.end_index,
                        },
                        "paragraphStyle": paragraph_style,
                            "fields": ",".join(
                                sorted(WRITABLE_PARAGRAPH_STYLE_FIELDS - {"pageBreakBefore"})
                            ),
                    }
                }
            )
            if paragraph.text:
                format_requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": paragraph.start_index,
                                "endIndex": paragraph.start_index
                                + _utf16_len(paragraph.text),
                            },
                            "textStyle": expected_format["text_style"],
                            "fields": ",".join(sorted(WRITABLE_TEXT_STYLE_FIELDS)),
                        }
                    }
                )
            for span in expected_format["style_spans"]:
                style = {
                    key: value
                    for key, value in span["style"].items()
                    if key != "link"
                }
                if not style or span["end"] <= span["start"]:
                    continue
                format_requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": paragraph.start_index + span["start"],
                                "endIndex": paragraph.start_index + span["end"],
                            },
                            "textStyle": style,
                            "fields": ",".join(sorted(style)),
                        }
                    }
                )
        for offset in range(0, len(format_requests), 400):
            response = (
                service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={
                        "requests": format_requests[offset : offset + 400],
                        "writeControl": {"requiredRevisionId": required_revision},
                    },
                )
                .execute()
            )
            responses.append(response)
            required_revision = (
                response.get("writeControl", {}).get("requiredRevisionId")
                or service.documents().get(documentId=document_id).execute()["revisionId"]
            )
        intermediate = service.documents().get(documentId=document_id).execute()
        rendered = paragraph_reader(intermediate, plan["lesson"])
        link_requests: list[dict[str, Any]] = []
        for paragraph, expected_spans in zip(
            rendered, plan.get("expected_link_spans", []), strict=True
        ):
            live_link_spans = [
                span
                for span in paragraph.style_spans
                if span.get("style", {}).get("link", {}).get("url")
            ]
            for live_span in live_link_spans:
                link_requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": paragraph.start_index
                                + live_span["start"],
                                "endIndex": paragraph.start_index + live_span["end"],
                            },
                            "textStyle": {},
                            "fields": "link",
                        }
                    }
                )
            for span in expected_spans:
                link_requests.append(
                    {
                        "updateTextStyle": {
                            "range": {
                                "startIndex": paragraph.start_index + span["start"],
                                "endIndex": paragraph.start_index + span["end"],
                            },
                            "textStyle": {"link": span["link"]},
                            "fields": "link",
                        }
                    }
                )
        for offset in range(0, len(link_requests), 400):
            response = (
                service.documents()
                .batchUpdate(
                    documentId=document_id,
                    body={
                        "requests": link_requests[offset : offset + 400],
                        "writeControl": {"requiredRevisionId": required_revision},
                    },
                )
                .execute()
            )
            responses.append(response)
            required_revision = (
                response.get("writeControl", {}).get("requiredRevisionId")
                or service.documents().get(documentId=document_id).execute()["revisionId"]
            )
    after = service.documents().get(documentId=document_id).execute()
    actual = [p.text for p in paragraph_reader(after, plan["lesson"])]
    issues = []
    if actual != plan["expected_after_paragraphs"]:
        issues.append("Rendered lesson paragraphs differ from the approved plan")
    if _document_tail_texts(after, plan["lesson"]) != plan["expected_unchanged_tail"]:
        issues.append("Content after the replaced lesson changed")
    if dict(_link_inventory(after)) != plan["expected_link_inventory"]:
        issues.append("Document link-target inventory differs from the approved plan")
    if _token_inventory(actual) != _token_inventory(plan["expected_after_paragraphs"]):
        issues.append("Protected-token inventory differs from the rendered manifest")
    result = {
        "valid": not issues,
        "before_revision_id": before.get("revisionId"),
        "after_revision_id": after.get("revisionId"),
        "actual_paragraph_count": len(actual),
        "expected_paragraph_count": len(plan["expected_after_paragraphs"]),
        "issues": issues,
        "write_responses": responses,
        "batch_count": len(responses),
    }
    return after, result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace an already-translated lesson from an updated English source."
    )
    parser.add_argument("--source-raw", required=True, type=Path)
    parser.add_argument("--destination-raw", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--lesson", required=True)
    parser.add_argument("--destination-doc-id", required=True)
    parser.add_argument("--allow-doc-id", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--operation-log", type=Path)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path(__file__).parents[2] / "keys" / "lesson_importer_key.json",
    )
    args = parser.parse_args()

    source_document = _read_json(args.source_raw)
    destination_document = _read_json(args.destination_raw)
    completed = _read_json(args.manifest)
    source_manifest = _read_json(args.source_manifest)
    plan = build_replacement_plan(
        source_document,
        destination_document,
        completed,
        source_manifest,
        lesson=args.lesson,
        destination_doc_id=args.destination_doc_id,
        allowed_doc_id=args.allow_doc_id,
    )
    _write_json(args.plan, plan)
    print(
        f"Planned {plan['summary']['replacement_group_count']} replacement groups and "
        f"{plan['summary']['google_request_count']} Google Docs requests."
    )
    if not args.execute:
        return
    if args.operation_log is None:
        raise ValueError("--execute requires --operation-log")
    _, result = execute_replacement_plan(plan, args.credentials)
    result["plan_sha256"] = hashlib.sha256(args.plan.read_bytes()).hexdigest()
    _write_json(args.operation_log, result)
    if not result["valid"]:
        raise SystemExit(f"Write completed but validation failed: {result['issues']!r}")
    print(
        f"Write complete and verified at revision {result['after_revision_id']}; "
        f"{result['actual_paragraph_count']} lesson paragraphs."
    )


if __name__ == "__main__":
    main()

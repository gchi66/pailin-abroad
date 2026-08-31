"""Parse labeled Google Docs speaking-coach content into normalized JSON.

The parser is intentionally independent from the lesson and exercise-bank
parsers. It accepts either a saved Google Docs API response or a document ID,
supports tabbed and legacy documents, and reports structured validation issues.

Usage:
    python -m app.tools.speaking_coach_parser DOCUMENT_ID \
        --all-tabs \
        --output data/speaking_coach.parsed.json

    python -m app.tools.speaking_coach_parser \
        --raw-input data/speaking_coach_raw.json \
        --output data/speaking_coach.parsed.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple


SCHEMA_VERSION = "speaking-coach-parser-v3"
LABEL_RE = re.compile(r"^\s*([A-Z][A-Z0-9_]*):(?:\s*(.*))?$", re.DOTALL)
ANSWER_LABEL_RE = re.compile(r"^ANSWER_(\d+)$")
LESSON_ID_RE = re.compile(r"^\d+\.(?:\d+|CHP)$", re.I)
FOCUS_ITEM_RE = re.compile(r"^\[P([123])\]\s+(.+)$")
FOCUS_MARKER_RE = re.compile(r"^\[[Pp]([^\]]*)\]")

PRACTICE_TYPE_ALIASES = {
    "pronunciation": "pronunciation",
    "repeat": "pronunciation",
    "repeat_after_me": "pronunciation",
    "open": "open",
    "open_ended": "open",
    "open_chp": "open",
    "translate": "translation",
    "translation": "translation",
}

PRACTICE_FIELDS = {"TIP_ENGLISH", "TIP_THAI"}
QUESTION_FIELDS = {
    "FOCUS",
    "REPEAT_ENGLISH",
    "REPEAT_THAI",
    "OPEN_ENGLISH",
    "OPEN_THAI",
    "EXAMPLE_ENGLISH",
    "EXAMPLE_THAI",
    "TRANSLATE_ENGLISH",
    "TRANSLATE_THAI",
    "CHP_ENGLISH",
    "CHP_THAI",
    "FOR_EXAMPLE_ENG",
    "FOR_EXAMPLE_TH",
}

QUESTION_FIELD_ALIASES = {
    "CHP_ENGLISH": "OPEN_ENGLISH",
    "CHP_THAI": "OPEN_THAI",
    "FOR_EXAMPLE_ENG": "EXAMPLE_ENGLISH",
    "FOR_EXAMPLE_TH": "EXAMPLE_THAI",
}


@dataclass
class RichText:
    text: str = ""
    runs: List[Dict[str, Any]] = field(default_factory=list)

    def append(self, other: "RichText", separator: str = "\n") -> None:
        if not other.text:
            return
        if self.text and separator:
            self.text += separator
            self.runs.append({"text": separator})
        self.text += other.text
        self.runs.extend(other.runs)
        self.runs = _merge_runs(self.runs)


@dataclass
class Paragraph:
    rich: RichText
    element_index: int
    paragraph_index: int


@dataclass
class SourceTab:
    tab_id: str
    title: str
    index: int
    path: List[str]
    document_tab: Dict[str, Any]


def _style_run(text: str, style: Dict[str, Any]) -> Dict[str, Any]:
    run: Dict[str, Any] = {"text": text}
    for source, target in (
        ("bold", "bold"),
        ("italic", "italic"),
        ("underline", "underline"),
        ("strikethrough", "strikethrough"),
    ):
        if style.get(source):
            run[target] = True
    link = style.get("link") or {}
    if link.get("url"):
        run["link"] = link["url"]
    return run


def _merge_runs(runs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for original in runs:
        run = {key: value for key, value in original.items() if value is not None}
        text = run.get("text", "")
        if not text:
            continue
        style = {key: value for key, value in run.items() if key != "text"}
        if merged:
            previous_style = {
                key: value for key, value in merged[-1].items() if key != "text"
            }
            if previous_style == style:
                merged[-1]["text"] += text
                continue
        merged.append(run)
    return merged


def _slice_rich(rich: RichText, start: int, end: Optional[int] = None) -> RichText:
    end = len(rich.text) if end is None else end
    if start >= end:
        return RichText()
    output: List[Dict[str, Any]] = []
    cursor = 0
    for run in rich.runs:
        run_text = run.get("text", "")
        run_start = cursor
        run_end = cursor + len(run_text)
        cursor = run_end
        overlap_start = max(start, run_start)
        overlap_end = min(end, run_end)
        if overlap_start >= overlap_end:
            continue
        sliced = dict(run)
        sliced["text"] = run_text[
            overlap_start - run_start : overlap_end - run_start
        ]
        output.append(sliced)
    return RichText(rich.text[start:end], _merge_runs(output))


def _trim_rich(rich: RichText) -> RichText:
    if not rich.text:
        return RichText()
    start = len(rich.text) - len(rich.text.lstrip())
    end = len(rich.text.rstrip())
    return _slice_rich(rich, start, end)


def _rich_from_paragraph(paragraph: Dict[str, Any]) -> RichText:
    runs: List[Dict[str, Any]] = []
    for element in paragraph.get("elements", []) or []:
        text_run = element.get("textRun")
        if text_run:
            text = (text_run.get("content") or "").replace("\u000b", "\n")
            runs.append(_style_run(text, text_run.get("textStyle") or {}))
            continue
        auto_text = element.get("autoText")
        if auto_text and auto_text.get("content"):
            runs.append({"text": auto_text["content"]})
    rich = RichText(
        "".join(run.get("text", "") for run in runs),
        _merge_runs(runs),
    )
    while rich.text.endswith("\n"):
        rich = _slice_rich(rich, 0, len(rich.text) - 1)
    return rich


def _walk_structural_elements(
    elements: Sequence[Dict[str, Any]],
) -> Iterator[Tuple[int, Dict[str, Any]]]:
    """Yield paragraphs, including paragraphs nested in tables and a TOC."""
    for element_index, element in enumerate(elements):
        paragraph = element.get("paragraph")
        if paragraph is not None:
            yield element_index, paragraph
        table = element.get("table")
        if table:
            for row in table.get("tableRows", []) or []:
                for cell in row.get("tableCells", []) or []:
                    yield from _walk_structural_elements(cell.get("content", []) or [])
        toc = element.get("tableOfContents")
        if toc:
            yield from _walk_structural_elements(toc.get("content", []) or [])


def _paragraphs(document_tab: Dict[str, Any]) -> List[Paragraph]:
    body = (document_tab.get("body") or {}).get("content", []) or []
    result: List[Paragraph] = []
    for paragraph_index, (element_index, paragraph) in enumerate(
        _walk_structural_elements(body)
    ):
        result.append(
            Paragraph(
                rich=_rich_from_paragraph(paragraph),
                element_index=element_index,
                paragraph_index=paragraph_index,
            )
        )
    return result


def _walk_tabs(
    tabs: Sequence[Dict[str, Any]],
    parent_path: Optional[List[str]] = None,
) -> Iterator[SourceTab]:
    parent_path = parent_path or []
    for fallback_index, tab in enumerate(tabs):
        properties = tab.get("tabProperties") or {}
        title = str(properties.get("title") or f"Tab {fallback_index + 1}")
        path = [*parent_path, title]
        document_tab = tab.get("documentTab")
        if document_tab is not None:
            yield SourceTab(
                tab_id=str(properties.get("tabId") or ""),
                title=title,
                index=int(properties.get("index", fallback_index)),
                path=path,
                document_tab=document_tab,
            )
        yield from _walk_tabs(tab.get("childTabs", []) or [], path)


def _source_tabs(document: Dict[str, Any]) -> List[SourceTab]:
    if document.get("tabs"):
        return list(_walk_tabs(document["tabs"]))
    if document.get("body"):
        title = str(document.get("title") or "Document")
        return [
            SourceTab(
                tab_id="legacy-first-tab",
                title=title,
                index=0,
                path=[title],
                document_tab=document,
            )
        ]
    return []


def _hash_key(*parts: Any) -> str:
    canonical = "|".join(str(part) for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _plain_rich(text: str) -> RichText:
    return RichText(text=text, runs=[{"text": text}] if text else [])


class SpeakingCoachParser:
    def __init__(self) -> None:
        self.document_id = ""
        self.issues: List[Dict[str, Any]] = []

    def _issue(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        tab: Optional[SourceTab] = None,
        lesson_external_id: Optional[str] = None,
        practice_type: Optional[str] = None,
        question_number: Optional[str] = None,
        paragraph_index: Optional[int] = None,
    ) -> None:
        location: Dict[str, Any] = {}
        if tab:
            location.update(
                {
                    "tab_id": tab.tab_id,
                    "tab_title": tab.title,
                    "tab_path": tab.path,
                }
            )
        if lesson_external_id is not None:
            location["lesson_external_id"] = lesson_external_id
        if practice_type is not None:
            location["practice_type"] = practice_type
        if question_number is not None:
            location["question_number"] = question_number
        if paragraph_index is not None:
            location["paragraph_index"] = paragraph_index
        self.issues.append(
            {
                "severity": severity,
                "code": code,
                "message": message,
                "location": location,
            }
        )

    def parse(self, document: Dict[str, Any]) -> Dict[str, Any]:
        self.document_id = str(document.get("documentId") or "")
        self.issues = []
        tabs = _source_tabs(document)
        if not tabs:
            self._issue(
                "error",
                "missing_document_content",
                "Document contains neither tabs nor a legacy body.",
            )

        lessons: List[Dict[str, Any]] = []
        for tab in tabs:
            lessons.extend(self._parse_tab(tab, len(lessons)))

        seen_lessons: Dict[str, Dict[str, Any]] = {}
        for lesson in lessons:
            lesson_id = lesson["lesson_external_id"]
            if lesson_id in seen_lessons:
                source = lesson["source"]
                self._issue(
                    "error",
                    "duplicate_lesson",
                    f"Lesson {lesson_id} appears more than once in the document.",
                    lesson_external_id=lesson_id,
                    paragraph_index=source["paragraph_index"],
                )
            else:
                seen_lessons[lesson_id] = lesson

        practice_sets = [
            practice
            for lesson in lessons
            for practice in lesson["practice_sets"]
        ]
        questions = [
            question
            for practice in practice_sets
            for question in practice["questions"]
        ]
        practice_types: Dict[str, int] = {}
        for practice in practice_sets:
            practice_type = practice["practice_type"] or "unknown"
            practice_types[practice_type] = practice_types.get(practice_type, 0) + 1

        error_count = sum(issue["severity"] == "error" for issue in self.issues)
        warning_count = sum(issue["severity"] == "warning" for issue in self.issues)
        return {
            "schema_version": SCHEMA_VERSION,
            "document": {
                "document_id": self.document_id or None,
                "title": document.get("title"),
                "tab_count": len(tabs),
            },
            "summary": {
                "lesson_count": len(lessons),
                "practice_set_count": len(practice_sets),
                "question_count": len(questions),
                "error_count": error_count,
                "warning_count": warning_count,
                "practice_types": dict(sorted(practice_types.items())),
            },
            "lessons": lessons,
            "issues": self.issues,
        }

    def _parse_tab(self, tab: SourceTab, lesson_offset: int) -> List[Dict[str, Any]]:
        lessons: List[Dict[str, Any]] = []
        current_lesson: Optional[Dict[str, Any]] = None
        current_practice: Optional[Dict[str, Any]] = None
        current_question: Optional[Dict[str, Any]] = None
        pending_field: Optional[Tuple[str, str]] = None
        practice_type_occurrences: Dict[str, int] = {}

        def context() -> Dict[str, Optional[str]]:
            return {
                "lesson_external_id": (
                    current_lesson.get("lesson_external_id")
                    if current_lesson
                    else None
                ),
                "practice_type": (
                    current_practice.get("practice_type")
                    if current_practice
                    else None
                ),
                "question_number": (
                    current_question.get("source_number")
                    if current_question
                    else None
                ),
            }

        def flush_question() -> None:
            nonlocal current_question, pending_field
            if current_question is None:
                return
            if current_practice is None:
                current_question = None
                pending_field = None
                return
            question = self._finalize_question(current_question, current_practice, tab)
            current_practice["questions"].append(question)
            current_question = None
            pending_field = None

        def flush_practice() -> None:
            nonlocal current_practice, current_question, pending_field
            flush_question()
            if current_practice is None:
                return
            self._finalize_practice(current_practice, tab)
            if current_lesson is not None:
                current_lesson["practice_sets"].append(current_practice)
            current_practice = None
            current_question = None
            pending_field = None

        def flush_lesson() -> None:
            nonlocal current_lesson, current_practice, current_question
            nonlocal pending_field, practice_type_occurrences
            flush_practice()
            if current_lesson is None:
                return
            self._validate_lesson(current_lesson, tab)
            lessons.append(current_lesson)
            current_lesson = None
            current_practice = None
            current_question = None
            pending_field = None
            practice_type_occurrences = {}

        for paragraph in _paragraphs(tab.document_tab):
            rich = _trim_rich(paragraph.rich)
            text = rich.text
            if not text:
                continue

            label_match = LABEL_RE.match(text)
            if label_match:
                label = label_match.group(1)
                value_start = (
                    label_match.start(2)
                    if label_match.group(2) is not None
                    else len(text)
                )
                value_rich = _trim_rich(_slice_rich(rich, value_start))
                value = value_rich.text

                if label == "LESSON":
                    flush_lesson()
                    lesson_id = value.strip()
                    if re.match(r"^\d+\.chp$", lesson_id, re.I):
                        lesson_id = lesson_id.lower()
                    lesson_order = lesson_offset + len(lessons) + 1
                    current_lesson = {
                        "source_key": _hash_key(
                            self.document_id,
                            "lesson",
                            lesson_id,
                        ),
                        "lesson_external_id": lesson_id,
                        "sort_order": lesson_order,
                        "source": {
                            "document_id": self.document_id or None,
                            "tab_id": tab.tab_id,
                            "tab_title": tab.title,
                            "tab_path": tab.path,
                            "tab_order": tab.index + 1,
                            "paragraph_index": paragraph.paragraph_index,
                        },
                        "practice_sets": [],
                    }
                    practice_type_occurrences = {}
                    pending_field = None
                    continue

                if label == "PRACTICE_TYPE":
                    flush_practice()
                    if current_lesson is None:
                        self._issue(
                            "error",
                            "practice_before_lesson",
                            "PRACTICE_TYPE appeared before LESSON.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                        )
                        continue
                    source_type = value.strip().lower().replace("-", "_").replace(" ", "_")
                    practice_type = PRACTICE_TYPE_ALIASES.get(source_type, source_type)
                    occurrence = practice_type_occurrences.get(practice_type, 0) + 1
                    practice_type_occurrences[practice_type] = occurrence
                    lesson_key = current_lesson["source_key"]
                    current_practice = {
                        "source_key": _hash_key(
                            lesson_key,
                            "practice",
                            practice_type,
                            occurrence,
                        ),
                        "lesson_source_key": lesson_key,
                        "practice_type": practice_type,
                        "source_practice_type": value.strip(),
                        "sort_order": len(current_lesson["practice_sets"]) + 1,
                        "focus": None,
                        "focus_runs": [],
                        "tip": {"en": None, "th": None},
                        "tip_runs": {"en": [], "th": []},
                        "source": {
                            "document_id": self.document_id or None,
                            "tab_id": tab.tab_id,
                            "tab_title": tab.title,
                            "tab_path": tab.path,
                            "tab_order": tab.index + 1,
                            "lesson_external_id": current_lesson["lesson_external_id"],
                            "practice_occurrence": occurrence,
                            "paragraph_index": paragraph.paragraph_index,
                        },
                        "questions": [],
                        "_rich_fields": {},
                    }
                    pending_field = None
                    continue

                if label in PRACTICE_FIELDS:
                    if current_practice is None:
                        self._issue(
                            "warning",
                            "orphan_practice_field",
                            f"Ignored {label} before PRACTICE_TYPE.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                        pending_field = None
                        continue
                    field_name = {
                        "FOCUS": "focus",
                        "TIP_ENGLISH": "tip_en",
                        "TIP_THAI": "tip_th",
                    }[label]
                    if field_name in current_practice["_rich_fields"]:
                        self._issue(
                            "warning",
                            "duplicate_practice_field",
                            f"Appended duplicate {label} field.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                        current_practice["_rich_fields"][field_name].append(value_rich)
                    else:
                        if field_name == "focus" and re.match(r"^FOCUS\s*:", value, re.I):
                            cleaned = re.sub(r"^FOCUS\s*:\s*", "", value, count=1, flags=re.I)
                            value_rich = _plain_rich(cleaned)
                            self._issue(
                                "warning",
                                "duplicate_focus_prefix",
                                "Removed a repeated FOCUS prefix from the field value.",
                                tab=tab,
                                paragraph_index=paragraph.paragraph_index,
                                **context(),
                            )
                        current_practice["_rich_fields"][field_name] = value_rich
                    pending_field = ("practice", field_name)
                    continue

                if label == "FOCUS":
                    if re.match(r"^FOCUS\s*:", value, re.I):
                        cleaned = re.sub(
                            r"^FOCUS\s*:\s*", "", value, count=1, flags=re.I
                        )
                        value_rich = _plain_rich(cleaned)
                        self._issue(
                            "warning",
                            "duplicate_focus_prefix",
                            "Removed a repeated FOCUS prefix from the field value.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                    if current_question is not None:
                        if label in current_question["fields"]:
                            self._issue(
                                "warning",
                                "duplicate_question_field",
                                "Appended duplicate FOCUS field.",
                                tab=tab,
                                paragraph_index=paragraph.paragraph_index,
                                **context(),
                            )
                            current_question["fields"][label].append(value_rich)
                        else:
                            current_question["fields"][label] = value_rich
                        pending_field = ("question", label)
                        continue
                    if current_practice is not None:
                        if "focus" in current_practice["_rich_fields"]:
                            self._issue(
                                "warning",
                                "duplicate_practice_field",
                                "Appended duplicate FOCUS field.",
                                tab=tab,
                                paragraph_index=paragraph.paragraph_index,
                                **context(),
                            )
                            current_practice["_rich_fields"]["focus"].append(value_rich)
                        else:
                            current_practice["_rich_fields"]["focus"] = value_rich
                        pending_field = ("practice", "focus")
                        continue
                    self._issue(
                        "warning",
                        "orphan_practice_field",
                        "Ignored FOCUS before PRACTICE_TYPE or QUESTION.",
                        tab=tab,
                        paragraph_index=paragraph.paragraph_index,
                        **context(),
                    )
                    pending_field = None
                    continue

                if label == "QUESTION":
                    flush_question()
                    if current_practice is None:
                        self._issue(
                            "error",
                            "question_before_practice",
                            "QUESTION appeared before PRACTICE_TYPE.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                        continue
                    current_question = {
                        "source_number": value.strip(),
                        "sort_order": len(current_practice["questions"]) + 1,
                        "paragraph_index": paragraph.paragraph_index,
                        "fields": {},
                        "answers": {},
                    }
                    pending_field = None
                    continue

                answer_match = ANSWER_LABEL_RE.match(label)
                if label in QUESTION_FIELDS or answer_match:
                    if current_question is None:
                        self._issue(
                            "warning",
                            "orphan_question_field",
                            f"Ignored {label} before QUESTION.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                        pending_field = None
                        continue
                    if answer_match:
                        answer_index = int(answer_match.group(1))
                        if answer_index < 1:
                            self._issue(
                                "error",
                                "invalid_answer_number",
                                f"{label} must use an index of 1 or greater.",
                                tab=tab,
                                paragraph_index=paragraph.paragraph_index,
                                **context(),
                            )
                        if answer_index in current_question["answers"]:
                            self._issue(
                                "error",
                                "duplicate_answer_number",
                                f"{label} appears more than once.",
                                tab=tab,
                                paragraph_index=paragraph.paragraph_index,
                                **context(),
                            )
                            current_question["answers"][answer_index].append(value_rich)
                        else:
                            current_question["answers"][answer_index] = value_rich
                        pending_field = ("answer", str(answer_index))
                        continue

                    canonical_label = QUESTION_FIELD_ALIASES.get(label, label)
                    if canonical_label in current_question["fields"]:
                        self._issue(
                            "warning",
                            "duplicate_question_field",
                            f"Appended duplicate {label} field.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                            **context(),
                        )
                        current_question["fields"][canonical_label].append(value_rich)
                    else:
                        current_question["fields"][canonical_label] = value_rich
                    pending_field = ("question", canonical_label)
                    continue

                self._issue(
                    "warning",
                    "unknown_label",
                    f"Unrecognized field label {label}.",
                    tab=tab,
                    paragraph_index=paragraph.paragraph_index,
                    **context(),
                )
                pending_field = None
                continue

            if pending_field is not None:
                scope, field_name = pending_field
                if scope == "practice" and current_practice is not None:
                    current_practice["_rich_fields"][field_name].append(rich)
                elif scope == "question" and current_question is not None:
                    current_question["fields"][field_name].append(rich)
                elif scope == "answer" and current_question is not None:
                    current_question["answers"][int(field_name)].append(rich)
                continue

            self._issue(
                "warning",
                "unrecognized_text",
                "Ignored text that was not attached to a labeled field.",
                tab=tab,
                paragraph_index=paragraph.paragraph_index,
                **context(),
            )

        flush_lesson()
        return lessons

    def _finalize_practice(
        self,
        practice: Dict[str, Any],
        tab: SourceTab,
    ) -> None:
        rich_fields = practice.pop("_rich_fields")
        focus = rich_fields.get("focus") or RichText()
        tip_en = rich_fields.get("tip_en") or RichText()
        tip_th = rich_fields.get("tip_th") or RichText()
        practice["focus"] = focus.text or None
        practice["focus_runs"] = focus.runs
        practice["focus_items"] = self._parse_focus_items(
            practice["focus"],
            tab=tab,
            lesson_external_id=practice["source"]["lesson_external_id"],
            practice_type=practice["practice_type"],
            question_number=None,
            paragraph_index=practice["source"]["paragraph_index"],
            allow_legacy_unranked=True,
        )
        practice["tip"] = {
            "en": tip_en.text or None,
            "th": tip_th.text or None,
        }
        practice["tip_runs"] = {
            "en": tip_en.runs,
            "th": tip_th.runs,
        }
        self._validate_practice(practice, tab)

    def _finalize_question(
        self,
        question: Dict[str, Any],
        practice: Dict[str, Any],
        tab: SourceTab,
    ) -> Dict[str, Any]:
        fields: Dict[str, RichText] = question["fields"]
        answers: Dict[int, RichText] = question["answers"]
        answer_indexes = sorted(answers)
        accepted_answers = [answers[index].text for index in answer_indexes if answers[index].text]
        question_focus = (fields.get("FOCUS") or RichText()).text or None
        question_focus_runs = (fields.get("FOCUS") or RichText()).runs
        inherited_legacy_focus = False
        if question_focus is None:
            legacy_focus = practice.get("_rich_fields", {}).get("focus") or RichText()
            question_focus = legacy_focus.text or None
            question_focus_runs = legacy_focus.runs
            inherited_legacy_focus = question_focus is not None

        focus_items = self._parse_focus_items(
            question_focus,
            tab=tab,
            lesson_external_id=practice["source"]["lesson_external_id"],
            practice_type=practice["practice_type"],
            question_number=question["source_number"],
            paragraph_index=question["paragraph_index"],
            allow_legacy_unranked=inherited_legacy_focus,
        )

        practice_type = practice["practice_type"]
        if practice_type == "pronunciation":
            prompt_en = (fields.get("REPEAT_ENGLISH") or RichText()).text
            prompt_th = (fields.get("REPEAT_THAI") or RichText()).text
            target_answers = [prompt_en] if prompt_en else []
            examples: List[Dict[str, Optional[str]]] = []
        elif practice_type == "open":
            prompt_en = (fields.get("OPEN_ENGLISH") or RichText()).text
            prompt_th = (fields.get("OPEN_THAI") or RichText()).text
            target_answers = []
            example_en = (fields.get("EXAMPLE_ENGLISH") or RichText()).text or None
            example_th = (fields.get("EXAMPLE_THAI") or RichText()).text or None
            examples = (
                [{"en": example_en, "th": example_th}]
                if example_en or example_th
                else []
            )
        elif practice_type == "translation":
            prompt_en = (fields.get("TRANSLATE_ENGLISH") or RichText()).text
            prompt_th = (fields.get("TRANSLATE_THAI") or RichText()).text
            target_answers = accepted_answers
            examples = []
        else:
            prompt_en = ""
            prompt_th = ""
            target_answers = accepted_answers
            examples = []

        source_number = question["source_number"]
        result = {
            "source_key": _hash_key(
                practice["source_key"],
                "question",
                source_number,
            ),
            "practice_set_source_key": practice["source_key"],
            "source_number": source_number,
            "sort_order": question["sort_order"],
            "prompt": {
                "en": prompt_en or None,
                "th": prompt_th or None,
            },
            "target_answers": target_answers,
            "examples": examples,
            "focus": question_focus,
            "focus_runs": question_focus_runs,
            "focus_items": focus_items,
            "source": {
                "paragraph_index": question["paragraph_index"],
            },
        }
        self._validate_question(result, fields, answer_indexes, practice, tab)
        return result

    def _parse_focus_items(
        self,
        focus: Optional[str],
        *,
        tab: SourceTab,
        lesson_external_id: Optional[str],
        practice_type: Optional[str],
        question_number: Optional[str],
        paragraph_index: Optional[int],
        allow_legacy_unranked: bool,
    ) -> List[Dict[str, Any]]:
        if not focus:
            return []

        lines = [line.strip() for line in focus.splitlines() if line.strip()]
        ranked_items: List[Dict[str, Any]] = []
        unranked_lines: List[str] = []
        invalid_marker = False

        for line in lines:
            item_match = FOCUS_ITEM_RE.match(line)
            if item_match:
                ranked_items.append(
                    {
                        "priority": int(item_match.group(1)),
                        "instruction": item_match.group(2).strip(),
                    }
                )
                continue

            marker_match = FOCUS_MARKER_RE.match(line)
            if marker_match:
                invalid_marker = True
                marker = marker_match.group(0)
                code = (
                    "empty_focus_instruction"
                    if marker in {"[P1]", "[P2]", "[P3]"}
                    else "invalid_focus_priority"
                )
                message = (
                    f"{marker} must be followed by a non-empty instruction."
                    if code == "empty_focus_instruction"
                    else f"Focus priority {marker!r} must be [P1], [P2], or [P3]."
                )
                self._issue(
                    "error",
                    code,
                    message,
                    tab=tab,
                    lesson_external_id=lesson_external_id,
                    practice_type=practice_type,
                    question_number=question_number,
                    paragraph_index=paragraph_index,
                )
                continue

            unranked_lines.append(line)

        if ranked_items and unranked_lines:
            self._issue(
                "error",
                "mixed_ranked_unranked_focus",
                "Every paragraph in a ranked FOCUS must begin with [P1], [P2], or [P3].",
                tab=tab,
                lesson_external_id=lesson_external_id,
                practice_type=practice_type,
                question_number=question_number,
                paragraph_index=paragraph_index,
            )
            return ranked_items

        if ranked_items or invalid_marker:
            return ranked_items

        instruction = "\n".join(unranked_lines).strip()
        if not instruction:
            return []
        if allow_legacy_unranked:
            return [{"priority": 1, "instruction": instruction}]

        self._issue(
            "error",
            "unranked_question_focus",
            "Question-level FOCUS items must begin with [P1], [P2], or [P3].",
            tab=tab,
            lesson_external_id=lesson_external_id,
            practice_type=practice_type,
            question_number=question_number,
            paragraph_index=paragraph_index,
        )
        return [{"priority": 1, "instruction": instruction}]

    def _validate_lesson(self, lesson: Dict[str, Any], tab: SourceTab) -> None:
        lesson_id = lesson["lesson_external_id"]
        if not lesson_id:
            self._issue(
                "error",
                "missing_lesson_id",
                "LESSON must have a value.",
                tab=tab,
                paragraph_index=lesson["source"]["paragraph_index"],
            )
        elif not LESSON_ID_RE.match(lesson_id):
            self._issue(
                "warning",
                "unexpected_lesson_id",
                f"Lesson identifier {lesson_id!r} does not match X.Y.",
                tab=tab,
                lesson_external_id=lesson_id,
                paragraph_index=lesson["source"]["paragraph_index"],
            )
        if not lesson["practice_sets"]:
            self._issue(
                "error",
                "lesson_without_practice_sets",
                "Lesson has no speaking practice sets.",
                tab=tab,
                lesson_external_id=lesson_id,
            )

    def _validate_practice(self, practice: Dict[str, Any], tab: SourceTab) -> None:
        lesson_id = practice["source"]["lesson_external_id"]
        practice_type = practice["practice_type"]
        if practice_type not in set(PRACTICE_TYPE_ALIASES.values()):
            self._issue(
                "error",
                "unsupported_practice_type",
                f"Unsupported practice type: {practice_type or '<empty>'}.",
                tab=tab,
                lesson_external_id=lesson_id,
                practice_type=practice_type,
                paragraph_index=practice["source"]["paragraph_index"],
            )
        if not practice["questions"]:
            self._issue(
                "error",
                "practice_without_questions",
                "Speaking practice set has no questions.",
                tab=tab,
                lesson_external_id=lesson_id,
                practice_type=practice_type,
            )

        seen_numbers: set[str] = set()
        for question in practice["questions"]:
            number = question["source_number"]
            if number in seen_numbers:
                self._issue(
                    "error",
                    "duplicate_question_number",
                    f"Question number {number!r} appears more than once in this practice set.",
                    tab=tab,
                    lesson_external_id=lesson_id,
                    practice_type=practice_type,
                    question_number=number,
                    paragraph_index=question["source"]["paragraph_index"],
                )
            seen_numbers.add(number)

    def _validate_question(
        self,
        question: Dict[str, Any],
        fields: Dict[str, RichText],
        answer_indexes: List[int],
        practice: Dict[str, Any],
        tab: SourceTab,
    ) -> None:
        lesson_id = practice["source"]["lesson_external_id"]
        practice_type = practice["practice_type"]
        number = question["source_number"]
        paragraph_index = question["source"]["paragraph_index"]

        def missing(label: str) -> None:
            self._issue(
                "error",
                "missing_required_question_field",
                f"Question is missing required {label}.",
                tab=tab,
                lesson_external_id=lesson_id,
                practice_type=practice_type,
                question_number=number,
                paragraph_index=paragraph_index,
            )

        if not question.get("focus"):
            missing("FOCUS")

        if not number:
            missing("QUESTION number")
        if practice_type == "pronunciation":
            for label in ("REPEAT_ENGLISH", "REPEAT_THAI"):
                if not (fields.get(label) or RichText()).text:
                    missing(label)
        elif practice_type == "open":
            for label in (
                "OPEN_ENGLISH",
                "OPEN_THAI",
                "EXAMPLE_ENGLISH",
                "EXAMPLE_THAI",
            ):
                if not (fields.get(label) or RichText()).text:
                    missing(label)
        elif practice_type == "translation":
            if not (fields.get("TRANSLATE_THAI") or RichText()).text:
                missing("TRANSLATE_THAI")
            if not answer_indexes:
                missing("ANSWER_n")
            elif answer_indexes != list(range(1, max(answer_indexes) + 1)):
                self._issue(
                    "warning",
                    "non_contiguous_answer_numbers",
                    "Translation ANSWER_n fields are not numbered contiguously from 1.",
                    tab=tab,
                    lesson_external_id=lesson_id,
                    practice_type=practice_type,
                    question_number=number,
                    paragraph_index=paragraph_index,
                )


def parse_document(document: Dict[str, Any]) -> Dict[str, Any]:
    return SpeakingCoachParser().parse(document)


def parse_file(path: str | Path) -> Dict[str, Any]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        return parse_document(json.load(handle))


def select_document_tab(document: Dict[str, Any], tab_title: str) -> Dict[str, Any]:
    """Return a document containing only the uniquely named Google Docs tab."""
    requested = tab_title.strip().casefold()
    matches: List[Dict[str, Any]] = []

    def collect(tabs: Sequence[Dict[str, Any]]) -> None:
        for tab in tabs:
            properties = tab.get("tabProperties") or {}
            title = str(properties.get("title") or "").strip()
            if title.casefold() == requested:
                matches.append(tab)
            collect(tab.get("childTabs", []) or [])

    collect(document.get("tabs", []) or [])
    if not matches:
        raise ValueError(f"Google Docs tab {tab_title!r} was not found.")
    if len(matches) > 1:
        raise ValueError(
            f"Google Docs tab title {tab_title!r} is not unique; "
            f"found {len(matches)} matches."
        )
    return {**document, "tabs": [matches[0]]}


def fetch_and_parse(
    document_id: str,
    *,
    include_tabs_content: bool = False,
    tab_title: str | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    try:
        from .docs_fetch import fetch_doc
    except ImportError:  # pragma: no cover - direct script fallback
        from app.tools.docs_fetch import fetch_doc  # type: ignore

    document = fetch_doc(document_id, include_tabs_content=include_tabs_content)
    if not document:
        raise RuntimeError(f"Failed to fetch Google document {document_id}")
    selected_document = (
        select_document_tab(document, tab_title) if tab_title else document
    )
    return document, parse_document(selected_document)


def main(argv: Optional[Sequence[str]] = None) -> int:
    argument_parser = argparse.ArgumentParser(
        description="Fetch and parse a labeled Google Docs speaking-coach document."
    )
    argument_parser.add_argument(
        "document_id",
        nargs="?",
        help="Google Docs document ID",
    )
    argument_parser.add_argument(
        "--output",
        help="Write parsed JSON here (default: stdout)",
    )
    argument_parser.add_argument(
        "--all-tabs",
        action="store_true",
        help="Fetch and parse all Google Docs tabs",
    )
    argument_parser.add_argument(
        "--tab-title",
        help="Fetch all tab content but parse only the uniquely named tab",
    )
    argument_parser.add_argument(
        "--raw-input",
        help="Parse a saved Google Docs JSON response instead of fetching",
    )
    argument_parser.add_argument(
        "--raw-output",
        help="Save the fetched Google Docs response here",
    )
    argument_parser.add_argument(
        "--allow-errors",
        action="store_true",
        help="Exit successfully even when validation errors are present",
    )
    args = argument_parser.parse_args(argv)

    try:
        if args.raw_input:
            if args.document_id:
                argument_parser.error(
                    "document_id and --raw-input cannot be used together"
                )
            raw_document = None
            result = parse_file(args.raw_input)
        else:
            if not args.document_id:
                argument_parser.error(
                    "document_id is required unless --raw-input is provided"
                )
            raw_document, result = fetch_and_parse(
                args.document_id,
                include_tabs_content=args.all_tabs or bool(args.tab_title),
                tab_title=args.tab_title,
            )
            if args.raw_output:
                raw_output_path = Path(args.raw_output)
                raw_output_path.parent.mkdir(parents=True, exist_ok=True)
                raw_output_path.write_text(
                    json.dumps(raw_document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(
                    "[speaking_coach_parser] "
                    f"wrote raw Google Docs JSON to {raw_output_path}"
                )
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError) as error:
        print(f"[speaking_coach_parser] {error}", file=sys.stderr)
        return 2

    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
        print(
            "[speaking_coach_parser] "
            f"wrote {result['summary']['lesson_count']} lessons, "
            f"{result['summary']['practice_set_count']} practice sets, and "
            f"{result['summary']['question_count']} questions to {output_path}"
        )
    else:
        print(serialized)

    summary = result["summary"]
    print(
        "[speaking_coach_parser] "
        f"{summary['error_count']} errors, "
        f"{summary['warning_count']} warnings",
        file=sys.stderr,
    )
    if summary["error_count"] and not args.allow_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

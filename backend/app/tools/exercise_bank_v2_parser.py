"""Parse an all-tabs Google Docs exercise bank into import-ready JSON.

This parser is intentionally independent from the legacy exercise-bank and lesson
parsers. It fetches a Google Doc and emits parent exercise records with one child
record per question. Saved raw JSON remains available as an optional debugging input.

Usage:
    python -m app.tools.exercise_bank_v2_parser DOCUMENT_ID \
        --all-tabs \
        --output data/exercise_bank.parsed.json
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


SUPPORTED_TYPES = {"fill_blank", "multiple_choice", "sentence_transform"}
TOPIC_FIELDS = {
    "TOPIC": "topic",
    "DISPLAY_TITLE": "display_title",
    "CATEGORY": "category",
    "SUB_CATEGORY": "sub_category",
    "DIFFICULTY": "difficulty",
    "LESSON": "lesson",
}
REQUIRED_TOPIC_FIELDS = {"topic", "display_title", "category", "lesson"}
REQUIRED_EXERCISE_FIELDS = {"exercise_type", "display_type", "prompt"}
LABEL_RE = re.compile(r"^\s*([A-Z][A-Z_]*):(?:\s*(.*))?$", re.DOTALL)
OPTION_RE = re.compile(r"^\s*([A-Z])\.\s*(.+?)\s*$", re.DOTALL)
BLANK_RE = re.compile(r"_+")


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
    text: str
    runs: List[Dict[str, Any]]
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
    foreground = (style.get("foregroundColor") or {}).get("color") or {}
    rgb = foreground.get("rgbColor")
    if rgb:
        run["color"] = rgb
    background = (style.get("backgroundColor") or {}).get("color") or {}
    rgb_background = background.get("rgbColor")
    if rgb_background:
        run["background_color"] = rgb_background
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


def _trim_rich(rich: RichText) -> RichText:
    if not rich.text:
        return RichText()
    left = len(rich.text) - len(rich.text.lstrip())
    right = len(rich.text.rstrip())
    return _slice_rich(rich, left, right)


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
    """Yield paragraphs, including paragraphs nested in Google Docs tables."""
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
    result: List[Paragraph] = []
    body = (document_tab.get("body") or {}).get("content", []) or []
    for paragraph_index, (element_index, paragraph) in enumerate(
        _walk_structural_elements(body)
    ):
        rich = _rich_from_paragraph(paragraph)
        result.append(
            Paragraph(
                text=rich.text,
                runs=rich.runs,
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
        return [
            SourceTab(
                tab_id="legacy-first-tab",
                title=str(document.get("title") or "Document"),
                index=0,
                path=[str(document.get("title") or "Document")],
                document_tab=document,
            )
        ]
    return []


def _hash_key(*parts: Any) -> str:
    canonical = "|".join(str(part) for part in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _parse_bool(value: str) -> Optional[bool]:
    normalized = value.strip().lower()
    if normalized in {"yes", "true"}:
        return True
    if normalized in {"no", "false"}:
        return False
    return None


def _accepted_answers(raw_answers: Sequence[str]) -> List[str]:
    answers: List[str] = []
    for raw in raw_answers:
        for part in re.split(r"\s*,\s*", raw.strip()):
            if part and part not in answers:
                answers.append(part)
    return answers


class ExerciseBankParser:
    def __init__(self) -> None:
        self.issues: List[Dict[str, Any]] = []
        self.document_id = ""

    def _issue(
        self,
        severity: str,
        code: str,
        message: str,
        *,
        tab: Optional[SourceTab] = None,
        exercise_order: Optional[int] = None,
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
        if exercise_order is not None:
            location["exercise_order"] = exercise_order
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
        self.issues = []
        self.document_id = str(document.get("documentId") or "")
        tabs = _source_tabs(document)
        if not tabs:
            self._issue(
                "error",
                "missing_document_content",
                "Document contains neither tabs nor a legacy body.",
            )

        exercises: List[Dict[str, Any]] = []
        for tab in tabs:
            exercises.extend(self._parse_tab(tab))

        topics = self._build_topics(exercises)
        question_count = sum(len(exercise["questions"]) for exercise in exercises)
        example_count = sum(
            1
            for exercise in exercises
            for question in exercise["questions"]
            if question["is_example"]
        )
        gradable_count = question_count - example_count
        errors = sum(issue["severity"] == "error" for issue in self.issues)
        warnings = sum(issue["severity"] == "warning" for issue in self.issues)

        return {
            "document": {
                "document_id": self.document_id or None,
                "title": document.get("title"),
                "tab_count": len(tabs),
            },
            "summary": {
                "topic_count": len(topics),
                "exercise_count": len(exercises),
                "question_count": question_count,
                "gradable_question_count": gradable_count,
                "example_count": example_count,
                "error_count": errors,
                "warning_count": warnings,
                "exercise_types": self._type_counts(exercises),
            },
            "topics": topics,
            "exercises": exercises,
            "issues": self.issues,
        }

    @staticmethod
    def _type_counts(exercises: Sequence[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for exercise in exercises:
            kind = exercise.get("exercise_type") or "unknown"
            counts[kind] = counts.get(kind, 0) + 1
        return dict(sorted(counts.items()))

    def _build_topics(
        self,
        exercises: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        topics: List[Dict[str, Any]] = []
        by_source_key: Dict[str, Dict[str, Any]] = {}
        comparable_fields = (
            "topic",
            "display_title",
            "category",
            "sub_category",
            "lesson_external_id",
        )

        for exercise in exercises:
            source = exercise["source"]
            topic = {
                "source_key": exercise["topic_source_key"],
                "source_document_id": source["document_id"],
                "source_tab_id": source["tab_id"],
                "source_tab_title": source["tab_title"],
                "source_tab_order": source["tab_order"],
                "topic": exercise.get("topic"),
                "display_title": exercise.get("display_title"),
                "category": exercise.get("category"),
                "sub_category": exercise.get("sub_category"),
                "lesson_external_id": exercise.get("lesson"),
                "sort_order": source["tab_order"],
            }
            existing = by_source_key.get(topic["source_key"])
            if existing is None:
                by_source_key[topic["source_key"]] = topic
                topics.append(topic)
                continue

            differences = [
                field_name
                for field_name in comparable_fields
                if existing.get(field_name) != topic.get(field_name)
            ]
            if differences:
                self._issue(
                    "error",
                    "conflicting_topic_metadata",
                    (
                        "Exercises in the same source tab have conflicting topic "
                        f"metadata: {', '.join(differences)}."
                    ),
                    exercise_order=source["exercise_order"],
                )

        return topics

    def _parse_tab(self, tab: SourceTab) -> List[Dict[str, Any]]:
        metadata: Dict[str, Optional[str]] = {
            "topic": None,
            "display_title": None,
            "category": None,
            "sub_category": None,
            "difficulty": None,
            "lesson": None,
        }
        exercises: List[Dict[str, Any]] = []
        current_exercise: Optional[Dict[str, Any]] = None
        current_question: Optional[Dict[str, Any]] = None
        pending_field: Optional[str] = None
        exercise_order = 0

        def flush_question() -> None:
            nonlocal current_question, pending_field
            if current_question is None:
                return
            if current_exercise is None:
                current_question = None
                pending_field = None
                return
            question = self._finalize_question(
                current_question,
                current_exercise,
                tab,
            )
            current_exercise["questions"].append(question)
            current_question = None
            pending_field = None

        def flush_exercise() -> None:
            nonlocal current_exercise, current_question, pending_field
            flush_question()
            if current_exercise is None:
                return
            self._validate_exercise(current_exercise, tab)
            exercises.append(current_exercise)
            current_exercise = None
            current_question = None
            pending_field = None

        for paragraph in _paragraphs(tab.document_tab):
            rich = _trim_rich(RichText(paragraph.text, paragraph.runs))
            text = rich.text
            if not text:
                continue

            label_match = LABEL_RE.match(text)
            if label_match:
                label = label_match.group(1)
                value_start = label_match.start(2) if label_match.group(2) is not None else len(text)
                value_rich = _trim_rich(_slice_rich(rich, value_start))
                value = value_rich.text

                if label in TOPIC_FIELDS:
                    flush_exercise()
                    metadata[TOPIC_FIELDS[label]] = value or None
                    pending_field = None
                    continue

                if label == "TYPE":
                    flush_exercise()
                    exercise_order += 1
                    current_exercise = self._new_exercise(
                        tab,
                        exercise_order,
                        metadata,
                        value,
                        paragraph.paragraph_index,
                    )
                    pending_field = None
                    continue

                if current_exercise is None:
                    if label not in {"QUESTION", "ITEM", "TEXT", "STEM", "ANSWER"}:
                        self._issue(
                            "warning",
                            "orphan_field",
                            f"Ignored {label} before the first TYPE in this tab.",
                            tab=tab,
                            paragraph_index=paragraph.paragraph_index,
                        )
                    continue

                if label in {"DISPLAY_TYPE", "PROMPT", "KEYWORDS", "CHARACTERS"}:
                    if label == "CHARACTERS":
                        try:
                            characters = int(value)
                        except (TypeError, ValueError):
                            characters = 0
                        if characters < 1:
                            self._issue(
                                "error",
                                "invalid_characters",
                                "CHARACTERS must be a positive integer.",
                                tab=tab,
                                exercise_order=current_exercise["source"]["exercise_order"],
                                paragraph_index=paragraph.paragraph_index,
                            )
                            current_exercise["characters"] = None
                        else:
                            current_exercise["characters"] = characters
                        pending_field = None
                        continue
                    key = {
                        "DISPLAY_TYPE": "display_type",
                        "PROMPT": "prompt",
                        "KEYWORDS": "keywords_raw",
                    }[label]
                    current_exercise[key] = value
                    if label == "KEYWORDS":
                        current_exercise["keywords"] = _accepted_answers([value])
                    current_exercise[f"_{key}_rich"] = value_rich
                    pending_field = f"exercise:{key}"
                    continue

                if label in {"ITEM", "QUESTION"}:
                    flush_question()
                    number = value.strip()
                    current_question = {
                        "marker": label.lower(),
                        "source_number": None
                        if number.lower() == "example"
                        else number,
                        "is_example": number.lower() == "example",
                        "raw_number": number,
                        "sort_order": len(current_exercise["questions"]) + 1,
                        "fields": {},
                        "rich_fields": {},
                        "raw_answers": [],
                        "options": [],
                        "_paragraph_index": paragraph.paragraph_index,
                    }
                    pending_field = None
                    continue

                if current_question is None:
                    self._issue(
                        "warning",
                        "orphan_question_field",
                        f"Ignored {label} before ITEM or QUESTION.",
                        tab=tab,
                        exercise_order=current_exercise["source"]["exercise_order"],
                        paragraph_index=paragraph.paragraph_index,
                    )
                    continue

                if label in {"TEXT", "STEM"}:
                    key = label.lower()
                    current_question["fields"][key] = value
                    current_question["rich_fields"][key] = value_rich
                    pending_field = f"question:{key}"
                    continue

                if label == "CORRECT":
                    current_question["fields"]["correct_raw"] = value
                    current_question["fields"]["is_correct"] = _parse_bool(value)
                    pending_field = None
                    continue

                if label == "ANSWER":
                    current_question["raw_answers"].append(value)
                    pending_field = "question:answer"
                    continue

                if label == "OPTIONS":
                    pending_field = "question:options"
                    continue

                self._issue(
                    "warning",
                    "unknown_label",
                    f"Unrecognized field label {label}.",
                    tab=tab,
                    exercise_order=current_exercise["source"]["exercise_order"],
                    question_number=current_question.get("raw_number"),
                    paragraph_index=paragraph.paragraph_index,
                )
                pending_field = None
                continue

            option_match = OPTION_RE.match(text)
            if (
                option_match
                and current_question is not None
                and pending_field == "question:options"
            ):
                option_label = option_match.group(1)
                option_value_start = option_match.start(2)
                option_rich = _trim_rich(_slice_rich(rich, option_value_start))
                current_question["options"].append(
                    {
                        "label": option_label,
                        "text": option_rich.text,
                        "text_runs": option_rich.runs,
                    }
                )
                continue

            if pending_field:
                self._append_continuation(
                    pending_field,
                    rich,
                    current_exercise,
                    current_question,
                )

        flush_exercise()
        return exercises

    def _new_exercise(
        self,
        tab: SourceTab,
        exercise_order: int,
        metadata: Dict[str, Optional[str]],
        exercise_type: str,
        paragraph_index: int,
    ) -> Dict[str, Any]:
        topic_source_key = _hash_key(
            self.document_id,
            tab.tab_id,
            "topic",
        )
        source_key = _hash_key(
            self.document_id,
            tab.tab_id,
            "exercise",
            exercise_order,
        )
        return {
            "source_key": source_key,
            "topic_source_key": topic_source_key,
            "topic": metadata.get("topic"),
            "display_title": metadata.get("display_title"),
            "category": metadata.get("category"),
            "sub_category": metadata.get("sub_category"),
            "difficulty": metadata.get("difficulty"),
            "lesson": metadata.get("lesson"),
            "exercise_type": exercise_type.strip().lower(),
            "display_type": None,
            "prompt": None,
            "keywords": None,
            "characters": None,
            "source": {
                "document_id": self.document_id or None,
                "tab_id": tab.tab_id,
                "tab_title": tab.title,
                "tab_path": tab.path,
                "tab_order": tab.index + 1,
                "exercise_order": exercise_order,
                "paragraph_index": paragraph_index,
            },
            "questions": [],
        }

    @staticmethod
    def _append_continuation(
        pending_field: str,
        rich: RichText,
        exercise: Optional[Dict[str, Any]],
        question: Optional[Dict[str, Any]],
    ) -> None:
        scope, field_name = pending_field.split(":", 1)
        if scope == "exercise" and exercise is not None:
            rich_key = f"_{field_name}_rich"
            existing = exercise.get(rich_key) or RichText()
            existing.append(rich)
            exercise[rich_key] = existing
            exercise[field_name] = existing.text
            if field_name == "keywords_raw":
                exercise["keywords"] = _accepted_answers([existing.text])
            return
        if scope != "question" or question is None:
            return
        if field_name in {"text", "stem"}:
            existing = question["rich_fields"].get(field_name) or RichText()
            existing.append(rich)
            question["rich_fields"][field_name] = existing
            question["fields"][field_name] = existing.text
        elif field_name == "answer" and question["raw_answers"]:
            question["raw_answers"][-1] += f"\n{rich.text}"
        elif field_name == "options" and question["options"]:
            option = question["options"][-1]
            existing = RichText(option["text"], option["text_runs"])
            existing.append(rich)
            option["text"] = existing.text
            option["text_runs"] = existing.runs

    def _finalize_question(
        self,
        question: Dict[str, Any],
        exercise: Dict[str, Any],
        tab: SourceTab,
    ) -> Dict[str, Any]:
        exercise_type = exercise["exercise_type"]
        fields = question["fields"]
        raw_answers = [answer.strip() for answer in question["raw_answers"] if answer.strip()]
        accepted_answers = _accepted_answers(raw_answers)
        content: Dict[str, Any] = {}

        if exercise_type == "fill_blank":
            content["text"] = fields.get("text")
            content["text_runs"] = self._runs_for(question, "text")
            content["raw_answers"] = raw_answers
            content["accepted_answers"] = accepted_answers
            content["blanks"] = self._fill_blank_definitions(
                fields.get("text") or "",
                exercise.get("characters"),
            )
        elif exercise_type == "multiple_choice":
            content["text"] = fields.get("text")
            content["text_runs"] = self._runs_for(question, "text")
            content["options"] = question["options"]
            content["correct_option"] = raw_answers[0] if raw_answers else None
        elif exercise_type == "sentence_transform":
            content["stem"] = fields.get("stem")
            content["stem_runs"] = self._runs_for(question, "stem")
            if "correct_raw" in fields:
                content["is_correct"] = fields.get("is_correct")
                content["correct_raw"] = fields.get("correct_raw")
            content["raw_answers"] = raw_answers
            content["accepted_answers"] = accepted_answers
        else:
            content.update(fields)
            content["raw_answers"] = raw_answers

        source_number = question.get("source_number")
        question_key_part = (
            f"example:{question['sort_order']}"
            if question["is_example"]
            else f"{question['marker']}:{source_number}"
        )
        result = {
            "source_key": _hash_key(exercise["source_key"], question_key_part),
            "exercise_source_key": exercise["source_key"],
            "source_number": source_number,
            "is_example": bool(question["is_example"]),
            "sort_order": question["sort_order"],
            "content": content,
            "source": {
                "marker": question["marker"],
                "raw_number": question["raw_number"],
                "paragraph_index": question["_paragraph_index"],
            },
        }
        self._validate_question(result, exercise, tab)
        return result

    @staticmethod
    def _fill_blank_definitions(
        text: str,
        authored_min_len: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Create renderer metadata for every authored underscore blank.

        CHARACTERS is a visual-width hint, not an answer-length constraint. Match
        the legacy parser by adding one character of display space. When it is
        absent, the underscore run length remains a useful rendering fallback.
        """
        return [
            {
                "id": f"b{index}",
                "min_len": (
                    authored_min_len + 1
                    if authored_min_len is not None
                    else len(match.group(0))
                ),
            }
            for index, match in enumerate(BLANK_RE.finditer(text), start=1)
        ]

    @staticmethod
    def _runs_for(question: Dict[str, Any], field_name: str) -> List[Dict[str, Any]]:
        rich = question["rich_fields"].get(field_name)
        return rich.runs if rich else []

    def _validate_exercise(
        self,
        exercise: Dict[str, Any],
        tab: SourceTab,
    ) -> None:
        order = exercise["source"]["exercise_order"]
        for field_name in sorted(REQUIRED_TOPIC_FIELDS):
            if not exercise.get(field_name):
                self._issue(
                    "error",
                    "missing_required_topic_field",
                    f"Exercise is missing required {field_name}.",
                    tab=tab,
                    exercise_order=order,
                )
        for field_name in sorted(REQUIRED_EXERCISE_FIELDS):
            if not exercise.get(field_name):
                self._issue(
                    "error",
                    "missing_required_exercise_field",
                    f"Exercise is missing required {field_name}.",
                    tab=tab,
                    exercise_order=order,
                )
        if exercise["exercise_type"] not in SUPPORTED_TYPES:
            self._issue(
                "error",
                "unsupported_exercise_type",
                f"Unsupported exercise type: {exercise['exercise_type'] or '<empty>'}.",
                tab=tab,
                exercise_order=order,
            )
        if (
            exercise.get("characters") is not None
            and exercise["exercise_type"] != "fill_blank"
        ):
            self._issue(
                "error",
                "characters_on_non_fill_blank",
                "CHARACTERS is only supported for fill_blank exercises.",
                tab=tab,
                exercise_order=order,
            )
        if not exercise["questions"]:
            self._issue(
                "error",
                "exercise_without_questions",
                "Exercise has no questions or examples.",
                tab=tab,
                exercise_order=order,
            )
        elif not any(not question["is_example"] for question in exercise["questions"]):
            self._issue(
                "error",
                "exercise_without_gradable_questions",
                "Exercise has no gradable questions.",
                tab=tab,
                exercise_order=order,
            )
        self._expose_rich_exercise_fields(exercise)

    @staticmethod
    def _expose_rich_exercise_fields(exercise: Dict[str, Any]) -> None:
        for field_name in ("display_type", "prompt"):
            rich = exercise.pop(f"_{field_name}_rich", None)
            if rich:
                exercise[f"{field_name}_runs"] = rich.runs
        exercise.pop("_keywords_raw_rich", None)
        exercise.pop("keywords_raw", None)

    def _validate_question(
        self,
        question: Dict[str, Any],
        exercise: Dict[str, Any],
        tab: SourceTab,
    ) -> None:
        exercise_type = exercise["exercise_type"]
        content = question["content"]
        order = exercise["source"]["exercise_order"]
        number = question["source"]["raw_number"]

        if not question["is_example"] and not question["source_number"]:
            self._issue(
                "error",
                "missing_question_number",
                "Gradable question has no source number.",
                tab=tab,
                exercise_order=order,
                question_number=number,
            )

        if exercise_type == "fill_blank":
            if not content.get("text"):
                self._missing_question_field("TEXT", tab, order, number)
            if not content.get("accepted_answers"):
                self._missing_question_field("ANSWER", tab, order, number)
        elif exercise_type == "multiple_choice":
            if not content.get("text"):
                self._missing_question_field("TEXT", tab, order, number)
            if len(content.get("options") or []) < 2:
                self._issue(
                    "error",
                    "invalid_options",
                    "Multiple-choice question requires at least two options.",
                    tab=tab,
                    exercise_order=order,
                    question_number=number,
                )
            labels = {option["label"] for option in content.get("options") or []}
            if content.get("correct_option") not in labels:
                self._issue(
                    "error",
                    "invalid_correct_option",
                    "Multiple-choice ANSWER must match an option label.",
                    tab=tab,
                    exercise_order=order,
                    question_number=number,
                )
        elif exercise_type == "sentence_transform":
            if not content.get("stem"):
                self._missing_question_field("STEM", tab, order, number)
            if "correct_raw" in content:
                if content.get("is_correct") is None:
                    self._issue(
                        "error",
                        "invalid_correct_value",
                        "CORRECT must be yes/no or true/false.",
                        tab=tab,
                        exercise_order=order,
                        question_number=number,
                    )
                if content.get("is_correct") is False and not content.get(
                    "accepted_answers"
                ):
                    self._missing_question_field("ANSWER", tab, order, number)
            elif not content.get("accepted_answers"):
                self._missing_question_field("ANSWER", tab, order, number)

    def _missing_question_field(
        self,
        field_name: str,
        tab: SourceTab,
        exercise_order: int,
        question_number: str,
    ) -> None:
        self._issue(
            "error",
            "missing_required_question_field",
            f"Question is missing required {field_name}.",
            tab=tab,
            exercise_order=exercise_order,
            question_number=question_number,
        )


def parse_document(document: Dict[str, Any]) -> Dict[str, Any]:
    return ExerciseBankParser().parse(document)


def parse_file(path: str | Path) -> Dict[str, Any]:
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        document = json.load(handle)
    return parse_document(document)


def fetch_and_parse(
    document_id: str,
    *,
    include_tabs_content: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetch Google Docs content and return both raw and parsed documents."""
    try:
        from .docs_fetch import fetch_doc
    except ImportError:  # pragma: no cover - direct script fallback
        from app.tools.docs_fetch import fetch_doc  # type: ignore

    document = fetch_doc(
        document_id,
        include_tabs_content=include_tabs_content,
    )
    if not document:
        raise RuntimeError(f"Failed to fetch Google document {document_id}")
    return document, parse_document(document)


def main(argv: Optional[Sequence[str]] = None) -> int:
    argument_parser = argparse.ArgumentParser(
        description=(
            "Fetch and parse a Google Docs exercise bank into "
            "parent exercises and individual question records."
        )
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
        "--raw-input",
        help="Debug only: parse a saved Google Docs JSON response instead of fetching",
    )
    argument_parser.add_argument(
        "--raw-output",
        help="Debug only: save the fetched Google Docs response here",
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
                include_tabs_content=args.all_tabs,
            )
            if args.raw_output:
                raw_output_path = Path(args.raw_output)
                raw_output_path.parent.mkdir(parents=True, exist_ok=True)
                raw_output_path.write_text(
                    json.dumps(raw_document, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                print(
                    "[exercise_bank_v2_parser] "
                    f"wrote raw Google Docs JSON to {raw_output_path}"
                )
    except (OSError, json.JSONDecodeError, RuntimeError) as error:
        print(f"[exercise_bank_v2_parser] {error}", file=sys.stderr)
        return 2

    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + "\n", encoding="utf-8")
        print(
            "[exercise_bank_v2_parser] "
            f"wrote {result['summary']['exercise_count']} exercises and "
            f"{result['summary']['question_count']} questions to {output_path}"
        )
    else:
        print(serialized)

    summary = result["summary"]
    print(
        "[exercise_bank_v2_parser] "
        f"{summary['gradable_question_count']} gradable, "
        f"{summary['example_count']} examples, "
        f"{summary['error_count']} errors, "
        f"{summary['warning_count']} warnings",
        file=sys.stderr,
    )
    if summary["error_count"] and not args.allow_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

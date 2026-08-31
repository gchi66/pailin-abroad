#!/usr/bin/env python3
"""Import parsed speaking-coach JSON into Supabase.

The command is a read-only dry run unless ``--apply`` is supplied. Imports are
idempotent: practice sets and questions are upserted by their parser-generated
``source_key``. Missing rows remain active unless ``--deactivate-missing`` is
explicitly requested together with ``--apply``.

Usage:
    python -m app.tools.speaking_coach_importer data/speaking_coach.json
    python -m app.tools.speaking_coach_importer data/speaking_coach.json --apply
    python -m app.tools.speaking_coach_importer data/speaking_coach.json \
        --apply --deactivate-missing
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import httpx
from postgrest.exceptions import APIError

from app.supabase_client import supabase_admin


PRACTICE_SETS_TABLE = "speaking_coach_practice_sets"
QUESTIONS_TABLE = "speaking_coach_questions"
LESSONS_TABLE = "lessons"
PARSER_SCHEMA_VERSION = "speaking-coach-parser-v3"
SUPPORTED_PARSER_SCHEMA_VERSIONS = {
    "speaking-coach-parser-v1",
    "speaking-coach-parser-v2",
    PARSER_SCHEMA_VERSION,
}
DEFAULT_BATCH_SIZE = 100
SUPPORTED_PRACTICE_TYPES = {"pronunciation", "open", "translation"}


@dataclass
class ImportData:
    document_id: str
    lesson_external_ids: List[str]
    practice_sets: List[Dict[str, Any]]
    questions: List[Dict[str, Any]]


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _duplicates(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def _content_hash(value: Any) -> str:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _validate_examples(value: Any, context: str, errors: List[str]) -> List[Dict[str, str | None]]:
    if not isinstance(value, list):
        errors.append(f"{context} must be an array.")
        return []
    examples: List[Dict[str, str | None]] = []
    for index, example in enumerate(value, start=1):
        example_context = f"{context}[{index}]"
        if not isinstance(example, dict):
            errors.append(f"{example_context} must be an object.")
            continue
        en = example.get("en")
        th = example.get("th")
        if en is not None and not isinstance(en, str):
            errors.append(f"{example_context}.en must be a string or null.")
        if th is not None and not isinstance(th, str):
            errors.append(f"{example_context}.th must be a string or null.")
        examples.append({"en": _optional_text(en), "th": _optional_text(th)})
    return examples


def _validate_focus_items(
    value: Any,
    context: str,
    errors: List[str],
) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{context} must be an array.")
        return []
    if not value:
        errors.append(f"{context} must contain at least one focus item.")
        return []

    focus_items: List[Dict[str, Any]] = []
    for index, item in enumerate(value, start=1):
        item_context = f"{context}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_context} must be an object.")
            continue

        priority = item.get("priority")
        instruction = _optional_text(item.get("instruction"))
        if (
            not isinstance(priority, int)
            or isinstance(priority, bool)
            or priority not in {1, 2, 3}
        ):
            errors.append(f"{item_context}.priority must be the integer 1, 2, or 3.")
        if instruction is None:
            errors.append(f"{item_context}.instruction must be a non-empty string.")
        if (
            isinstance(priority, int)
            and not isinstance(priority, bool)
            and priority in {1, 2, 3}
            and instruction is not None
        ):
            focus_items.append(
                {
                    "priority": priority,
                    "instruction": instruction,
                }
            )
    return focus_items


def prepare_import(payload: Any) -> tuple[ImportData | None, List[str]]:
    """Validate parser output and flatten it into database-ready logical rows."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return None, ["Root JSON must be an object."]

    schema_version = payload.get("schema_version")
    if schema_version not in SUPPORTED_PARSER_SCHEMA_VERSIONS:
        errors.append(
            "'schema_version' must be one of "
            f"{sorted(SUPPORTED_PARSER_SCHEMA_VERSIONS)}."
        )

    document = payload.get("document")
    lessons = payload.get("lessons")
    issues = payload.get("issues")
    if not isinstance(document, dict):
        errors.append("'document' must be an object.")
        document = {}
    if not isinstance(lessons, list):
        errors.append("'lessons' must be an array.")
        lessons = []
    if not isinstance(issues, list):
        errors.append("'issues' must be an array.")
        issues = []

    document_id = document.get("document_id")
    if not _non_empty(document_id):
        errors.append("'document.document_id' must be a non-empty string.")
        document_id = ""

    parser_errors = [
        issue
        for issue in issues
        if isinstance(issue, dict) and issue.get("severity") == "error"
    ]
    if parser_errors:
        errors.append(
            f"Parser output contains {len(parser_errors)} error issue(s); import refused."
        )
    if not lessons:
        errors.append("At least one lesson is required.")

    lesson_external_ids: List[str] = []
    practice_rows: List[Dict[str, Any]] = []
    question_rows: List[Dict[str, Any]] = []

    for lesson_index, lesson in enumerate(lessons, start=1):
        lesson_context = f"Lesson[{lesson_index}]"
        if not isinstance(lesson, dict):
            errors.append(f"{lesson_context} must be an object.")
            continue

        lesson_external_id = lesson.get("lesson_external_id")
        lesson_source_key = lesson.get("source_key")
        if not _non_empty(lesson_external_id):
            errors.append(
                f"{lesson_context}.lesson_external_id must be a non-empty string."
            )
        else:
            lesson_external_ids.append(lesson_external_id)
        if not _non_empty(lesson_source_key):
            errors.append(f"{lesson_context}.source_key must be a non-empty string.")

        practice_sets = lesson.get("practice_sets")
        if not isinstance(practice_sets, list):
            errors.append(f"{lesson_context}.practice_sets must be an array.")
            continue
        if not practice_sets:
            errors.append(f"{lesson_context} must contain at least one practice set.")

        lesson_question_position = 0
        for practice_index, practice in enumerate(practice_sets, start=1):
            practice_context = f"{lesson_context}.PracticeSet[{practice_index}]"
            if not isinstance(practice, dict):
                errors.append(f"{practice_context} must be an object.")
                continue

            source_key = practice.get("source_key")
            parent_key = practice.get("lesson_source_key")
            practice_type = practice.get("practice_type")
            source = practice.get("source")
            tip = practice.get("tip")
            questions = practice.get("questions")

            for field in ("source_key", "lesson_source_key", "source_practice_type"):
                if not _non_empty(practice.get(field)):
                    errors.append(f"{practice_context}.{field} must be a non-empty string.")
            if parent_key != lesson_source_key:
                errors.append(
                    f"{practice_context} does not reference its containing lesson."
                )
            if practice_type not in SUPPORTED_PRACTICE_TYPES:
                errors.append(
                    f"{practice_context} has unsupported practice_type '{practice_type}'."
                )
            if not _positive_int(practice.get("sort_order")):
                errors.append(f"{practice_context}.sort_order must be a positive integer.")
            if not isinstance(source, dict):
                errors.append(f"{practice_context}.source must be an object.")
                source = {}
            if source.get("document_id") != document_id:
                errors.append(
                    f"{practice_context}.source.document_id does not match the root document."
                )
            if not isinstance(tip, dict):
                errors.append(f"{practice_context}.tip must be an object.")
                tip = {}
            for language in ("en", "th"):
                if tip.get(language) is not None and not isinstance(tip.get(language), str):
                    errors.append(
                        f"{practice_context}.tip.{language} must be a string or null."
                    )
            if not isinstance(questions, list):
                errors.append(f"{practice_context}.questions must be an array.")
                questions = []
            if not questions:
                errors.append(f"{practice_context} must contain at least one question.")

            practice_question_hashes: List[str] = []
            question_focuses: List[str] = []
            for question_index, question in enumerate(questions, start=1):
                lesson_question_position += 1
                question_context = f"{practice_context}.Question[{question_index}]"
                if not isinstance(question, dict):
                    errors.append(f"{question_context} must be an object.")
                    continue

                question_source_key = question.get("source_key")
                question_parent_key = question.get("practice_set_source_key")
                prompt = question.get("prompt")
                target_answers = question.get("target_answers")
                question_source = question.get("source")

                for field in ("source_key", "practice_set_source_key", "source_number"):
                    if not _non_empty(question.get(field)):
                        errors.append(
                            f"{question_context}.{field} must be a non-empty string."
                        )
                if question_parent_key != source_key:
                    errors.append(
                        f"{question_context} does not reference its containing practice set."
                    )
                if not _positive_int(question.get("sort_order")):
                    errors.append(
                        f"{question_context}.sort_order must be a positive integer."
                    )
                if not isinstance(prompt, dict):
                    errors.append(f"{question_context}.prompt must be an object.")
                    prompt = {}
                for language in ("en", "th"):
                    if prompt.get(language) is not None and not isinstance(
                        prompt.get(language), str
                    ):
                        errors.append(
                            f"{question_context}.prompt.{language} must be a string or null."
                        )
                if not isinstance(target_answers, list) or not all(
                    _non_empty(answer) for answer in target_answers
                ):
                    if target_answers != []:
                        errors.append(
                            f"{question_context}.target_answers must contain only "
                            "non-empty strings."
                        )
                    target_answers = []
                examples = _validate_examples(
                    question.get("examples"), f"{question_context}.examples", errors
                )
                focus = _optional_text(question.get("focus")) or _optional_text(
                    practice.get("focus")
                )
                if focus is None:
                    errors.append(f"{question_context}.focus must be a non-empty string.")
                else:
                    question_focuses.append(focus)
                if schema_version == PARSER_SCHEMA_VERSION:
                    focus_items = _validate_focus_items(
                        question.get("focus_items"),
                        f"{question_context}.focus_items",
                        errors,
                    )
                else:
                    focus_items = (
                        [{"priority": 1, "instruction": focus}]
                        if focus is not None
                        else []
                    )
                if not isinstance(question_source, dict):
                    errors.append(f"{question_context}.source must be an object.")
                    question_source = {}

                prompt_en = _optional_text(prompt.get("en"))
                prompt_th = _optional_text(prompt.get("th"))
                if practice_type in {"pronunciation", "open"}:
                    if prompt_en is None:
                        errors.append(f"{question_context}.prompt.en is required.")
                    if prompt_th is None:
                        errors.append(f"{question_context}.prompt.th is required.")
                elif practice_type == "translation":
                    if prompt_th is None:
                        errors.append(f"{question_context}.prompt.th is required.")
                if practice_type in {"pronunciation", "translation"} and not target_answers:
                    errors.append(f"{question_context}.target_answers cannot be empty.")

                prompt_audio_key = (
                    f"{lesson_external_id}_speaking_{lesson_question_position}.mp3"
                    if _non_empty(lesson_external_id)
                    and practice_type != "translation"
                    else None
                )
                hash_input = {
                    "prompt_en": prompt_en,
                    "prompt_th": prompt_th,
                    "target_answers": target_answers,
                    "examples": examples,
                    "focus": focus,
                    "focus_items": focus_items,
                    "prompt_audio_key": prompt_audio_key,
                }
                question_hash = _content_hash(hash_input)
                practice_question_hashes.append(question_hash)
                question_rows.append(
                    {
                        "source_key": question_source_key,
                        "_practice_set_source_key": question_parent_key,
                        "source_number": question.get("source_number"),
                        "sort_order": question.get("sort_order"),
                        "prompt_en": prompt_en,
                        "prompt_th": prompt_th,
                        "target_answers": target_answers,
                        "examples": examples,
                        "focus": focus,
                        "focus_items": focus_items,
                        "prompt_audio_key": prompt_audio_key,
                        "source_paragraph_index": question_source.get(
                            "paragraph_index"
                        ),
                        "content_hash": question_hash,
                        "is_active": True,
                    }
                )

            practice_focus = _optional_text(practice.get("focus")) or "\n\n".join(
                question_focuses
            )
            practice_hash = _content_hash(
                {
                    "practice_type": practice_type,
                    "focus": practice_focus,
                    "tip_en": _optional_text(tip.get("en")),
                    "tip_th": _optional_text(tip.get("th")),
                    "questions": practice_question_hashes,
                }
            )
            practice_rows.append(
                {
                    "source_key": source_key,
                    "_lesson_external_id": lesson_external_id,
                    "source_document_id": document_id,
                    "source_tab_id": _optional_text(source.get("tab_id")),
                    "source_tab_title": _optional_text(source.get("tab_title")),
                    "source_tab_order": source.get("tab_order"),
                    "source_paragraph_index": source.get("paragraph_index"),
                    "practice_type": practice_type,
                    "source_practice_type": practice.get("source_practice_type"),
                    "focus": practice_focus,
                    "tip_en": _optional_text(tip.get("en")),
                    "tip_th": _optional_text(tip.get("th")),
                    "sort_order": practice.get("sort_order"),
                    "content_hash": practice_hash,
                    "is_active": True,
                }
            )

    duplicate_lessons = _duplicates(
        value for value in lesson_external_ids if _non_empty(value)
    )
    duplicate_lesson_keys = _duplicates(
        lesson.get("source_key")
        for lesson in lessons
        if isinstance(lesson, dict) and _non_empty(lesson.get("source_key"))
    )
    duplicate_practices = _duplicates(
        row["source_key"] for row in practice_rows if _non_empty(row.get("source_key"))
    )
    duplicate_questions = _duplicates(
        row["source_key"] for row in question_rows if _non_empty(row.get("source_key"))
    )
    if duplicate_lessons:
        errors.append(
            f"Duplicate lesson_external_id(s): {', '.join(duplicate_lessons)}"
        )
    if duplicate_lesson_keys:
        errors.append(
            f"Duplicate lesson source_key(s): {', '.join(duplicate_lesson_keys)}"
        )
    if duplicate_practices:
        errors.append(
            f"Duplicate practice-set source_key(s): {', '.join(duplicate_practices)}"
        )
    if duplicate_questions:
        errors.append(
            f"Duplicate question source_key(s): {', '.join(duplicate_questions)}"
        )

    known_practice_keys = {
        row["source_key"] for row in practice_rows if _non_empty(row.get("source_key"))
    }
    for row in question_rows:
        parent_key = row.get("_practice_set_source_key")
        if _non_empty(parent_key) and parent_key not in known_practice_keys:
            errors.append(
                f"Question '{row.get('source_key')}' references unknown "
                f"practice_set_source_key '{parent_key}'."
            )

    if errors:
        return None, errors
    return ImportData(
        document_id=document_id,
        lesson_external_ids=lesson_external_ids,
        practice_sets=practice_rows,
        questions=question_rows,
    ), []


def _execute_with_retry(builder: Any, label: str, retries: int = 3) -> Any:
    attempt = 0
    while True:
        try:
            return builder.execute()
        except (httpx.TransportError, APIError) as exc:
            attempt += 1
            error_text = str(exc).lower()
            transient = isinstance(exc, httpx.TransportError) or any(
                marker in error_text
                for marker in ("gateway", "network", "502", "503", "504")
            )
            if not transient or attempt > retries:
                raise
            delay = 0.5 * (2 ** (attempt - 1))
            print(
                f"[WARN] {label} failed; retrying in {delay:.1f}s "
                f"({attempt}/{retries})"
            )
            time.sleep(delay)


def _chunks(rows: Sequence[Any], size: int) -> Iterable[List[Any]]:
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def _resolve_lesson_ids(
    client: Any, external_ids: Sequence[str], batch_size: int
) -> Dict[str, str]:
    rows: List[Dict[str, Any]] = []
    for batch in _chunks(list(external_ids), batch_size):
        response = _execute_with_retry(
            client.table(LESSONS_TABLE)
            .select("id,lesson_external_id")
            .in_("lesson_external_id", batch),
            "resolve lesson IDs",
        )
        rows.extend(getattr(response, "data", None) or [])

    grouped: Dict[str, List[str]] = {}
    for row in rows:
        grouped.setdefault(row["lesson_external_id"], []).append(row["id"])
    missing = sorted(set(external_ids) - set(grouped))
    duplicates = sorted(key for key, ids in grouped.items() if len(ids) > 1)
    if missing:
        raise RuntimeError(
            "No lessons row found for lesson_external_id(s): " + ", ".join(missing)
        )
    if duplicates:
        raise RuntimeError(
            "Multiple lessons rows found for lesson_external_id(s): "
            + ", ".join(duplicates)
        )
    return {key: ids[0] for key, ids in grouped.items()}


def _upsert_rows(
    client: Any, table: str, rows: Sequence[Dict[str, Any]], batch_size: int
) -> None:
    batches = list(_chunks(list(rows), batch_size))
    for number, batch in enumerate(batches, start=1):
        _execute_with_retry(
            client.table(table).upsert(batch, on_conflict="source_key"),
            f"{table} batch {number}/{len(batches)}",
        )
        print(
            f"[INFO] {table}: upserted batch {number}/{len(batches)} "
            f"({len(batch)} rows)"
        )


def _resolve_practice_set_ids(
    client: Any, source_keys: Sequence[str], batch_size: int
) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for batch in _chunks(list(source_keys), batch_size):
        response = _execute_with_retry(
            client.table(PRACTICE_SETS_TABLE)
            .select("id,source_key")
            .in_("source_key", batch),
            "resolve practice-set IDs",
        )
        for row in getattr(response, "data", None) or []:
            result[row["source_key"]] = row["id"]
    missing = sorted(set(source_keys) - set(result))
    if missing:
        raise RuntimeError(
            f"Could not resolve {len(missing)} practice-set ID(s) after upsert."
        )
    return result


def _deactivate_stale_rows(
    client: Any,
    *,
    document_id: str,
    lesson_ids: Sequence[str],
    active_practice_keys: Sequence[str],
    active_question_keys: Sequence[str],
    batch_size: int,
) -> tuple[int, int]:
    practice_response = _execute_with_retry(
        client.table(PRACTICE_SETS_TABLE)
        .select("id,source_key")
        .eq("source_document_id", document_id)
        .in_("lesson_id", list(lesson_ids)),
        "find stale speaking-coach practice sets",
    )
    practices = getattr(practice_response, "data", None) or []
    practice_ids = [row["id"] for row in practices]
    active_practices = set(active_practice_keys)
    stale_practice_ids = [
        row["id"] for row in practices if row.get("source_key") not in active_practices
    ]

    questions: List[Dict[str, Any]] = []
    for parent_batch in _chunks(practice_ids, batch_size):
        response = _execute_with_retry(
            client.table(QUESTIONS_TABLE)
            .select("id,source_key")
            .in_("practice_set_id", parent_batch),
            "find stale speaking-coach questions",
        )
        questions.extend(getattr(response, "data", None) or [])
    active_questions = set(active_question_keys)
    stale_question_ids = [
        row["id"] for row in questions if row.get("source_key") not in active_questions
    ]

    for batch in _chunks(stale_question_ids, batch_size):
        _execute_with_retry(
            client.table(QUESTIONS_TABLE)
            .update({"is_active": False})
            .in_("id", batch),
            "deactivate stale speaking-coach questions",
        )
    for batch in _chunks(stale_practice_ids, batch_size):
        _execute_with_retry(
            client.table(PRACTICE_SETS_TABLE)
            .update({"is_active": False})
            .in_("id", batch),
            "deactivate stale speaking-coach practice sets",
        )
    return len(stale_practice_ids), len(stale_question_ids)


def import_data(
    data: ImportData,
    *,
    client: Any = supabase_admin,
    apply: bool = False,
    deactivate_missing: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, int]:
    """Resolve lessons, then optionally write the validated authored content."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    if deactivate_missing and not apply:
        raise ValueError("deactivate_missing requires apply=True.")

    lesson_ids = _resolve_lesson_ids(client, data.lesson_external_ids, batch_size)
    summary = {
        "lessons": len(lesson_ids),
        "practice_sets": len(data.practice_sets),
        "questions": len(data.questions),
        "deactivated_practice_sets": 0,
        "deactivated_questions": 0,
    }
    if not apply:
        return summary

    practice_rows: List[Dict[str, Any]] = []
    for original in data.practice_sets:
        row = dict(original)
        lesson_external_id = row.pop("_lesson_external_id")
        row["lesson_id"] = lesson_ids[lesson_external_id]
        practice_rows.append(row)
    _upsert_rows(client, PRACTICE_SETS_TABLE, practice_rows, batch_size)

    practice_ids = _resolve_practice_set_ids(
        client,
        [row["source_key"] for row in practice_rows],
        batch_size,
    )
    question_rows: List[Dict[str, Any]] = []
    for original in data.questions:
        row = dict(original)
        practice_source_key = row.pop("_practice_set_source_key")
        row["practice_set_id"] = practice_ids[practice_source_key]
        question_rows.append(row)
    _upsert_rows(client, QUESTIONS_TABLE, question_rows, batch_size)

    if deactivate_missing:
        practices, questions = _deactivate_stale_rows(
            client,
            document_id=data.document_id,
            lesson_ids=list(lesson_ids.values()),
            active_practice_keys=[row["source_key"] for row in practice_rows],
            active_question_keys=[row["source_key"] for row in question_rows],
            batch_size=batch_size,
        )
        summary["deactivated_practice_sets"] = practices
        summary["deactivated_questions"] = questions
    return summary


def load_and_prepare(path: Path) -> tuple[ImportData | None, List[str]]:
    if not path.is_file():
        return None, [f"File not found: {path}"]
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"Could not load JSON from {path}: {exc}"]
    return prepare_import(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and import parsed speaking-coach JSON. The default is a "
            "read-only dry run; pass --apply to write."
        )
    )
    parser.add_argument("file", type=Path, help="Parsed speaking-coach JSON file.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the validated content to Supabase.",
    )
    parser.add_argument(
        "--deactivate-missing",
        action="store_true",
        help=(
            "Mark rows from this document and these lessons inactive when they "
            "are absent from the input. Requires --apply."
        ),
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args(argv)
    if args.deactivate_missing and not args.apply:
        parser.error("--deactivate-missing requires --apply")

    data, errors = load_and_prepare(args.file)
    if errors:
        print("[ERROR] Import validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1
    assert data is not None

    print(
        f"[VALID] {len(data.lesson_external_ids)} lessons, "
        f"{len(data.practice_sets)} practice sets, "
        f"{len(data.questions)} questions"
    )
    try:
        summary = import_data(
            data,
            apply=args.apply,
            deactivate_missing=args.deactivate_missing,
            batch_size=args.batch_size,
        )
    except (APIError, httpx.TransportError, RuntimeError, ValueError) as exc:
        print(f"[ERROR] Import failed: {exc}")
        return 1

    label = "SUCCESS" if args.apply else "DRY RUN"
    print(
        f"[{label}] Lessons matched: {summary['lessons']} | "
        f"Practice sets: {summary['practice_sets']} | "
        f"Questions: {summary['questions']} | "
        f"Deactivated: {summary['deactivated_practice_sets']} practice sets, "
        f"{summary['deactivated_questions']} questions"
    )
    if not args.apply:
        print("[DRY RUN] No database rows were changed. Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

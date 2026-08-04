#!/usr/bin/env python3
"""Import parsed exercise-bank v2 JSON into the three normalized Supabase tables.

Usage:
    python -m app.tools.exercise_bank_v2_importer data/exercise_bank.json --dry-run
    python -m app.tools.exercise_bank_v2_importer data/exercise_bank.json

Normal imports generate polished learner-facing review answers. Use
``--skip-review-answer-generation`` only for parser/import diagnostics.

The importer is idempotent: all three tables are upserted by ``source_key``.
Records absent from an import are left alone unless ``--deactivate-missing`` is used.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import httpx
from openai import OpenAI
from postgrest.exceptions import APIError

from app.supabase_client import supabase_admin
from app.tools.exercise_bank_v2_review_answers import enrich_question_content


TOPICS_TABLE = "exercise_bank_topics"
EXERCISES_TABLE = "exercise_bank_exercises"
QUESTIONS_TABLE = "exercise_bank_questions"
DEFAULT_BATCH_SIZE = 100
SUPPORTED_TYPES = {"fill_blank", "multiple_choice", "sentence_transform"}


@dataclass
class ImportData:
    document_id: str
    topics: List[Dict[str, Any]]
    exercises: List[Dict[str, Any]]
    questions: List[Dict[str, Any]]


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _duplicates(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return sorted(duplicate)


def prepare_import(payload: Any) -> tuple[ImportData | None, List[str]]:
    """Validate parsed JSON and turn it into database-ready, parent-linked rows."""
    errors: List[str] = []
    if not isinstance(payload, dict):
        return None, ["Root JSON must be an object."]

    document = payload.get("document")
    topics = payload.get("topics")
    exercises = payload.get("exercises")
    issues = payload.get("issues")
    if not isinstance(document, dict):
        errors.append("'document' must be an object.")
        document = {}
    if not isinstance(topics, list):
        errors.append("'topics' must be an array.")
        topics = []
    if not isinstance(exercises, list):
        errors.append("'exercises' must be an array.")
        exercises = []
    if not isinstance(issues, list):
        errors.append("'issues' must be an array.")
        issues = []

    document_id = document.get("document_id")
    if not _non_empty(document_id):
        errors.append("'document.document_id' must be a non-empty string.")
        document_id = ""

    parser_errors = [
        issue for issue in issues
        if isinstance(issue, dict) and issue.get("severity") == "error"
    ]
    if parser_errors:
        errors.append(
            f"Parser output contains {len(parser_errors)} error issue(s); import refused."
        )

    topic_rows: List[Dict[str, Any]] = []
    topic_keys: set[str] = set()
    for index, topic in enumerate(topics, start=1):
        ctx = f"Topic[{index}]"
        if not isinstance(topic, dict):
            errors.append(f"{ctx} must be an object.")
            continue
        required = (
            "source_key", "source_document_id", "source_tab_id",
            "topic", "display_title", "category", "lesson_external_id",
        )
        for field in required:
            if not _non_empty(topic.get(field)):
                errors.append(f"{ctx}.{field} must be a non-empty string.")
        source_key = topic.get("source_key")
        if _non_empty(source_key):
            topic_keys.add(source_key)
        topic_rows.append(
            {
                "source_key": source_key,
                "source_document_id": topic.get("source_document_id"),
                "source_tab_id": topic.get("source_tab_id"),
                "source_tab_title": topic.get("source_tab_title"),
                "source_tab_order": topic.get("source_tab_order"),
                "topic": topic.get("topic"),
                "display_title": topic.get("display_title"),
                "category": topic.get("category"),
                "sub_category": topic.get("sub_category") or None,
                "lesson_external_id": topic.get("lesson_external_id"),
                "sort_order": topic.get("sort_order"),
                "is_active": True,
            }
        )

    duplicate_topics = _duplicates(
        row["source_key"] for row in topic_rows if _non_empty(row.get("source_key"))
    )
    if duplicate_topics:
        errors.append(f"Duplicate topic source_key(s): {', '.join(duplicate_topics)}")

    exercise_rows: List[Dict[str, Any]] = []
    question_rows: List[Dict[str, Any]] = []
    exercise_keys: set[str] = set()
    for index, exercise in enumerate(exercises, start=1):
        ctx = f"Exercise[{index}]"
        if not isinstance(exercise, dict):
            errors.append(f"{ctx} must be an object.")
            continue
        for field in ("source_key", "topic_source_key", "exercise_type", "display_type", "prompt"):
            if not _non_empty(exercise.get(field)):
                errors.append(f"{ctx}.{field} must be a non-empty string.")
        source_key = exercise.get("source_key")
        parent_key = exercise.get("topic_source_key")
        exercise_type = exercise.get("exercise_type")
        if _non_empty(parent_key) and parent_key not in topic_keys:
            errors.append(f"{ctx} references unknown topic_source_key '{parent_key}'.")
        if exercise_type not in SUPPORTED_TYPES:
            errors.append(f"{ctx} has unsupported exercise_type '{exercise_type}'.")
        if _non_empty(source_key):
            exercise_keys.add(source_key)

        source = exercise.get("source") or {}
        exercise_rows.append(
            {
                "source_key": source_key,
                "_topic_source_key": parent_key,
                "difficulty": exercise.get("difficulty") or None,
                "exercise_type": exercise_type,
                "display_type": exercise.get("display_type"),
                "prompt": exercise.get("prompt"),
                "keywords": exercise.get("keywords") or None,
                "sort_order": source.get("exercise_order", index),
                "is_active": True,
            }
        )

        questions = exercise.get("questions")
        if not isinstance(questions, list):
            errors.append(f"{ctx}.questions must be an array.")
            continue
        for question_index, question in enumerate(questions, start=1):
            qctx = f"{ctx}.Question[{question_index}]"
            if not isinstance(question, dict):
                errors.append(f"{qctx} must be an object.")
                continue
            for field in ("source_key", "exercise_source_key"):
                if not _non_empty(question.get(field)):
                    errors.append(f"{qctx}.{field} must be a non-empty string.")
            if question.get("exercise_source_key") != source_key:
                errors.append(f"{qctx} does not reference its containing exercise.")
            if not isinstance(question.get("content"), dict):
                errors.append(f"{qctx}.content must be an object.")
            question_rows.append(
                {
                    "source_key": question.get("source_key"),
                    "_exercise_source_key": question.get("exercise_source_key"),
                    "source_number": question.get("source_number"),
                    "is_example": bool(question.get("is_example", False)),
                    "sort_order": question.get("sort_order", question_index),
                    "content": question.get("content"),
                    "is_active": True,
                }
            )

    duplicate_exercises = _duplicates(
        row["source_key"] for row in exercise_rows if _non_empty(row.get("source_key"))
    )
    duplicate_questions = _duplicates(
        row["source_key"] for row in question_rows if _non_empty(row.get("source_key"))
    )
    if duplicate_exercises:
        errors.append(
            f"Duplicate exercise source_key(s): {', '.join(duplicate_exercises)}"
        )
    if duplicate_questions:
        errors.append(
            f"Duplicate question source_key(s): {', '.join(duplicate_questions)}"
        )
    for row in question_rows:
        parent_key = row.get("_exercise_source_key")
        if _non_empty(parent_key) and parent_key not in exercise_keys:
            errors.append(
                f"Question '{row.get('source_key')}' references unknown "
                f"exercise_source_key '{parent_key}'."
            )

    if errors:
        return None, errors
    return ImportData(document_id, topic_rows, exercise_rows, question_rows), []


def _execute_with_retry(builder: Any, label: str, retries: int = 3) -> Any:
    attempt = 0
    while True:
        try:
            return builder.execute()
        except (httpx.TransportError, APIError) as exc:
            attempt += 1
            text = str(exc).lower()
            transient = isinstance(exc, httpx.TransportError) or any(
                marker in text for marker in ("gateway", "network", "502", "503", "504")
            )
            if not transient or attempt > retries:
                raise
            delay = 0.5 * (2 ** (attempt - 1))
            print(f"[WARN] {label} failed; retrying in {delay:.1f}s ({attempt}/{retries})")
            time.sleep(delay)


def _chunks(rows: Sequence[Dict[str, Any]], size: int) -> Iterable[List[Dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield list(rows[start : start + size])


def _upsert_rows(
    client: Any, table: str, rows: Sequence[Dict[str, Any]], batch_size: int
) -> None:
    batches = list(_chunks(rows, batch_size))
    for number, batch in enumerate(batches, start=1):
        response = _execute_with_retry(
            client.table(table).upsert(batch, on_conflict="source_key"),
            f"{table} batch {number}/{len(batches)}",
        )
        if getattr(response, "data", None) is None:
            raise RuntimeError(f"{table} batch {number} returned no data.")
        print(f"[INFO] {table}: upserted batch {number}/{len(batches)} ({len(batch)} rows)")


def _fetch_id_map(
    client: Any, table: str, source_keys: Sequence[str], batch_size: int
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for batch in _chunks(list(source_keys), batch_size):
        response = _execute_with_retry(
            client.table(table).select("id,source_key").in_("source_key", batch),
            f"resolve IDs from {table}",
        )
        for row in getattr(response, "data", None) or []:
            result[row["source_key"]] = row["id"]
    missing = sorted(set(source_keys) - set(result))
    if missing:
        raise RuntimeError(f"Could not resolve {len(missing)} ID(s) from {table}.")
    return result


def _fetch_existing_question_content(
    client: Any, source_keys: Sequence[str], batch_size: int
) -> Dict[str, Mapping[str, Any]]:
    result: Dict[str, Mapping[str, Any]] = {}
    for batch in _chunks(list(source_keys), batch_size):
        response = _execute_with_retry(
            client.table(QUESTIONS_TABLE).select("source_key,content").in_("source_key", batch),
            f"load existing review answers from {QUESTIONS_TABLE}",
        )
        for row in getattr(response, "data", None) or []:
            if isinstance(row.get("content"), dict):
                result[row["source_key"]] = row["content"]
    return result


def _enrich_review_answers(
    data: ImportData, *, client: Any, batch_size: int, ai_client: OpenAI | None = None
) -> tuple[int, int]:
    exercises = {row["source_key"]: row for row in data.exercises}
    eligible = [row for row in data.questions if not row.get("is_example")]
    existing = _fetch_existing_question_content(
        client, [row["source_key"] for row in eligible], batch_size
    )
    shared_ai_client = ai_client or OpenAI()
    generated = 0
    reused = 0
    for index, question in enumerate(eligible, start=1):
        exercise = exercises[question["_exercise_source_key"]]
        enriched, was_generated = enrich_question_content(
            exercise_type=exercise["exercise_type"],
            display_type=exercise["display_type"],
            prompt=exercise["prompt"],
            content=question["content"],
            existing_content=existing.get(question["source_key"]),
            client=shared_ai_client,
        )
        question["content"] = enriched
        generated += int(was_generated)
        reused += int(not was_generated)
        print(
            f"[INFO] review answers: {index}/{len(eligible)} "
            f"({'generated' if was_generated else 'reused'})"
        )
    return generated, reused


def _deactivate_missing(
    client: Any, table: str, document_id: str, active_keys: Sequence[str]
) -> tuple[int, List[Any]]:
    """Deactivate stale rows. Child tables are scoped through current document parents."""
    if table == TOPICS_TABLE:
        query = (
            client.table(table)
            .select("id,source_key")
            .eq("source_document_id", document_id)
            .eq("is_active", True)
        )
    else:
        # Caller supplies only rows belonging to this document via the resolved parent IDs.
        raise ValueError("Child deactivation must use _deactivate_missing_children.")
    response = _execute_with_retry(query, f"find stale rows in {table}")
    rows = getattr(response, "data", None) or []
    stale = [
        row["id"] for row in rows
        if row.get("source_key") not in set(active_keys)
    ]
    for batch in _chunks(stale, DEFAULT_BATCH_SIZE):
        _execute_with_retry(
            client.table(table).update({"is_active": False}).in_("id", batch),
            f"deactivate stale rows in {table}",
        )
    return len(stale), [row["id"] for row in rows]


def _deactivate_missing_children(
    client: Any,
    table: str,
    foreign_key: str,
    parent_ids: Sequence[Any],
    active_keys: Sequence[str],
    batch_size: int,
) -> tuple[int, List[Any]]:
    active = set(active_keys)
    stale_ids: List[Any] = []
    all_ids: List[Any] = []
    for parents in _chunks(list(parent_ids), batch_size):
        response = _execute_with_retry(
            client.table(table)
            .select("id,source_key")
            .in_(foreign_key, parents)
            .eq("is_active", True),
            f"find stale rows in {table}",
        )
        rows = getattr(response, "data", None) or []
        all_ids.extend(row["id"] for row in rows)
        stale_ids.extend(row["id"] for row in rows if row.get("source_key") not in active)
    for batch in _chunks(stale_ids, batch_size):
        _execute_with_retry(
            client.table(table).update({"is_active": False}).in_("id", batch),
            f"deactivate stale rows in {table}",
        )
    return len(stale_ids), all_ids


def import_data(
    data: ImportData,
    *,
    client: Any = supabase_admin,
    dry_run: bool = False,
    deactivate_missing: bool = False,
    generate_review_answers: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")

    summary = {
        "topics": len(data.topics),
        "exercises": len(data.exercises),
        "questions": len(data.questions),
        "deactivated": 0,
    }
    if dry_run:
        return summary

    if generate_review_answers:
        generated, reused = _enrich_review_answers(
            data, client=client, batch_size=batch_size
        )
        print(f"[INFO] review answers: generated {generated}, reused {reused}")

    _upsert_rows(client, TOPICS_TABLE, data.topics, batch_size)
    topic_ids = _fetch_id_map(
        client, TOPICS_TABLE, [row["source_key"] for row in data.topics], batch_size
    )

    exercise_rows = []
    for original in data.exercises:
        row = dict(original)
        parent_key = row.pop("_topic_source_key")
        row["topic_id"] = topic_ids[parent_key]
        exercise_rows.append(row)
    _upsert_rows(client, EXERCISES_TABLE, exercise_rows, batch_size)
    exercise_ids = _fetch_id_map(
        client,
        EXERCISES_TABLE,
        [row["source_key"] for row in exercise_rows],
        batch_size,
    )

    question_rows = []
    for original in data.questions:
        row = dict(original)
        parent_key = row.pop("_exercise_source_key")
        row["exercise_id"] = exercise_ids[parent_key]
        question_rows.append(row)
    _upsert_rows(client, QUESTIONS_TABLE, question_rows, batch_size)

    if deactivate_missing:
        topic_deactivated, all_topic_ids = _deactivate_missing(
            client,
            TOPICS_TABLE,
            data.document_id,
            [row["source_key"] for row in data.topics],
        )
        exercise_deactivated, all_exercise_ids = _deactivate_missing_children(
            client,
            EXERCISES_TABLE,
            "topic_id",
            all_topic_ids,
            [row["source_key"] for row in exercise_rows],
            batch_size,
        )
        question_deactivated, _ = _deactivate_missing_children(
            client,
            QUESTIONS_TABLE,
            "exercise_id",
            all_exercise_ids,
            [row["source_key"] for row in question_rows],
            batch_size,
        )
        summary["deactivated"] = (
            topic_deactivated + exercise_deactivated + question_deactivated
        )
    return summary


def load_and_prepare(path: Path) -> tuple[ImportData | None, List[str]]:
    if not path.is_file():
        return None, [f"File not found: {path}"]
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON in {path}: {exc}"]
    return prepare_import(payload)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import parsed exercise-bank v2 JSON into Supabase."
    )
    parser.add_argument("file", type=Path, help="Parsed exercise-bank JSON file.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate and summarize without connecting to or changing Supabase.",
    )
    parser.add_argument(
        "--deactivate-missing", action="store_true",
        help="Mark records missing from this document import inactive.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--skip-review-answer-generation",
        action="store_true",
        help="Import without generating polished learner-facing review answers.",
    )
    args = parser.parse_args()

    data, errors = load_and_prepare(args.file)
    if errors:
        print("[ERROR] Import validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)
    assert data is not None

    print(
        f"[VALID] {len(data.topics)} topics, {len(data.exercises)} exercises, "
        f"{len(data.questions)} questions"
    )
    summary = import_data(
        data,
        dry_run=args.dry_run,
        deactivate_missing=args.deactivate_missing,
        generate_review_answers=not args.skip_review_answer_generation,
        batch_size=args.batch_size,
    )
    label = "DRY RUN" if args.dry_run else "SUCCESS"
    print(
        f"[{label}] Topics: {summary['topics']} | Exercises: {summary['exercises']} | "
        f"Questions: {summary['questions']} | Deactivated: {summary['deactivated']}"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Import parsed exercise-bank v2 JSON into the three normalized Supabase tables.

Usage:
    python -m app.tools.exercise_bank_v2_importer data/exercise_bank.json --dry-run
    python -m app.tools.exercise_bank_v2_importer data/exercise_bank.json
    python -m app.tools.exercise_bank_v2_importer data/exercise_bank_th.json \
        --lang th --english-source data/exercise_bank.json --dry-run

Normal imports generate polished learner-facing review answers. Use
``--skip-review-answer-generation`` only for parser/import diagnostics.

The importer is idempotent: all three tables are upserted by ``source_key``.
Records absent from an import are left alone unless ``--deactivate-missing`` is used.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import unicodedata
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


@dataclass
class ThaiImportData:
    topics: List[Dict[str, Any]]
    exercises: List[Dict[str, Any]]
    questions: List[Dict[str, Any]]
    skipped_thai_examples: List[str]
    unmatched_thai: List[str]
    unmatched_english: List[str]


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


THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
OPTION_RE = re.compile(r"^\s*([A-Za-z])\.\s*(.*?)\s*$", re.DOTALL)


def _normalized_anchor(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("‘", "'").replace("’", "'")
    text = re.sub(r"_+", " <blank> ", text)
    text = re.sub(r"[^\w<>']+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _english_lines(value: Any) -> List[str]:
    if not isinstance(value, str):
        return []
    result: List[str] = []
    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line or THAI_RE.search(line):
            continue
        option_match = OPTION_RE.match(line)
        result.append(option_match.group(2) if option_match else line)
    return result


def _english_question_anchors(content: Mapping[str, Any]) -> set[str]:
    candidates: List[str] = []
    for field in ("text", "stem"):
        candidates.extend(_english_lines(content.get(field)))
    options = content.get("options")
    if isinstance(options, list):
        for option in options:
            if isinstance(option, dict):
                candidates.extend(_english_lines(option.get("text")))
            else:
                candidates.extend(_english_lines(option))
    return {anchor for value in candidates if (anchor := _normalized_anchor(value))}


def _thai_item_anchors(item: Mapping[str, Any]) -> set[str]:
    candidates = _english_lines(item.get("text"))
    options = item.get("options")
    if isinstance(options, list):
        for option in options:
            if isinstance(option, dict):
                candidates.extend(_english_lines(option.get("text")))
            else:
                candidates.extend(_english_lines(option))
    return {anchor for value in candidates if (anchor := _normalized_anchor(value))}


def _localized_options(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: List[Dict[str, str]] = []
    for raw_option in value:
        if isinstance(raw_option, dict):
            label = str(raw_option.get("label") or "").strip().upper()
            text = str(raw_option.get("text") or "").strip()
            if label and text:
                result.append({"label": label, "text": text})
            continue
        text = str(raw_option or "").strip()
        if not text:
            continue
        match = OPTION_RE.match(text)
        if match:
            result.append({"label": match.group(1).upper(), "text": match.group(2).strip()})
        elif result and THAI_RE.search(text):
            result[-1]["text"] = f"{result[-1]['text']}\n{text}"
    return result


def _localized_question_content(
    item: Mapping[str, Any], english_content: Mapping[str, Any]
) -> Dict[str, Any]:
    localized: Dict[str, Any] = {}
    text = str(item.get("text") or "").strip()
    if text:
        target_field = "stem" if _non_empty(english_content.get("stem")) else "text"
        localized[target_field] = text
    options = _localized_options(item.get("options"))
    if options:
        localized["options"] = options
    return localized


def _localized_display_type(exercise: Mapping[str, Any]) -> str:
    kind = str(exercise.get("kind") or "")
    title = exercise.get("title")
    english_title = str(title.get("en") or "") if isinstance(title, dict) else ""
    if kind == "fill_blank":
        return "🧩 เติมคำในช่องว่าง"
    if kind == "multiple_choice":
        return "🔘 เลือกคำตอบที่ถูกต้อง"
    if "CORRECT OR INCORRECT" in english_title.upper():
        return "✅❌ ถูกหรือผิด?"
    return "✏️ เขียนประโยคใหม่"


def _thai_exercise_prompt(exercise: Mapping[str, Any]) -> str | None:
    prompt = exercise.get("prompt")
    if not isinstance(prompt, dict):
        return None
    value = str(prompt.get("th") or "").strip()
    return value or None


def _question_is_example(item: Mapping[str, Any]) -> bool:
    return bool(item.get("is_example")) or str(item.get("number") or "").casefold() == "example"


def prepare_thai_import(
    thai_payload: Any, english_payload: Any
) -> tuple[ThaiImportData | None, List[str]]:
    """Align legacy Thai parser output to existing v2 English source keys."""
    errors: List[str] = []
    english_data, english_errors = prepare_import(english_payload)
    if english_errors or english_data is None:
        return None, [f"English source: {error}" for error in english_errors]
    if not isinstance(thai_payload, list):
        return None, ["Thai parser output must be an array of section objects."]
    if len(thai_payload) != len(english_data.topics):
        errors.append(
            f"Thai topic count ({len(thai_payload)}) does not match English "
            f"topic count ({len(english_data.topics)})."
        )

    english_exercises_by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for exercise in english_data.exercises:
        english_exercises_by_topic.setdefault(exercise["_topic_source_key"], []).append(exercise)
    english_questions_by_exercise: Dict[str, List[Dict[str, Any]]] = {}
    for question in english_data.questions:
        english_questions_by_exercise.setdefault(
            question["_exercise_source_key"], []
        ).append(question)

    topic_updates: List[Dict[str, Any]] = []
    exercise_updates: Dict[str, Dict[str, Any]] = {}
    question_updates: Dict[str, Dict[str, Any]] = {}
    skipped_thai_examples: List[str] = []
    unmatched_thai: List[str] = []
    matched_english_questions: set[str] = set()

    for topic_index, (thai_section, english_topic) in enumerate(
        zip(thai_payload, english_data.topics), start=1
    ):
        if not isinstance(thai_section, dict):
            errors.append(f"Thai section {topic_index} must be an object.")
            continue
        section = thai_section.get("section")
        thai_exercises = thai_section.get("exercises")
        if not isinstance(section, dict) or not isinstance(thai_exercises, list):
            errors.append(
                f"Thai section {topic_index} must contain a section object and exercises array."
            )
            continue
        title_th = str(section.get("title_th") or "").strip()
        if not title_th:
            errors.append(f"Thai section {topic_index} has no Thai title.")
            continue
        topic_updates.append(
            {
                "source_key": english_topic["source_key"],
                "topic_th": title_th,
                "display_title_th": title_th,
            }
        )

        english_exercises = english_exercises_by_topic.get(
            english_topic["source_key"], []
        )
        english_question_records: List[Dict[str, Any]] = []
        for english_exercise in english_exercises:
            for english_question in english_questions_by_exercise.get(
                english_exercise["source_key"], []
            ):
                english_question_records.append(
                    {
                        "exercise": english_exercise,
                        "question": english_question,
                        "anchors": _english_question_anchors(
                            english_question.get("content") or {}
                        ),
                    }
                )

        for thai_exercise_index, thai_exercise in enumerate(thai_exercises, start=1):
            if not isinstance(thai_exercise, dict):
                errors.append(
                    f"Thai section {topic_index} exercise {thai_exercise_index} must be an object."
                )
                continue
            kind = thai_exercise.get("kind")
            items = thai_exercise.get("items_th")
            if kind not in SUPPORTED_TYPES or not isinstance(items, list):
                errors.append(
                    f"Thai section {topic_index} exercise {thai_exercise_index} is malformed."
                )
                continue

            item_candidates: List[tuple[Mapping[str, Any], List[tuple[int, Dict[str, Any]]]]] = []
            parent_scores: Dict[str, int] = {}
            for item in items:
                if not isinstance(item, dict):
                    continue
                anchors = _thai_item_anchors(item)
                is_example = _question_is_example(item)
                candidates: List[tuple[int, Dict[str, Any]]] = []
                for record in english_question_records:
                    english_exercise = record["exercise"]
                    english_question = record["question"]
                    if english_exercise.get("exercise_type") != kind:
                        continue
                    if bool(english_question.get("is_example")) != is_example:
                        continue
                    score = len(anchors & record["anchors"])
                    if score:
                        candidates.append((score, record))
                        parent_key = english_exercise["source_key"]
                        parent_scores[parent_key] = parent_scores.get(parent_key, 0) + score
                item_candidates.append((item, candidates))

            if not parent_scores:
                unmatched_thai.append(
                    f"section {topic_index} exercise {thai_exercise_index}: no English exercise match"
                )
                continue
            best_parent_score = max(parent_scores.values())
            best_parents = [
                key for key, score in parent_scores.items() if score == best_parent_score
            ]
            if len(best_parents) != 1:
                unmatched_thai.append(
                    f"section {topic_index} exercise {thai_exercise_index}: ambiguous English exercise match"
                )
                continue
            parent_key = best_parents[0]
            prompt_th = _thai_exercise_prompt(thai_exercise)
            proposed_exercise = {
                "source_key": parent_key,
                "display_type_th": _localized_display_type(thai_exercise),
                "prompt_th": prompt_th,
            }
            existing_exercise = exercise_updates.get(parent_key)
            if existing_exercise:
                for field in ("display_type_th", "prompt_th"):
                    current = existing_exercise.get(field)
                    proposed = proposed_exercise.get(field)
                    if current and proposed and current != proposed:
                        unmatched_thai.append(
                            f"section {topic_index} exercise {thai_exercise_index}: "
                            f"conflicting {field} for English exercise {parent_key}"
                        )
            else:
                exercise_updates[parent_key] = proposed_exercise

            for item, candidates in item_candidates:
                candidates = [
                    candidate for candidate in candidates
                    if candidate[1]["exercise"]["source_key"] == parent_key
                ]
                if not candidates:
                    issue = (
                        f"section {topic_index} exercise {thai_exercise_index} item "
                        f"{item.get('number')}: no English question match"
                    )
                    if _question_is_example(item):
                        skipped_thai_examples.append(issue)
                    else:
                        unmatched_thai.append(issue)
                    continue
                highest = max(score for score, _ in candidates)
                best = [record for score, record in candidates if score == highest]
                unused = [
                    record for record in best
                    if record["question"]["source_key"] not in matched_english_questions
                ]
                if len(unused) == 1:
                    matched = unused[0]
                elif len(best) == 1 and best[0]["question"]["source_key"] not in matched_english_questions:
                    matched = best[0]
                else:
                    source_number = str(item.get("number") or "").strip().casefold()
                    numbered = [
                        record for record in unused
                        if str(record["question"].get("source_number") or "").strip().casefold()
                        == source_number
                    ]
                    if len(numbered) != 1:
                        issue = (
                            f"section {topic_index} exercise {thai_exercise_index} item "
                            f"{item.get('number')}: ambiguous English question match"
                        )
                        if _question_is_example(item):
                            skipped_thai_examples.append(issue)
                        else:
                            unmatched_thai.append(issue)
                        continue
                    matched = numbered[0]
                question = matched["question"]
                question_key = question["source_key"]
                matched_english_questions.add(question_key)
                localized_content = _localized_question_content(
                    item, question.get("content") or {}
                )
                if not localized_content:
                    unmatched_thai.append(
                        f"section {topic_index} exercise {thai_exercise_index} item "
                        f"{item.get('number')}: no localized display content"
                    )
                    continue
                question_updates[question_key] = {
                    "source_key": question_key,
                    "content_th": localized_content,
                }

    all_english_question_keys = {row["source_key"] for row in english_data.questions}
    unmatched_english = sorted(all_english_question_keys - matched_english_questions)
    return ThaiImportData(
        topics=topic_updates,
        exercises=list(exercise_updates.values()),
        questions=list(question_updates.values()),
        skipped_thai_examples=skipped_thai_examples,
        unmatched_thai=unmatched_thai,
        unmatched_english=unmatched_english,
    ), errors


def _execute_with_retry(builder: Any, label: str, retries: int = 3) -> Any:
    attempt = 0
    while True:
        try:
            return builder.execute()
        except (httpx.TransportError, APIError) as exc:
            attempt += 1
            message = str(getattr(exc, "message", exc)).lower()
            code = str(getattr(exc, "code", ""))
            transient = isinstance(exc, httpx.TransportError) or code in {
                "502", "503", "504"
            } or any(
                marker in message
                for marker in ("bad gateway", "service unavailable", "gateway timeout")
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
    client: Any,
    table: str,
    rows: Sequence[Dict[str, Any]],
    batch_size: int,
    *,
    on_conflict: str = "source_key",
) -> None:
    batches = list(_chunks(rows, batch_size))
    for number, batch in enumerate(batches, start=1):
        response = _execute_with_retry(
            client.table(table).upsert(batch, on_conflict=on_conflict),
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


def _merge_translations_with_existing_rows(
    client: Any,
    table: str,
    translations: Sequence[Dict[str, Any]],
    batch_size: int,
) -> List[Dict[str, Any]]:
    """Build complete rows so translation upserts satisfy every NOT NULL column."""
    by_key = {row["source_key"]: row for row in translations}
    existing_by_key: Dict[str, Dict[str, Any]] = {}
    for batch in _chunks(list(by_key), batch_size):
        response = _execute_with_retry(
            client.table(table).select("*").in_("source_key", batch),
            f"load existing rows from {table}",
        )
        for row in getattr(response, "data", None) or []:
            source_key = row.get("source_key")
            if source_key in existing_by_key:
                raise RuntimeError(
                    f"Multiple {table} rows use source_key '{source_key}'."
                )
            existing_by_key[source_key] = row
    missing = sorted(set(by_key) - set(existing_by_key))
    if missing:
        raise RuntimeError(
            f"Could not resolve {len(missing)} existing row(s) from {table}."
        )
    return [
        {**existing_by_key[source_key], **by_key[source_key]}
        for source_key in by_key
    ]


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


def import_thai_data(
    data: ThaiImportData,
    *,
    client: Any = supabase_admin,
    dry_run: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, int]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    summary = {
        "topics": len(data.topics),
        "exercises": len(data.exercises),
        "questions": len(data.questions),
        "skipped_thai_examples": len(data.skipped_thai_examples),
        "unmatched_thai": len(data.unmatched_thai),
        "unmatched_english": len(data.unmatched_english),
    }
    if dry_run:
        return summary

    # Postgres validates NOT NULL columns before resolving an upsert conflict. Merge
    # each localized patch onto its live row, then conflict on the immutable primary ID.
    topic_rows = _merge_translations_with_existing_rows(
        client, TOPICS_TABLE, data.topics, batch_size
    )
    exercise_rows = _merge_translations_with_existing_rows(
        client, EXERCISES_TABLE, data.exercises, batch_size
    )
    question_rows = _merge_translations_with_existing_rows(
        client, QUESTIONS_TABLE, data.questions, batch_size
    )
    _upsert_rows(client, TOPICS_TABLE, topic_rows, batch_size, on_conflict="id")
    _upsert_rows(client, EXERCISES_TABLE, exercise_rows, batch_size, on_conflict="id")
    _upsert_rows(client, QUESTIONS_TABLE, question_rows, batch_size, on_conflict="id")
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


def _load_json(path: Path) -> tuple[Any | None, List[str]]:
    if not path.is_file():
        return None, [f"File not found: {path}"]
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle), []
    except json.JSONDecodeError as exc:
        return None, [f"Invalid JSON in {path}: {exc}"]


def _print_alignment_issues(data: ThaiImportData, limit: int = 25) -> None:
    if data.skipped_thai_examples:
        print(
            f"[WARN] {len(data.skipped_thai_examples)} extra/duplicate Thai "
            "example(s) have no live English row and will be skipped:"
        )
        for issue in data.skipped_thai_examples[:limit]:
            print(f"  - {issue}")
        if len(data.skipped_thai_examples) > limit:
            print(f"  ... {len(data.skipped_thai_examples) - limit} more")
    if data.unmatched_thai:
        print(f"[WARN] {len(data.unmatched_thai)} unmatched Thai item(s):")
        for issue in data.unmatched_thai[:limit]:
            print(f"  - {issue}")
        if len(data.unmatched_thai) > limit:
            print(f"  ... {len(data.unmatched_thai) - limit} more")
    if data.unmatched_english:
        print(f"[WARN] {len(data.unmatched_english)} English question(s) have no Thai match.")
        for source_key in data.unmatched_english[:limit]:
            print(f"  - {source_key}")
        if len(data.unmatched_english) > limit:
            print(f"  ... {len(data.unmatched_english) - limit} more")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import parsed exercise-bank v2 JSON into Supabase."
    )
    parser.add_argument("file", type=Path, help="Parsed exercise-bank JSON file.")
    parser.add_argument(
        "--lang", choices=("en", "th"), default="en",
        help="Import English v2 content or update Thai fields (default: en).",
    )
    parser.add_argument(
        "--english-source", type=Path,
        help="English v2 parser output used to align a Thai import.",
    )
    parser.add_argument(
        "--allow-partial", action="store_true",
        help="Allow a Thai import to skip unmatched content. Never implicit.",
    )
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

    if args.lang == "th":
        if args.english_source is None:
            parser.error("--english-source is required with --lang th")
        if args.deactivate_missing:
            parser.error("--deactivate-missing cannot be used with --lang th")

        thai_payload, thai_errors = _load_json(args.file)
        english_payload, english_errors = _load_json(args.english_source)
        errors = thai_errors + english_errors
        data = None
        if not errors:
            data, errors = prepare_thai_import(thai_payload, english_payload)
        if errors:
            print("[ERROR] Thai import validation failed:")
            for error in errors:
                print(f"  - {error}")
            raise SystemExit(1)
        assert data is not None

        print(
            f"[VALID] {len(data.topics)} topic translations, "
            f"{len(data.exercises)} exercise translations, "
            f"{len(data.questions)} question translations"
        )
        _print_alignment_issues(data)
        if (data.unmatched_thai or data.unmatched_english) and not args.allow_partial:
            print(
                "[ERROR] Thai alignment is incomplete. No rows were changed. "
                "Fix the source drift or pass --allow-partial explicitly."
            )
            raise SystemExit(1)
        summary = import_thai_data(
            data,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
        )
        label = "DRY RUN" if args.dry_run else "SUCCESS"
        print(
            f"[{label}] Topics: {summary['topics']} | Exercises: {summary['exercises']} | "
            f"Questions: {summary['questions']} | Unmatched Thai: "
            f"{summary['unmatched_thai']} | Skipped Thai examples: "
            f"{summary['skipped_thai_examples']} | Unmatched English: "
            f"{summary['unmatched_english']}"
        )
        return

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

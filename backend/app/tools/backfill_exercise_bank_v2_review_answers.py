#!/usr/bin/env python3
"""Backfill polished Exercise Bank v2 review answers for existing questions."""

from __future__ import annotations

import argparse
from typing import Any

from openai import OpenAI

from app.supabase_client import supabase_admin
from app.tools.exercise_bank_v2_review_answers import (
    enrich_question_content,
    existing_review_answer_is_current,
    review_answer_source_hash,
)

PAGE_SIZE = 1000


def _fetch_all_rows(
    client: Any,
    table: str,
    columns: str,
    *,
    filters: tuple[tuple[str, Any], ...] = (),
    limit: int | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while limit is None or len(rows) < limit:
        remaining = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - len(rows))
        query = client.table(table).select(columns)
        for column, value in filters:
            query = query.eq(column, value)
        response = query.order("id").range(start, start + remaining - 1).execute()
        page = getattr(response, "data", None) or []
        rows.extend(page)
        if len(page) < remaining:
            break
        start += len(page)
    return rows


def backfill_review_answers(
    *, client: Any = supabase_admin, dry_run: bool = False, limit: int | None = None
) -> dict[str, int]:
    exercise_rows = _fetch_all_rows(
        client,
        "exercise_bank_exercises",
        "id,exercise_type,display_type,prompt",
        filters=(("is_active", True),),
    )
    exercises = {
        row["id"]: row for row in exercise_rows
    }
    questions = _fetch_all_rows(
        client,
        "exercise_bank_questions",
        "id,source_key,exercise_id,is_example,content",
        filters=(("is_active", True), ("is_example", False)),
        limit=limit,
    )

    pending: list[tuple[dict[str, Any], dict[str, Any]]] = []
    current = 0
    for question in questions:
        exercise = exercises.get(question.get("exercise_id"))
        content = question.get("content")
        if not exercise or not isinstance(content, dict):
            continue
        source_hash = review_answer_source_hash(
            exercise_type=exercise["exercise_type"],
            display_type=exercise["display_type"],
            prompt=exercise["prompt"],
            content=content,
        )
        if existing_review_answer_is_current(content, source_hash):
            current += 1
        else:
            pending.append((question, exercise))

    summary = {"scanned": len(questions), "current": current, "generated": 0}
    print(
        f"[INFO] scanned {summary['scanned']} questions; "
        f"{summary['current']} current; {len(pending)} pending"
    )
    if dry_run or not pending:
        return summary

    ai_client = OpenAI()
    for index, (question, exercise) in enumerate(pending, start=1):
        enriched, _ = enrich_question_content(
            exercise_type=exercise["exercise_type"],
            display_type=exercise["display_type"],
            prompt=exercise["prompt"],
            content=question["content"],
            client=ai_client,
        )
        client.table("exercise_bank_questions").update({"content": enriched}).eq(
            "id", question["id"]
        ).execute()
        summary["generated"] += 1
        print(
            f"[INFO] backfill {index}/{len(pending)}: "
            f"{question.get('source_key') or question['id']}"
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill polished learner-facing Exercise Bank v2 answers."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    summary = backfill_review_answers(dry_run=args.dry_run, limit=args.limit)
    print(
        f"[DONE] Scanned: {summary['scanned']} | Current: {summary['current']} | "
        f"Generated: {summary['generated']}"
    )


if __name__ == "__main__":
    main()

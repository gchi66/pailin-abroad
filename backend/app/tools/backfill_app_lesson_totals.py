#!/usr/bin/env python3
"""
Backfill lessons.app_total_units using the current app lesson expectation builder.

Usage:
  python -m app.tools.backfill_app_lesson_totals
  python -m app.tools.backfill_app_lesson_totals --lesson-id <uuid>
  python -m app.tools.backfill_app_lesson_totals --dry-run
"""

from __future__ import annotations

import argparse

from app.app_lesson_progress import refresh_app_total_units_for_lessons
from app.supabase_client import supabase


def _fetch_lesson_ids(target_lesson_ids=None):
    if target_lesson_ids:
        return [lesson_id for lesson_id in target_lesson_ids if lesson_id]

    result = (
        supabase.table("lessons")
        .select("id")
        .order("stage", desc=False)
        .order("level", desc=False)
        .order("lesson_order", desc=False)
        .execute()
    )
    return [row.get("id") for row in (result.data or []) if row.get("id")]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill lessons.app_total_units.")
    parser.add_argument("--lesson-id", action="append", dest="lesson_ids", help="Specific lesson id to backfill. Repeatable.")
    parser.add_argument("--dry-run", action="store_true", help="Compute totals without writing them.")
    args = parser.parse_args()

    lesson_ids = _fetch_lesson_ids(args.lesson_ids)
    if not lesson_ids:
        print("[INFO] No lessons found.")
        return

    totals_by_lesson = refresh_app_total_units_for_lessons(
        lesson_ids,
        persist=not args.dry_run,
    )

    print(f"[INFO] Computed app_total_units for {len(totals_by_lesson)} lessons.")
    for lesson_id in lesson_ids[:10]:
        print(f"  {lesson_id}: {totals_by_lesson.get(lesson_id, 0)}")
    if len(lesson_ids) > 10:
        print(f"  ... {len(lesson_ids) - 10} more lessons omitted.")


if __name__ == "__main__":
    main()

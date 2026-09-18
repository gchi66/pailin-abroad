"""Backfill reviewed bilingual Lesson Library card labels.

Run from backend/ after adding focus_short and focus_short_th to public.lessons:
    python -m app.tools.backfill_short_lesson_focus
    python -m app.tools.backfill_short_lesson_focus --apply

The first command previews changes. Existing nonempty labels are never replaced
unless --overwrite-existing is also supplied.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_FILE = Path(__file__).resolve().parents[2] / "data" / "lesson_focus_short.json"
FIELDS = ("focus_short", "focus_short_th")


def lesson_key(row: dict) -> tuple[str, int, int]:
    return row["stage"], row["level"], row["lesson_order"]


def load_labels(path: Path) -> list[dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    rows = document.get("lessons")
    if not isinstance(rows, list) or not rows:
        raise ValueError("The JSON file must contain a nonempty 'lessons' list.")

    seen = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Lesson {index} must be an object.")
        if not isinstance(row.get("stage"), str) or not row["stage"].strip():
            raise ValueError(f"Lesson {index} needs a stage.")
        for field in ("level", "lesson_order"):
            if type(row.get(field)) is not int or row[field] < 1:
                raise ValueError(f"Lesson {index} needs a positive integer {field}.")
        key = lesson_key(row)
        if key in seen:
            raise ValueError(f"Duplicate lesson key: {key}.")
        seen.add(key)
        for field in FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"Lesson {row.get('external_id', key)} needs a trimmed {field}.")

    return rows


def fetch_existing_lessons(client) -> dict[tuple[str, int, int], dict]:
    rows = {}
    offset = 0
    page_size = 500
    while True:
        result = (
            client.table("lessons")
            .select("id,stage,level,lesson_order,focus_short,focus_short_th")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = result.data or []
        for row in page:
            key = lesson_key(row)
            if key in rows:
                raise ValueError(f"Database has duplicate lesson key: {key}.")
            rows[key] = row
        if len(page) < page_size:
            break
        offset += page_size
    return rows


def plan_updates(labels: list[dict], existing: dict, overwrite_existing: bool) -> tuple[list[tuple[str, str, dict]], list[str]]:
    changes = []
    errors = []
    for label in labels:
        number = label.get("external_id") or str(lesson_key(label))
        current = existing.get(lesson_key(label))
        if current is None:
            errors.append(f"{number}: no matching database lesson")
            continue

        update = {}
        for field in FIELDS:
            previous = current.get(field)
            desired = label[field]
            if previous == desired:
                continue
            if previous and not overwrite_existing:
                errors.append(f"{number}: {field} already has different text; review it or use --overwrite-existing")
                continue
            update[field] = desired
        if update:
            changes.append((number, current["id"], update))
    return changes, errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help="Reviewed label JSON file.")
    parser.add_argument("--apply", action="store_true", help="Write the labels to Supabase; default is preview only.")
    parser.add_argument("--overwrite-existing", action="store_true", help="Replace nonempty labels that differ from the JSON file.")
    args = parser.parse_args()

    labels = load_labels(args.file)
    # Import the client only after file validation, so local JSON checks need no credentials.
    from app.supabase_client import supabase_admin

    existing = fetch_existing_lessons(supabase_admin)
    changes, errors = plan_updates(labels, existing, args.overwrite_existing)
    print(f"Loaded {len(labels)} labels; found {len(existing)} database lessons; {len(changes)} rows need updates.")
    if errors:
        print("Preflight failed; no rows were changed:")
        for error in errors:
            print(f"  {error}")
        raise SystemExit(1)
    if not args.apply:
        for number, _, update in changes[:10]:
            print(f"  {number}: {', '.join(update)}")
        if len(changes) > 10:
            print(f"  ... and {len(changes) - 10} more")
        print("Preview only. Add --apply to write these labels.")
        return

    for index, (number, lesson_id, update) in enumerate(changes, start=1):
        try:
            result = supabase_admin.table("lessons").update(update).eq("id", lesson_id).execute()
            if len(result.data or []) != 1:
                raise RuntimeError("Database did not return exactly one updated row.")
        except Exception as exc:
            raise RuntimeError(f"Stopped at {number} after {index - 1} updates; rerun safely after fixing the error.") from exc
    print(f"Updated {len(changes)} lessons. Other lesson fields were untouched.")


if __name__ == "__main__":
    main()

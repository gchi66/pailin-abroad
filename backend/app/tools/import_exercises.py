#!/usr/bin/env python3
"""
Import exercise bank data into Supabase.

Supports two modes:
  --lang en  (default): insert/update base English rows.
  --lang th             update Thai fields on existing rows.

Usage:
  python -m app.tools.import_exercises data/exercise_bank.json
  python -m app.tools.import_exercises data/exercise_bank_th.json --lang th
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from app.supabase_client import supabase


def _ensure_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_sections(payload: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate top-level section objects and normalise core attributes.
    """
    errors: List[str] = []
    if not isinstance(payload, list):
        return [], ["Root JSON must be an array of section objects."]

    cleaned: List[Dict[str, Any]] = []
    last_category: str = ""
    for idx, section in enumerate(payload, start=1):
        ctx = f"Section[{idx}]"
        if not isinstance(section, dict):
            errors.append(f"{ctx}: section must be an object.")
            continue

        category = _ensure_str(section.get("category"))
        if not category and last_category:
            # Translation payloads sometimes omit category; reuse the previous one.
            category = last_category
        sec_info = section.get("section") or {}
        if not isinstance(sec_info, dict):
            errors.append(f"{ctx}: 'section' must be an object.")
            continue

        title_en = _ensure_str(sec_info.get("title_en") or sec_info.get("title"))
        title_th = _ensure_str(sec_info.get("title_th"))
        description = _ensure_str(sec_info.get("description"))
        display_title = title_en or title_th

        if category:
            last_category = category
        if not category:
            errors.append(f"{ctx}: 'category' must be a non-empty string.")
        if not display_title:
            errors.append(f"{ctx}: section title missing (title_en/title_th).")

        exercises = section.get("exercises")
        if not isinstance(exercises, list) or not exercises:
            errors.append(f"{ctx}: 'exercises' must be a non-empty array.")

        cleaned.append(
            {
                "category": category,
                "section_title_en": title_en,
                "section_title_th": title_th,
                "section_title": display_title,
                "section_description": description,
                "exercises": exercises or [],
            }
        )

    return cleaned, errors


def _prepare_rows_en(sections: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Build insert payloads for the English import pass.
    """
    rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    for sec_idx, section in enumerate(sections, start=1):
        ctx_section = f"Section[{sec_idx}]"
        section_key = section["section_title_en"] or section["section_title"]
        if not section_key:
            errors.append(f"{ctx_section}: Cannot determine section title for English import.")
            continue

        for ex_idx, exercise in enumerate(section["exercises"], start=1):
            ctx = f"{ctx_section} Exercise[{ex_idx}]"
            if not isinstance(exercise, dict):
                errors.append(f"{ctx}: exercise must be an object.")
                continue

            kind = _ensure_str(exercise.get("kind"))
            if not kind:
                errors.append(f"{ctx}: 'kind' must be a non-empty string.")
                continue

            items = exercise.get("items")
            if not isinstance(items, list):
                errors.append(f"{ctx}: 'items' must be an array for English import.")
                continue
            title_data = exercise.get("title")
            if isinstance(title_data, dict):
                title_en = _ensure_str(title_data.get("en"))
                title_th = _ensure_str(title_data.get("th"))
            else:
                title_en = _ensure_str(exercise.get("title_en") or title_data)
                title_th = _ensure_str(exercise.get("title_th"))

            prompt_data = exercise.get("prompt")
            if isinstance(prompt_data, dict):
                prompt_en = _ensure_str(prompt_data.get("en"))
                prompt_th = _ensure_str(prompt_data.get("th"))
            else:
                prompt_en = _ensure_str(exercise.get("prompt_en") or prompt_data)
                prompt_th = _ensure_str(exercise.get("prompt_th"))

            if not title_en:
                errors.append(f"{ctx}: English title missing (title/title_en).")
                continue

            row = {
                "category": section["category"],
                "section": section_key,
                "section_th": section.get("section_title_th") or None,
                "exercise_type": kind,
                "title": title_en or None,
                "title_th": title_th or None,
                "prompt": prompt_en or None,
                "prompt_th": prompt_th or None,
                "items": items,
                "items_th": exercise.get("items_th") if isinstance(exercise.get("items_th"), list) else [],
                "is_featured": bool(exercise.get("is_featured", False)),
            }
            rows.append(row)

    return rows, errors


def _prepare_updates_th(sections: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Build update payloads for the Thai import pass.
    Matches exercises by section + title_en.
    """
    updates: List[Dict[str, Any]] = []
    errors: List[str] = []

    for sec_idx, section in enumerate(sections, start=1):
        ctx_section = f"Section[{sec_idx}]"
        section_key = section["section_title_en"] or section["section_title"]
        if not section_key:
            errors.append(f"{ctx_section}: Cannot determine section title for Thai import.")
            continue

        for ex_idx, exercise in enumerate(section["exercises"], start=1):
            ctx = f"{ctx_section} Exercise[{ex_idx}]"
            if not isinstance(exercise, dict):
                errors.append(f"{ctx}: exercise must be an object.")
                continue

            kind = _ensure_str(exercise.get("kind"))
            if not kind:
                errors.append(f"{ctx}: 'kind' must be a non-empty string.")
                continue

            title_data = exercise.get("title")
            if isinstance(title_data, dict):
                title_en = _ensure_str(title_data.get("en"))
                title_th = _ensure_str(title_data.get("th"))
            else:
                title_en = _ensure_str(exercise.get("title_en"))
                title_th = _ensure_str(exercise.get("title_th"))

            if not title_en:
                errors.append(f"{ctx}: English title missing (needed for matching).")
                continue

            prompt_data = exercise.get("prompt")
            if isinstance(prompt_data, dict):
                prompt_th = _ensure_str(prompt_data.get("th"))
            else:
                prompt_th = _ensure_str(exercise.get("prompt_th"))

            items_th = exercise.get("items_th")
            if items_th is None:
                items_th = exercise.get("items")
            if not isinstance(items_th, list):
                errors.append(f"{ctx}: 'items_th' must be an array for Thai import.")
                continue

            updates.append(
                {
                    "category": section["category"],
                    "section": section_key,
                    "section_title_th": section.get("section_title_th") or None,
                    "title_en": title_en,
                    "exercise_type": kind,
                    "title_th": title_th or None,
                    "prompt_th": prompt_th or None,
                    "items_th": items_th,
                }
            )

    return updates, errors


def _delete_existing(rows: Iterable[Dict[str, Any]], dry_run: bool = False) -> None:
    combos = {(row["category"], row["section"]) for row in rows}
    for category, section in combos:
        if dry_run:
            print(f"[DRY RUN] Would delete existing rows where category='{category}' and section='{section}'.")
            continue
        resp = (
            supabase.table("exercise_bank")
            .delete()
            .eq("category", category)
            .eq("section", section)
            .execute()
        )
        if not getattr(resp, "data", None):
            print(f"[WARN] Delete returned no data for category='{category}' section='{section}'.")


def _insert_rows(rows: List[Dict[str, Any]], dry_run: bool = False, batch_size: int = 50) -> None:
    if dry_run:
        print(f"[DRY RUN] Would insert {len(rows)} rows into exercise_bank.")
        for row in rows[:5]:
            print(
                f"  → {row['category']} / {row['section']} [{row['exercise_type']}] "
                f"title='{row['title']}' items={len(row['items'])}"
            )
        if len(rows) > 5:
            print(f"  ... {len(rows) - 5} more rows omitted.")
        return

    total = len(rows)
    if not total:
        print("[INFO] No rows to insert.")
        return

    batches = (total + batch_size - 1) // batch_size
    for i in range(batches):
        chunk = rows[i * batch_size : (i + 1) * batch_size]
        resp = supabase.table("exercise_bank").insert(chunk).execute()
        if not getattr(resp, "data", None):
            print(f"[WARN] Insert batch {i + 1}/{batches} returned no data.")
        else:
            print(f"[INFO] Inserted batch {i + 1}/{batches} ({len(chunk)} rows).")


def _update_rows_th(updates: List[Dict[str, Any]], dry_run: bool = False) -> None:
    """
    Update Thai fields by matching on section + title (English title).
    """
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for update in updates:
        key = (update["category"], update["section"])
        grouped[key].append(update)

    for (category, section), update_list in grouped.items():
        if dry_run:
            print(
                f"[DRY RUN] Would update {len(update_list)} Thai rows for category='{category}' section='{section}'."
            )
            for upd in update_list[:5]:
                print(f"  → title_en='{upd['title_en']}' type={upd['exercise_type']} items={len(upd['items_th'])}")
            if len(update_list) > 5:
                print(f"  ... {len(update_list) - 5} more updates omitted.")
            continue

        # Fetch existing rows in this section
        resp = (
            supabase.table("exercise_bank")
            .select("id, title, exercise_type")
            .eq("category", category)
            .eq("section", section)
            .execute()
        )
        existing = getattr(resp, "data", []) or []

        # Build lookup: title -> row
        existing_by_title = {row["title"]: row for row in existing if row.get("title")}

        # Update the section_th value once per section if we have one.
        section_title_th = next((upd.get("section_title_th") for upd in update_list if upd.get("section_title_th")), None)
        if section_title_th:
            supabase.table("exercise_bank").update({"section_th": section_title_th}).eq("category", category).eq("section", section).execute()

        matched = 0
        unmatched = 0

        for update_payload in update_list:
            title_en = update_payload["title_en"]
            matching_row = existing_by_title.get(title_en)

            if not matching_row:
                print(
                    f"[WARN] No match found for title='{title_en}' in category='{category}' section='{section}'."
                )
                unmatched += 1
                continue

            # Verify exercise type matches
            if matching_row.get("exercise_type") != update_payload["exercise_type"]:
                print(
                    f"[WARN] Exercise type mismatch for title='{title_en}' "
                    f"(existing={matching_row.get('exercise_type')} "
                    f"update={update_payload['exercise_type']}) for row {matching_row.get('id')}."
                )

            payload = {
                "title_th": update_payload["title_th"],
                "prompt_th": update_payload["prompt_th"],
                "items_th": update_payload["items_th"],
            }
            if section_title_th:
                payload["section_th"] = section_title_th
            resp_update = supabase.table("exercise_bank").update(payload).eq("id", matching_row["id"]).execute()
            if not getattr(resp_update, "data", None):
                print(f"[WARN] Thai update failed for row id={matching_row['id']}.")
            else:
                matched += 1

        print(f"[INFO] Updated {matched} exercises in category='{category}' section='{section}' ({unmatched} unmatched).")


def import_exercises_from_file(path: Path, lang: str = "en", dry_run: bool = False) -> bool:
    if not path.is_file():
        print(f"[ERROR] File not found: {path}")
        return False

    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Invalid JSON in {path}: {exc}")
        return False

    sections, validation_errors = _normalize_sections(payload)
    if validation_errors:
        print("[ERROR] Section validation failed:")
        for err in validation_errors:
            print(f"  - {err}")
        return False

    if lang == "th":
        updates, update_errors = _prepare_updates_th(sections)
        if update_errors:
            print("[ERROR] Thai exercise validation failed:")
            for err in update_errors:
                print(f"  - {err}")
            return False

        if not updates:
            print("[WARN] No Thai exercises found; nothing to update.")
            return True

        _update_rows_th(updates, dry_run=dry_run)
        return True

    # English path
    rows, row_errors = _prepare_rows_en(sections)
    if row_errors:
        print("[ERROR] English exercise validation failed:")
        for err in row_errors:
            print(f"  - {err}")
        return False

    if not rows:
        print("[WARN] No exercises found; nothing to import.")
        return True

    _delete_existing(rows, dry_run=dry_run)
    _insert_rows(rows, dry_run=dry_run)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Import exercise bank JSON into Supabase.")
    parser.add_argument("file", help="Path to exercise_bank JSON file.")
    parser.add_argument("--lang", choices=["en", "th"], default="en", help="Language of the payload (default: en)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing data.")
    args = parser.parse_args()

    success = import_exercises_from_file(Path(args.file), lang=args.lang, dry_run=args.dry_run)
    if not success:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

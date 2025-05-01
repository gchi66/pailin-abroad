#!/usr/bin/env python3
"""
Import lessons into Supabase from JSON files.

Usage:
  # Import all JSON files in a folder
  python import_lessons.py path/to/folder

  # Import a single JSON file with multiple lessons (array)
  python import_lessons.py path/to/level3.json

  # Dry run (print payloads without writing)
  python import_lessons.py path/to/folder --dry-run
"""

import os
import glob
import json
import argparse
from app.supabase_client import supabase



# Required top-level keys in each lesson JSON object
REQUIRED_KEYS = {
    "lesson",
    "transcript",
    "comprehension_questions",
    "sections",
    "tags"
}

VALID_EXERCISE_KINDS = {
    'fill_blank',
    'sentence_transform',
    'multiple_choice',
    'open'
}

def upsert_practice_exercises(lesson_id, practice_exercises, dry_run=False):
    """Minimal update to handle practice exercises without changing other logic"""
    for ex in practice_exercises:
        if ex["kind"] not in VALID_EXERCISE_KINDS:
            print(f"[WARNING] Skipping invalid exercise kind: {ex['kind']}")
            continue

        record = {
            "lesson_id": lesson_id,
            "kind": ex["kind"],
            "title": ex.get("title", ""),
            "prompt_md": ex.get("prompt", ""),
            "items": ex.get("items", []),
            # Provide default sort_order (0 if not specified)
            "sort_order": ex.get("sort_order", 0),
            # These can be derived from items in components:
            "options": [],
            "answer_key": {}
}
        if dry_run:
            print(f"[DRY RUN] Would upsert practice exercise: {record}")
            continue

        try:
            supabase.table("practice_exercises") \
                .upsert(record, on_conflict="lesson_id,sort_order") \
                .execute()
        except Exception as e:
            print(f"[ERROR] practice_exercises for lesson {lesson_id}: {e}")

def upsert_lesson(data, dry_run=False):
    lesson = data["lesson"]
    record = {
        "stage": lesson["stage"],
        "level": lesson["level"],
        "lesson_order": lesson["lesson_order"],
        "title": lesson["title"],
        "subtitle": lesson.get("subtitle"),
        "focus": lesson.get("focus"),
        "backstory": lesson.get("backstory"),
    }
    if dry_run:
        print(f"[DRY RUN] Upsert lesson: {record}")
        return None

    res = supabase.table("lessons") \
        .upsert(record, on_conflict="stage,level,lesson_order", returning="representation") \
        .execute()

    return res.data[0]["id"]


def upsert_transcript(lesson_id, transcript, dry_run=False):
    for line in transcript:
        record = {
            "lesson_id": lesson_id,
            "sort_order": line["sort_order"],
            "speaker": line["speaker"],
            "line_text": line["line_text"],
        }
        if dry_run:
            print(f"[DRY RUN] Upsert transcript: {record}")
            continue
        try:
            supabase.table("transcript_lines") \
                .upsert(record, on_conflict="lesson_id,sort_order") \
                .execute()
        except Exception as e:
            print(f"[ERROR] transcript_lines for lesson {lesson_id}, sort {line['sort_order']}: {e}")


def upsert_comprehension(lesson_id, questions, dry_run=False):
    for q in questions:
        record = {
            "lesson_id": lesson_id,
            "sort_order": q["sort_order"],
            "prompt": q["prompt"],
            "options": q.get("options", []),
            "answer_key": q.get("answer_key", []),
        }
        if dry_run:
            print(f"[DRY RUN] Upsert comprehension: {record}")
            continue
        try:
            supabase.table("comprehension_questions") \
                .upsert(record, on_conflict="lesson_id,sort_order") \
                .execute()
        except Exception as e:
            print(f"[ERROR] comprehension_questions for lesson {lesson_id}, sort {q['sort_order']}: {e}")


def upsert_sections(lesson_id, sections, dry_run=False):
    for sec in sections:
        # phrases_verbs handled separately
        if sec["type"] == "phrases_verbs":
            continue
        record = {
            "lesson_id": lesson_id,
            "type": sec["type"],
            "sort_order": sec["sort_order"],
            "content": sec.get("content_md"),
        }
        if dry_run:
            print(f"[DRY RUN] Upsert section: {record}")
            if sec["type"] == "understand":
                print("\n--- Understand Section (raw markdown) ---")
                print(sec.get("content_md"))
                print("--- End Understand Section ---\n")
            continue
        try:
            supabase.table("lesson_sections") \
                .upsert(record, on_conflict="lesson_id,type") \
                .execute()
        except Exception as e:
            print(f"[ERROR] lesson_sections for lesson {lesson_id}, type {sec['type']}: {e}")


def upsert_phrases(lesson_id, sections, dry_run=False):
    for sec in sections:
        if sec["type"] != "phrases_verbs":
            continue

        for idx, item in enumerate(sec.get("items", []), start=1):
            phrase_record = {
                "phrase":       item.get("phrase"),
                "translation":  item.get("translation_th"),
                "notes":        item.get("notes"),
                "phrase_th":    item.get("phrase_th"),
                "notes_th":     item.get("notes_th"),
            }

            if dry_run:
                print("[DRY RUN] Upsert phrase:", phrase_record)
                phrase_id = None
            else:
                res = (
                    supabase.table("phrases")
                    .upsert(
                        phrase_record,
                        on_conflict="phrase",            # unique column
                        returning="representation"       # ask for the row back
                    )
                    .execute()
                )

                # If the row already existed, fetch its id
                if res.data:
                    phrase_id = res.data[0]["id"]
                else:
                    phrase_id = (
                        supabase.table("phrases")
                        .select("id")
                        .eq("phrase", phrase_record["phrase"])
                        .single()
                        .execute()
                        .data["id"]
                    )

            link = {"lesson_id": lesson_id, "phrase_id": phrase_id, "sort_order": idx}

            if dry_run:
                print("[DRY RUN] Upsert lesson_phrases:", link)
            else:
                supabase.table("lesson_phrases") \
                    .upsert(link, on_conflict="lesson_id,phrase_id") \
                    .execute()


def upsert_tags(lesson_id, tags, dry_run=False):
    for tag_name in tags:
        if dry_run:
            print(f"[DRY RUN] Upsert tag record: name={tag_name}")
            tag_id = None
        else:
            tr = supabase.table("tags") \
                .upsert({"name": tag_name}, on_conflict="name", returning="representation") \
                .execute()
            tag_id = tr.data[0]["id"]

        record = {"lesson_id": lesson_id, "tag_id": tag_id}
        if dry_run:
            print(f"[DRY RUN] Upsert lesson_tags: {record}")
            continue
        try:
            supabase.table("lesson_tags") \
                .upsert(record, on_conflict="lesson_id,tag_id") \
                .execute()
        except Exception as e:
            print(f"[ERROR] lesson_tags for lesson {lesson_id}, tag {tag_name}: {e}")


def process_lesson(data, dry_run=False):
    keys = set(data.keys())
    if not REQUIRED_KEYS.issubset(keys):
        print(f"[ERROR] Missing keys: {REQUIRED_KEYS - keys}")
        return

    lesson_id = upsert_lesson(data, dry_run=dry_run)
    upsert_transcript(lesson_id, data.get("transcript", []), dry_run=dry_run)
    upsert_comprehension(lesson_id, data.get("comprehension_questions", []), dry_run=dry_run)
    upsert_sections(lesson_id, data.get("sections", []), dry_run=dry_run)
    upsert_phrases(lesson_id, data.get("sections", []), dry_run=dry_run)
    upsert_practice_exercises(lesson_id, data.get("practice_exercises", []), dry_run=dry_run)
    upsert_tags(lesson_id, data.get("tags", []), dry_run=dry_run)


def import_lessons_from_folder(folder_path, dry_run=False):
    json_files = sorted(glob.glob(os.path.join(folder_path, "*.json")))
    if not json_files:
        print(f"No JSON files found in folder: {folder_path}")
        return

    for path in json_files:
        print(f"Importing file: {path}")
        data = json.load(open(path, "r", encoding="utf-8"))
        if dry_run:
            print("\n--- Full JSON content ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("--- End JSON content ---\n")
        process_lesson(data, dry_run=dry_run)

    print("Folder import complete.")


def import_lessons_from_file(file_path, dry_run=False):
    print(f"Importing lessons array from file: {file_path}")
    lessons = json.load(open(file_path, "r", encoding="utf-8"))
    if not isinstance(lessons, list):
        print("[ERROR] Expected top-level JSON array in file.")
        return

    for data in lessons:
        print(f"Importing lesson: {data['lesson'].get('external_id', '<unknown>')}")
        if dry_run:
            print("\n--- Full JSON content for lesson ---")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("--- End JSON content ---\n")
        process_lesson(data, dry_run=dry_run)

    print("File import complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import lessons JSON into Supabase")
    parser.add_argument("path", help="Path to a JSON file or folder of JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to DB")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        import_lessons_from_folder(args.path, dry_run=args.dry_run)
    elif os.path.isfile(args.path):
        import_lessons_from_file(args.path, dry_run=args.dry_run)
    else:
        print(f"[ERROR] Path not found: {args.path}")

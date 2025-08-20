#!/usr/bin/env python3
"""
Import lessons into Supabase from JSON files.

Usage:
  # Import a level folder containing multiple lesson JSON files
  python -m app.tools.import_lessons data/level_X.json

  # Dry run (print payloads without writing)
  python -m app.tools.import_lessons data/level_X.json --dry-run
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
            "prompt_md": ex.get("prompt") or None,
            "paragraph": ex.get("paragraph") or None,
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
                .upsert(record, on_conflict="lesson_id, kind, sort_order") \
                .execute()
        except Exception as e:
            print(f"[ERROR] practice_exercises for lesson {lesson_id}: {e}")

def upsert_lesson(data, lang="en", dry_run=False):
    lesson = data["lesson"]
    key = {
        "stage": lesson["stage"],
        "level": lesson["level"],
        "lesson_order": lesson["lesson_order"],
    }

    if lang == "en":
        record = {
            **key,
            "title": lesson.get("title"),
            "subtitle": lesson.get("subtitle"),
            "focus": lesson.get("focus"),
            "backstory": lesson.get("backstory"),
        }
        if dry_run:
            print(f"[DRY RUN] Lesson EN UPSERT: {record}")
            return None
        res = (supabase.table("lessons")
               .upsert(record, on_conflict="stage,level,lesson_order", returning="representation")
               .execute())
        return res.data[0]["id"]

    # TH path: update-only, then insert if missing
    th_update = {}
    if lesson.get("title"):     th_update["title_th"]     = lesson["title"]
    if lesson.get("subtitle"):  th_update["subtitle_th"]  = lesson["subtitle"]
    if lesson.get("focus"):     th_update["focus_th"]     = lesson["focus"]
    if lesson.get("backstory"): th_update["backstory_th"] = lesson["backstory"]

    if dry_run:
        print(f"[DRY RUN] Lesson TH UPDATE where {key} set {th_update}")
        print(f"[DRY RUN] (if no row, INSERT { {**key, **th_update} })")
        return None

    # UPDATE
    upd = (supabase.table("lessons")
           .update(th_update)
           .eq("stage", key["stage"])
           .eq("level", key["level"])
           .eq("lesson_order", key["lesson_order"])
           .execute())
    rows = upd.data or []
    if len(rows) == 0:
        # INSERT minimal row with TH
        ins_record = {**key, **th_update}
        res = (supabase.table("lessons")
               .insert(ins_record)
               .execute())
    # fetch id (safe either way)
    sel = (supabase.table("lessons")
           .select("id")
           .eq("stage", key["stage"])
           .eq("level", key["level"])
           .eq("lesson_order", key["lesson_order"])
           .single()
           .execute())
    return sel.data["id"]


def upsert_transcript(lesson_id, transcript, lang="en", dry_run=False):
    for line in transcript:
        key = {"lesson_id": lesson_id, "sort_order": line["sort_order"]}

        if lang == "en":
            record = {**key,
                      "speaker": line.get("speaker", ""),
                      "line_text": line.get("line_text", "")}
            if dry_run:
                print(f"[DRY RUN] Transcript EN UPSERT: {record}")
                continue
            (supabase.table("transcript_lines")
             .upsert(record, on_conflict="lesson_id,sort_order")
             .execute())
            continue

        # TH path: update-only; insert if missing
        th_update = {}
        if "speaker_th" in line:   th_update["speaker_th"]   = line["speaker_th"]
        if "line_text_th" in line: th_update["line_text_th"] = line["line_text_th"]

        if dry_run:
            print(f"[DRY RUN] Transcript TH UPDATE where {key} set {th_update}")
            print(f"[DRY RUN] (if no row, INSERT { {**key, **th_update} })")
            continue

        upd = (supabase.table("transcript_lines")
               .update(th_update)
               .eq("lesson_id", lesson_id)
               .eq("sort_order", line["sort_order"])
               .execute())
        rows = upd.data or []
        if len(rows) == 0:
            # Insert minimal row but supply NOT NULL EN columns with safe placeholders
            ins_record = {
                **key,
                "speaker": line.get("speaker", "") or "",      # satisfy NOT NULL
                "line_text": line.get("line_text", "") or "",  # satisfy NOT NULL
                **th_update,                                   # speaker_th / line_text_th
            }
            (supabase.table("transcript_lines").insert(ins_record).execute())



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


def upsert_sections(lesson_id, sections, lang="en", dry_run=False):
    for sec in sections:
        if sec["type"] == "phrases_verbs":
            continue

        key = {
            "lesson_id": lesson_id,
            "type": sec["type"],
            "sort_order": sec["sort_order"],
        }

        if lang == "en":
            record = {
                **key,
                "content": sec.get("content"),
            }
            if "content_jsonb" in sec and sec["content_jsonb"] is not None:
                record["content_jsonb"] = sec["content_jsonb"]
            if dry_run:
                print(f"[DRY RUN] Section EN UPSERT: {record}")
                continue
            try:
                (supabase.table("lesson_sections")
                    .upsert(record, on_conflict="lesson_id,type,sort_order")
                    .execute())
            except Exception as e:
                print(f"[ERROR] lesson_sections EN upsert {key}: {e}")
            continue

        # --------- TH path: update only TH fields; insert if missing ----------
        th_update = {}
        if "content_jsonb" in sec:
            th_update["content_jsonb_th"] = sec["content_jsonb"]
        if sec.get("render_mode"):
            th_update["render_mode"] = sec["render_mode"]

        if not th_update:
            # nothing to write for TH in this section
            continue

        if dry_run:
            print(f"[DRY RUN] Section TH UPDATE where {key} set {th_update}")
            print(f"[DRY RUN] (if no row, INSERT { {**key, **th_update} })")
            continue

        try:
            # UPDATE first (only TH fields)
            upd = (supabase.table("lesson_sections")
                   .update(th_update)
                   .eq("lesson_id", key["lesson_id"])
                   .eq("type", key["type"])
                   .eq("sort_order", key["sort_order"])
                   .execute())
            rows = upd.data or []
            if len(rows) == 0:
                # INSERT minimal row with TH fields
                ins_record = {**key, **th_update}
                (supabase.table("lesson_sections")
                 .insert(ins_record)
                 .execute())
        except Exception as e:
            print(f"[ERROR] lesson_sections TH update/insert {key}: {e}")


def upsert_phrases(lesson_id, sections, dry_run=False):
    for sec in sections:
        if sec["type"] != "phrases_verbs":
            continue

        for idx, item in enumerate(sec.get("items", []), start=1):
            # If this is a reference, just link to the existing phrase+variant
            if item.get("reference"):
                # Find the phrase by phrase+variant
                res = (
                    supabase.table("phrases")
                    .select("id")
                    .eq("phrase", item["phrase"])
                    .eq("variant", item.get("variant", 1))
                    .execute()
                )
                rows = res.data or []
                if len(rows) == 0:
                    print(f"[ERROR] Reference to missing phrase: {item['phrase']} variant {item.get('variant', 1)}")
                    continue
                elif len(rows) > 1:
                    print(f"[ERROR] Multiple phrases found for: {item['phrase']} variant {item.get('variant', 1)}")
                    continue
                phrase_id = rows[0]["id"]
            else:
                phrase_record = {
                    "phrase":       item.get("phrase"),
                    "variant":      item.get("variant", 1),
                    "translation":  item.get("translation_th") or "",
                    "content_md":   item.get("content_md") or "",
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
                            on_conflict="phrase,variant",  # unique key is phrase+variant
                            returning="representation"
                        )
                        .execute()
                    )

                    if res.data:
                        phrase_id = res.data[0]["id"]
                    else:
                        phrase_id = (
                            supabase.table("phrases")
                            .select("id")
                            .eq("phrase", phrase_record["phrase"])
                            .eq("variant", phrase_record["variant"])
                            .single()
                            .execute()
                            .data["id"]
                        )

            if phrase_id:
                link = {"lesson_id": lesson_id, "phrase_id": phrase_id, "sort_order": idx}
                if dry_run:
                    print("[DRY RUN] Link lesson to phrase:", link)
                else:
                    supabase.table("lesson_phrases").upsert(link, on_conflict="lesson_id,phrase_id").execute()


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


def process_lesson(data, lang="en", dry_run=False):
    keys = set(data.keys())
    if not REQUIRED_KEYS.issubset(keys):
        print(f"[ERROR] Missing keys: {REQUIRED_KEYS - keys}")
        return

    lesson_id = upsert_lesson(data, lang=lang, dry_run=dry_run)
    upsert_transcript(lesson_id, data.get("transcript", []), lang=lang, dry_run=dry_run)
    upsert_comprehension(lesson_id, data.get("comprehension_questions", []), dry_run=dry_run)
    upsert_sections(lesson_id, data.get("sections", []), lang=lang, dry_run=dry_run)
    upsert_phrases(lesson_id, data.get("sections", []), dry_run=dry_run)
    upsert_practice_exercises(lesson_id, data.get("practice_exercises", []), dry_run=dry_run)
    upsert_tags(lesson_id, data.get("tags", []), dry_run=dry_run)


def import_lessons_from_folder(folder_path, lang="en", dry_run=False):
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
        process_lesson(data, lang=lang, dry_run=dry_run)

    print("Folder import complete.")


def import_lessons_from_file(file_path, lang="en", dry_run=False):
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
        process_lesson(data, lang=lang, dry_run=dry_run)

    print("File import complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import lessons JSON into Supabase")
    parser.add_argument("path", help="Path to a JSON file or folder of JSON files")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to DB")
    parser.add_argument("--lang", choices=["en","th"], default="en", help="Language of this JSON")
    args = parser.parse_args()

    if os.path.isdir(args.path):
        import_lessons_from_folder(args.path, lang=args.lang, dry_run=args.dry_run)
    elif os.path.isfile(args.path):
        import_lessons_from_file(args.path, lang=args.lang, dry_run=args.dry_run)
    else:
        print(f"[ERROR] Path not found: {args.path}")

#!/usr/bin/env python3
"""
Import lessons into Supabase from JSON files.

Usage:
  # Import a level folder containing multiple lesson JSON files
  python -m app.tools.import_lessons data/level_X.json

  # Dry run (print payloads without writing)
  python -m app.tools.import_lessons data/level_X.json --dry-run
"""

import re
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

# ______________________ HELPERS
def _normalize_phrase(s: str) -> str:
    """Normalize punctuation/spacing and uppercase for stable matching."""
    if not s:
        return ""
    s = (s.replace("’", "'")
           .replace("‘", "'")
           .replace("“", '"')
           .replace("”", '"')
           .replace("–", "-")
           .replace("—", "-"))
    s = re.sub(r"\s+", " ", s.strip())
    return s.upper()

def _find_phrase_by_norm(variant: int, phrase_raw: str):
    """Fetch by variant, pick the row whose normalized phrase matches."""
    norm = _normalize_phrase(phrase_raw)
    res = supabase.table("phrases").select("id, phrase").eq("variant", variant).execute()
    rows = res.data or []
    for r in rows:
        if _normalize_phrase(r.get("phrase", "")) == norm:
            return r
    return None


#______________________ REGULAR METHODS
def upsert_practice_exercises(lesson_id, practice_exercises, lang=None, dry_run=False):
    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    if lang == "th":
        for ex in (practice_exercises or []):
            kind = ex.get("kind")
            if kind not in VALID_EXERCISE_KINDS:
                print(f"[WARNING] Skipping invalid exercise kind: {kind}")
                continue

            key = {"lesson_id": lesson_id, "kind": kind, "sort_order": ex.get("sort_order", 0)}
            patch = {
                "title_th":     ex.get("title", "") or "",
                "prompt_th":    (ex.get("prompt_md") or ex.get("prompt") or "") or "",
                "paragraph_th": ex.get("paragraph", "") or "",
                "items_th":     ex.get("items", []),
                # if you ever add localized MCQ choices for practice, include options_th here
            }

            if dry_run:
                print(f"[DRY RUN] PRACTICE TH UPDATE where {key} set {patch}")
                continue

            upd = (supabase.table("practice_exercises")
                   .update(patch)
                   .eq("lesson_id", key["lesson_id"])
                   .eq("kind", key["kind"])
                   .eq("sort_order", key["sort_order"])
                   .execute())
            if not (upd.data or []):
                print(f"[WARN] TH skip (no EN row yet) for practice {key}. Run EN import first.")
        return

    # EN (default): keep your existing UPSERT for base columns
    rows = []
    for ex in (practice_exercises or []):
        kind = ex.get("kind")
        if kind not in VALID_EXERCISE_KINDS:
            print(f"[WARNING] Skipping invalid exercise kind: {kind}")
            continue
        rows.append({
            "lesson_id": lesson_id,
            "kind": kind,
            "sort_order": ex.get("sort_order", 0),
            "title":      ex.get("title", "") or "",
            "prompt_md":  (ex.get("prompt_md") or ex.get("prompt")) or None,
            "paragraph":  ex.get("paragraph") or None,
            "items":      ex.get("items", []),
            "options":    ex.get("options", []),    # EN-only, keep NOT NULL
            "answer_key": ex.get("answer_key", {}), # EN-only, keep NOT NULL if you want
        })

    if not rows:
        print(f"[INFO] No practice rows to upsert for lesson {lesson_id} (lang=en). Skipping.")
        return

    (supabase.table("practice_exercises")
        .upsert(rows, on_conflict="lesson_id,kind,sort_order")
        .execute())

def upsert_lesson(data, lang="en", dry_run=False):
    lesson = data["lesson"]

    # --- Normalize keys so EN/TH hit the exact same row ---
    stage = (str(lesson.get("stage", ""))).strip()
    try:
        level = int(lesson.get("level"))
    except Exception:
        raise RuntimeError(f"Invalid level in lesson payload: {lesson.get('level')!r}")
    try:
        lesson_order = int(lesson.get("lesson_order"))
    except Exception:
        raise RuntimeError(f"Invalid lesson_order in lesson payload: {lesson.get('lesson_order')!r}")

    key = {"stage": stage, "level": level, "lesson_order": lesson_order}

    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    if lang == "en":
        # Base-language columns
        record = {
            **key,
            "lesson_external_id": lesson.get("external_id") or None,
            "title":     lesson.get("title") or None,
            "subtitle":  lesson.get("subtitle") or None,
            "focus":     lesson.get("focus") or None,
            "backstory": lesson.get("backstory") or None,
            # add other base fields here if you have them (e.g., conversation_audio_url)
        }

        if dry_run:
            print(f"[DRY RUN] Lesson EN UPSERT:", record)
            # Return a stable fake id so downstream dry-run prints don't crash
            return f"dryrun:{stage}-{level}-{lesson_order}"

        try:
            res = (
                supabase
                .table("lessons")
                .upsert(record, on_conflict="stage,level,lesson_order", returning="representation")
                .execute()
            )
            if res.data and len(res.data) > 0:
                return res.data[0]["id"]
            # Fallback: fetch by key if the client didn't return representation
            sel = (
                supabase.table("lessons")
                .select("id")
                .eq("stage", stage).eq("level", level).eq("lesson_order", lesson_order)
                .single()
                .execute()
            )
            return sel.data["id"]
        except Exception as e:
            # Last-chance fallback: try to read the existing id (in case upsert succeeded but the client errored)
            try:
                sel = (
                    supabase.table("lessons")
                    .select("id")
                    .eq("stage", stage).eq("level", level).eq("lesson_order", lesson_order)
                    .single()
                    .execute()
                )
                return sel.data["id"]
            except Exception:
                raise RuntimeError(f"EN upsert_lesson failed for {key}: {e}")

    # ---------------- TH path: update-only (never insert) ----------------
    th_update = {}
    if lesson.get("title"):     th_update["title_th"]     = lesson["title"]
    if lesson.get("subtitle"):  th_update["subtitle_th"]  = lesson["subtitle"]
    if lesson.get("focus"):     th_update["focus_th"]     = lesson["focus"]
    if lesson.get("backstory"): th_update["backstory_th"] = lesson["backstory"]

    if dry_run:
        print(f"[DRY RUN] Lesson TH UPDATE where {key} set {th_update}")
        return f"dryrun:{stage}-{level}-{lesson_order}"

    try:
        upd = (
            supabase.table("lessons")
            .update(th_update)
            .eq("stage", stage).eq("level", level).eq("lesson_order", lesson_order)
            .execute()
        )
        # Ensure the EN row exists; if not, fail loudly
        if not (upd.data or []):
            raise RuntimeError(
                f"TH update found no EN base row for {key}. Run EN import first (or allow TH to insert)."
            )

        sel = (
            supabase.table("lessons")
            .select("id")
            .eq("stage", stage).eq("level", level).eq("lesson_order", lesson_order)
            .single()
            .execute()
        )
        return sel.data["id"]
    except Exception as e:
        raise RuntimeError(f"TH upsert_lesson failed for {key}: {e}")


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



def upsert_comprehension(lesson_id, questions, lang=None, dry_run=False):
    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    if lang == "en":
        rows = []
        for q in questions:
            key = {"lesson_id": lesson_id, "sort_order": int(q["sort_order"])}
            rows.append({
                **key,
                "prompt": q.get("prompt", "") or "",
                "options": q.get("options", []),
                "answer_key": q.get("answer_key", {}),
            })
        if not rows:
            print(f"[INFO] No comprehension rows (EN) for lesson {lesson_id}. Skipping.")
            return
        supabase.table("comprehension_questions") \
            .upsert(rows, on_conflict="lesson_id,sort_order") \
            .execute()
        return

    # --- TH: update existing row only ---
    for q in questions:
        key = {"lesson_id": lesson_id, "sort_order": int(q["sort_order"])}
        patch = {
            "prompt_th": q.get("prompt", "") or "",
            "options_th": q.get("options", []),   # always set
        }

        if dry_run:
            print(f"[DRY RUN] TH UPDATE where {key} set {patch}")
            continue

        upd = (supabase.table("comprehension_questions")
               .update(patch)
               .eq("lesson_id", key["lesson_id"])
               .eq("sort_order", key["sort_order"])
               .execute())
        if not (upd.data or []):
            print(f"[WARN] TH skip (no EN row yet) for {key}. Run EN import first.")

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
                    .upsert(record, on_conflict="lesson_id,type")
                    .execute())
            except Exception as e:
                print(f"[ERROR] lesson_sections EN upsert {key}: {e}")
            continue

        # --------- TH path: update only TH fields; insert if missing ----------
        th_update = {}

        val = sec.get("content")
        if isinstance(val, str) and val.strip():
            th_update["content_th"] = val.strip()

        cj = sec.get("content_jsonb")
        if cj not in (None, "", "''", '""'):        # guard weird empties
            th_update["content_jsonb_th"] = cj

        # Only set render_mode if provided and non-empty
        rm = sec.get("render_mode")
        if isinstance(rm, str) and rm:
            th_update["render_mode"] = rm

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


def upsert_phrases(lesson_id, sections, lang="en", dry_run=False):
    for sec in sections:
        if sec.get("type") != "phrases_verbs":
            continue

        for idx, item in enumerate(sec.get("items", []), start=1):
            phrase_raw = (item.get("phrase") or "").strip()
            if not phrase_raw:
                continue
            variant = item.get("variant", 1)

            # --- pick the right JSONB payload per language ---
            if lang == "th":
                nodes_payload = item.get("content_jsonb_th")
                text_fallback = (item.get("content") or "").strip()  # optional
            else:  # en
                nodes_payload = item.get("content_jsonb")
                text_fallback = (item.get("content") or "").strip()  # optional

            notes     = item.get("notes")
            phrase_th = item.get("phrase_th")
            notes_th  = item.get("notes_th")

            # reference path
            if item.get("reference"):
                row = _find_phrase_by_norm(variant, phrase_raw)
                if not row:
                    print(f"[ERROR] Reference to missing phrase: {phrase_raw} variant {variant}")
                    continue
                phrase_id = row["id"]
            else:
                row = _find_phrase_by_norm(variant, phrase_raw)

                if row:
                    updates = {}
                    norm_phrase = _normalize_phrase(phrase_raw)
                    if norm_phrase and norm_phrase != row.get("phrase"):
                        updates["phrase"] = norm_phrase

                    if lang == "en":
                        if nodes_payload:
                            updates["content_jsonb"] = nodes_payload
                        if text_fallback:
                            updates["content"] = text_fallback
                        if notes is not None:
                            updates["notes"] = notes
                    else:  # th
                        if nodes_payload:
                            updates["content_jsonb_th"] = nodes_payload
                        if text_fallback:
                            updates["content_th"] = text_fallback
                        if phrase_th is not None:
                            updates["phrase_th"] = phrase_th
                        if notes_th is not None:
                            updates["notes_th"] = notes_th

                    if updates:
                        if dry_run:
                            print("[DRY RUN] Update phrases(id=%s): %r" % (row["id"], updates))
                        else:
                            supabase.table("phrases").update(updates).eq("id", row["id"]).execute()

                    phrase_id = row["id"]

                else:
                    insert_payload = {
                        "phrase":  _normalize_phrase(phrase_raw),
                        "variant": variant,
                    }
                    if lang == "en":
                        if nodes_payload:
                            insert_payload["content_jsonb"] = nodes_payload
                        if text_fallback:
                            insert_payload["content"] = text_fallback
                        if notes is not None:
                            insert_payload["notes"] = notes
                    else:  # th
                        if nodes_payload:
                            insert_payload["content_jsonb_th"] = nodes_payload
                        if text_fallback:
                            insert_payload["content_th"] = text_fallback
                        if phrase_th is not None:
                            insert_payload["phrase_th"] = phrase_th
                        if notes_th is not None:
                            insert_payload["notes_th"] = notes_th

                    if dry_run:
                        print("[DRY RUN] Insert phrases:", insert_payload)
                        phrase_id = None
                    else:
                        ins = supabase.table("phrases").insert(insert_payload).execute()
                        phrase_id = (ins.data or [{}])[0].get("id")
                        if not phrase_id:
                            refetched = _find_phrase_by_norm(variant, phrase_raw)
                            phrase_id = refetched["id"] if refetched else None

            if phrase_id:
                link = {"lesson_id": lesson_id, "phrase_id": phrase_id, "sort_order": idx}
                if dry_run:
                    print("[DRY RUN] Link lesson_phrases upsert:", link)
                else:
                    supabase.table("lesson_phrases").upsert(
                        link, on_conflict="lesson_id,phrase_id"
                    ).execute()


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
    upsert_comprehension(lesson_id, data.get("comprehension_questions", []), lang=lang, dry_run=dry_run)
    upsert_sections(lesson_id, data.get("sections", []), lang=lang, dry_run=dry_run)
    upsert_phrases(lesson_id, data.get("sections", []), lang=lang, dry_run=dry_run)
    upsert_practice_exercises(lesson_id, data.get("practice_exercises", []), lang=lang, dry_run=dry_run)
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

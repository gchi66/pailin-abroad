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
def _get_pailin_abroad_user_id():
    """
    Get the Pailin Abroad admin user ID for pinned comments.
    You can either:
    1. Set an environment variable PAILIN_ABROAD_USER_ID
    2. Query the users table for a known admin email
    3. Use a hardcoded UUID
    """
    # Option 1: Environment variable
    user_id = os.getenv("PAILIN_ABROAD_USER_ID")
    if user_id:
        return user_id

    # Option 2: Query by known admin email (replace with actual admin email)
    try:
        result = supabase.table("users").select("id").eq("email", "pailinabroad@gmail.com").single().execute()
        if result.data:
            return result.data["id"]
    except Exception as e:
        print(f"[WARN] Could not find Pailin Abroad user by email: {e}")

    # Option 3: Fallback to a default UUID (replace with actual UUID if known)
    print("[WARN] Using default user ID for pinned comments. Set PAILIN_ABROAD_USER_ID env var or update the admin email.")
    return "00000000-0000-0000-0000-000000000000"

def _normalize_phrase(s: str) -> str:
    """Normalize punctuation/spacing and uppercase for stable matching."""
    if not s:
        return ""
    s = (s.replace("'", "'")
           .replace("'", "'")
           .replace(""", '"')
           .replace(""", '"')
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
def _extract_th(val):
    """Return only the Thai string from a value that might be:
    - plain string (return stripped)
    - dict like {"en": "..", "th": ".."}
    - any mapping with a 'th' key
    Falls back to first non-empty string value, else empty string.
    """
    if isinstance(val, dict):
        # Preferred Thai keys
        for k in ("th", "TH", "thai", "Thai"):
            v = val.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        # Fallback: first non-empty string in dict
        for v in val.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    if isinstance(val, str):
        return val.strip()
    return ""

def upsert_practice_exercises(lesson_id, practice_exercises, lang=None, dry_run=False):
    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    if lang == "th":
        # Thai path: we ONLY localize textual fields. Image assets (image_key -> image_url resolution)
        # are canonical from the EN ingest. We still keep the Thai items array so that per-item
        # answers or alt text can be associated, but we never attempt to change the base EN
        # image mappings. We optionally warn if Thai JSON's image_key disagrees with EN.
        alt_update_rows = []  # collect (lesson_id,image_key,alt_text_th) upserts
        for ex in (practice_exercises or []):
            kind = ex.get("kind")
            if kind not in VALID_EXERCISE_KINDS:
                print(f"[WARNING] Skipping invalid exercise kind: {kind}")
                continue

            key = {"lesson_id": lesson_id, "kind": kind, "sort_order": ex.get("sort_order", 0)}

            # Fetch existing EN row to validate image_key alignment (best effort; ignore errors)
            en_items = []
            try:
                resp = (supabase.table("practice_exercises")
                        .select("items")
                        .eq("lesson_id", key["lesson_id"])
                        .eq("kind", key["kind"])
                        .eq("sort_order", key["sort_order"])
                        .single()
                        .execute())
                if resp.data and isinstance(resp.data.get("items"), list):
                    en_items = resp.data["items"]
            except Exception as e:
                # Non-fatal: just note inability to validate
                print(f"[INFO] Could not fetch EN practice row for validation ({key}): {e}")

            # Build map of EN items by number for quick comparison
            en_by_number = {str(it.get("number")): it for it in (en_items or []) if it.get("number") is not None}

            th_items_raw = ex.get("items", []) or []
            th_items_validated = []
            for th_item in th_items_raw:
                # Copy as-is (do not mutate original reference)
                item_copy = dict(th_item)
                num = str(item_copy.get("number")) if item_copy.get("number") is not None else None
                if num and "image_key" in item_copy and num in en_by_number:
                    en_image_key = en_by_number[num].get("image_key")
                    th_image_key = item_copy.get("image_key")
                    if en_image_key and th_image_key and en_image_key != th_image_key:
                        print(f"[WARN] TH practice item number {num} image_key '{th_image_key}' != EN '{en_image_key}'. Using EN mapping at runtime.")
                # We intentionally keep the Thai image_key (for diagnostics) but the frontend / resolver
                # should always rely on EN's canonical image_key when rendering.
                # Collect alt text for lesson_images.alt_text_th if present
                if item_copy.get("image_key") and item_copy.get("alt_text"):
                    alt_text_val = item_copy.get("alt_text", "").strip()
                    if alt_text_val:
                        alt_update_rows.append({
                            "lesson_id": lesson_id,
                            "image_key": item_copy["image_key"],
                            "alt_text_th": alt_text_val,
                        })
                th_items_validated.append(item_copy)

            patch = {
                "title_th":     _extract_th(ex.get("title")),
                "prompt_th":    _extract_th(ex.get("prompt_md") or ex.get("prompt")),
                "paragraph_th": _extract_th(ex.get("paragraph")),
                # Store the validated Thai items (with alt text / answers). We do NOT attempt to
                # reconcile or alter image keys here; EN remains source-of-truth.
                "items_th":     th_items_validated,
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
        # Conditional update of Thai alt text (only if existing row & alt_text_th is empty/null)
        if alt_update_rows:
            # Fetch existing image rows with current alt_text_th
            try:
                existing_resp = (supabase.table("lesson_images")
                                 .select("image_key,alt_text_th")
                                 .eq("lesson_id", lesson_id)
                                 .execute())
                existing_map = {rec.get("image_key"): rec for rec in (existing_resp.data or [])}
            except Exception as e:
                print(f"[INFO] Could not fetch existing lesson_images for TH alt text conditional update: {e}")
                existing_map = {}

            # Deduplicate desired updates keeping last
            dedup = {}
            for r in alt_update_rows:
                dedup[r["image_key"]] = r

            for image_key, r in dedup.items():
                existing = existing_map.get(image_key)
                if not existing:
                    # Skip creating new row; image backfill should run first
                    print(f"[WARN] Skip TH alt_text (no lesson_images row yet) image_key={image_key}")
                    continue
                current_val = (existing.get("alt_text_th") or "").strip()
                if current_val:
                    # Already populated; do not overwrite
                    continue
                if dry_run:
                    print(f"[DRY RUN] UPDATE lesson_images set alt_text_th (len={len(r['alt_text_th'])}) where lesson_id={lesson_id} image_key={image_key}")
                else:
                    try:
                        (supabase.table("lesson_images")
                         .update({"alt_text_th": r["alt_text_th"]})
                         .eq("lesson_id", lesson_id)
                         .eq("image_key", image_key)
                         .execute())
                    except Exception as e:
                        print(f"[ERROR] Updating alt_text_th for {image_key}: {e}")
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

    # After EN upsert, gather alt_text for lesson_images.alt_text_en
    alt_rows = []
    for ex in (practice_exercises or []):
        for item in ex.get("items", []) or []:
            if item.get("image_key") and item.get("alt_text"):
                alt_text_val = (item.get("alt_text") or "").strip()
                if alt_text_val:
                    alt_rows.append({
                        "lesson_id": lesson_id,
                        "image_key": item["image_key"],
                        "alt_text_en": alt_text_val,
                    })
    if alt_rows:
        # Fetch existing image rows with current alt_text_en
        try:
            existing_resp = (supabase.table("lesson_images")
                             .select("image_key,alt_text_en")
                             .eq("lesson_id", lesson_id)
                             .execute())
            existing_map = {rec.get("image_key"): rec for rec in (existing_resp.data or [])}
        except Exception as e:
            print(f"[INFO] Could not fetch existing lesson_images for EN alt text conditional update: {e}")
            existing_map = {}

        # Deduplicate desired updates keeping last
        dedup = {}
        for r in alt_rows:
            dedup[r["image_key"]] = r

        for image_key, r in dedup.items():
            existing = existing_map.get(image_key)
            if not existing:
                print(f"[WARN] Skip EN alt_text (no lesson_images row yet) image_key={image_key}")
                continue
            current_val = (existing.get("alt_text_en") or "").strip()
            if current_val:
                # Already set; do not overwrite
                continue
            if dry_run:
                print(f"[DRY RUN] UPDATE lesson_images set alt_text_en (len={len(r['alt_text_en'])}) where lesson_id={lesson_id} image_key={image_key}")
            else:
                try:
                    (supabase.table("lesson_images")
                     .update({"alt_text_en": r["alt_text_en"]})
                     .eq("lesson_id", lesson_id)
                     .eq("image_key", image_key)
                     .execute())
                except Exception as e:
                    print(f"[ERROR] Updating alt_text_en for {image_key}: {e}")

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
    if lesson.get("title"):     th_update["title_th"]     = _extract_th(lesson.get("title"))
    if lesson.get("subtitle"):  th_update["subtitle_th"]  = _extract_th(lesson.get("subtitle"))
    if lesson.get("focus"):     th_update["focus_th"]     = _extract_th(lesson.get("focus"))
    if lesson.get("backstory"): th_update["backstory_th"] = _extract_th(lesson.get("backstory"))

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
    """
    EN path: upsert speaker + line_text.
    TH path: update speaker_th + line_text_th; if no row, insert with EN placeholders.
    """
    for line in transcript:
        key = {"lesson_id": lesson_id, "sort_order": line["sort_order"]}

        if lang == "en":
            record = {
                **key,
                # ensure NOT NULL columns are always present
                "speaker": (line.get("speaker") or "").strip(),
                "line_text": (line.get("line_text") or "").strip(),
            }
            if dry_run:
                print(f"[DRY RUN] Transcript EN UPSERT: {record}")
                continue

            (supabase.table("transcript_lines")
             .upsert(record, on_conflict="lesson_id,sort_order")
             .execute())
            continue

        # ---------- TH path ----------
        # Only include TH fields actually provided (avoid overwriting with None)
        th_update = {}
        if "speaker_th" in line:
            th_update["speaker_th"] = (line["speaker_th"] or "").strip()
        if "line_text_th" in line:
            th_update["line_text_th"] = (line["line_text_th"] or "").strip()

        if not th_update:
            if dry_run:
                print(f"[DRY RUN] Transcript TH SKIP (no TH fields) for {key}")
            continue

        if dry_run:
            print(f"[DRY RUN] Transcript TH UPDATE where {key} set {th_update}")
            print(f"[DRY RUN] (if no row, INSERT { {**key, 'speaker': '', 'line_text': '', **th_update} })")
            continue

        # Try to UPDATE existing row and ask PostgREST to return matched rows.
        upd = (supabase.table("transcript_lines")
               .update(th_update, returning="representation")  # ensures .data contains updated rows
               .eq("lesson_id", lesson_id)
               .eq("sort_order", line["sort_order"])
               .execute())

        rows = upd.data or []

        if len(rows) == 0:
            # No existing row: INSERT with safe placeholders for NOT NULL EN columns.
            ins_record = {
                **key,
                "speaker": (line.get("speaker") or "").strip(),     # placeholders OK
                "line_text": (line.get("line_text") or "").strip(), # placeholders OK
                **th_update,
            }
            (supabase.table("transcript_lines")
             .insert(ins_record)
             .execute())


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
                        if phrase_th is not None and phrase_th.strip():
                            updates["phrase_th"] = phrase_th

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

                    else:  # th
                        if nodes_payload:
                            insert_payload["content_jsonb_th"] = nodes_payload
                        if text_fallback:
                            insert_payload["content_th"] = text_fallback
                        if phrase_th is not None and phrase_th.strip():
                            insert_payload["phrase_th"] = phrase_th

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


def upsert_pinned_comment(lesson_id, pinned_comment, lang="en", dry_run=False):
    """
    Upsert pinned comment for a lesson into the same row.
    - If lang="en": update 'body' column
    - If lang="th": update 'body_th' column
    Uses upsert to ensure we update the same comment row for both languages.
    """
    if not pinned_comment or not pinned_comment.strip():
        return  # No pinned comment to insert

    PAILIN_ABROAD_USER_ID = _get_pailin_abroad_user_id()

    lang = (lang or "en").lower()
    if lang not in ("en", "th"):
        raise ValueError("lang must be 'en' or 'th'")

    # Build the comment data - we always include both columns
    comment_data = {
        "lesson_id": lesson_id,
        "user_id": PAILIN_ABROAD_USER_ID,
        "pinned": True
    }

    # Set the appropriate language column
    if lang == "en":
        comment_data["body"] = pinned_comment.strip()
        comment_data["body_th"] = ""  # Initialize empty if not set
    else:  # th
        comment_data["body"] = ""  # Initialize empty if not set
        comment_data["body_th"] = pinned_comment.strip()

    if dry_run:
        print(f"[DRY RUN] Upsert pinned comment ({lang}): {comment_data}")
        return

    try:
        # Check if a pinned comment already exists for this lesson and user
        existing_result = supabase.table("comments").select("id,body,body_th").eq("lesson_id", lesson_id).eq("user_id", PAILIN_ABROAD_USER_ID).eq("pinned", True).execute()

        if existing_result.data:
            # Update existing comment - preserve the other language column
            existing_comment = existing_result.data[0]
            comment_id = existing_comment["id"]

            # Build update data preserving existing content
            update_data = {}
            if lang == "en":
                update_data["body"] = pinned_comment.strip()
                # Preserve existing Thai content if any
                if existing_comment.get("body_th"):
                    update_data["body_th"] = existing_comment["body_th"]
            else:  # th
                update_data["body_th"] = pinned_comment.strip()
                # Preserve existing English content if any
                if existing_comment.get("body"):
                    update_data["body"] = existing_comment["body"]

            supabase.table("comments").update(update_data).eq("id", comment_id).execute()
            print(f"[INFO] Updated existing pinned comment for lesson {lesson_id} (lang={lang})")
        else:
            # Insert new comment
            supabase.table("comments").insert(comment_data).execute()
            print(f"[INFO] Inserted new pinned comment for lesson {lesson_id} (lang={lang})")

    except Exception as e:
        print(f"[ERROR] Failed to upsert pinned comment for lesson {lesson_id}: {e}")


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

    # Handle pinned comment if present
    pinned_comment = data.get("pinned_comment")
    if pinned_comment:
        upsert_pinned_comment(lesson_id, pinned_comment, lang=lang, dry_run=dry_run)


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

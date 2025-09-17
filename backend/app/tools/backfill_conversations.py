# RCLONE USAGE -
# rclone copy \
#   pailin_audio:"Final/L1/Conversations" \
#   supabase:"lesson-audio/Beginner/L1/Conversations" \
#   --include "*_conversation*.mp3" -P
#
# Run:
#    python -m app.tools.backfill_conversations

import os, re
from pathlib import PurePosixPath
from app.config import Config
from supabase import create_client

# ── 1.  CONNECT ────────────────────────────────────────────────────────────
SUPABASE_URL  = os.environ["SUPABASE_URL"]
SERVICE_ROLE  = os.environ["SUPABASE_KEY"]
BUCKET        = "lesson-audio"

supabase = create_client(SUPABASE_URL, SERVICE_ROLE)

# ── 2.  CONSTANTS ──────────────────────────────────────────────────────────
STAGES = {"Beginner", "Intermediate", "Advanced", "Expert"}

FILE_RE = re.compile(
    r"(?P<level>\d+)\.(?P<order>\d+|checkpoint|chp)_conversation(?P<suffix>_no_bg|_bg)?\.mp3$",
    re.I,
)

# ── 3.  HELPERS ────────────────────────────────────────────────────────────
def list_all(bucket: str, path: str = ""):
    """Yield every file in the given bucket path (recursively)."""
    try:
        items = supabase.storage.from_(bucket).list(path=path)
        for item in items:
            item_name = item["name"]
            item_path = f"{path}/{item_name}" if path else item_name
            if "." not in item_name:
                # recurse into folders
                yield from list_all(bucket, item_path)
            else:
                file_obj = item.copy()
                file_obj["name"] = item_path
                yield file_obj
    except Exception as e:
        print(f"Error listing path '{path}': {e}")

# ── 4.  MAIN ───────────────────────────────────────────────────────────────
def main():
    print(f"Checking bucket: {BUCKET}")

    # Restrict scan to Conversations folder
    scan_path = "Beginner/L1/Conversations"

    try:
        test_list = supabase.storage.from_(BUCKET).list(path=scan_path, options={"limit": 1})
        print(f"Bucket access test successful: found {len(test_list)} objects in {scan_path}")
    except Exception as e:
        print(f"Bucket access failed: {e}")
        return

    all_objects = list(list_all(BUCKET, scan_path))
    print(f"Total objects found in {scan_path}: {len(all_objects)}")
    if not all_objects:
        return

    updated = skipped = missing = 0

    for obj in list_all(BUCKET, scan_path):
        key  = obj["name"]                        # full bucket path
        name = PurePosixPath(key).name
        print(f"Processing: {key}")

        # Skip folders
        if not name or "." not in name:
            skipped += 1
            continue

        # Match file pattern
        m = FILE_RE.match(name)
        if not m:
            print(f"SKIP  filename doesn't match pattern '{FILE_RE.pattern}': {name}")
            skipped += 1
            continue

        parts = key.split("/")
        if len(parts) < 4:
            print(f"SKIP  bad path (need 4+ parts): {key}")
            skipped += 1
            continue

        stage_folder, level_folder = parts[0], parts[1]
        stage = stage_folder.replace("_", " ")

        if stage not in STAGES:
            print(f"SKIP  unknown stage '{stage}': {key}")
            skipped += 1
            continue

        try:
            level = int(level_folder.lstrip("L"))
        except ValueError:
            print(f"SKIP  bad level folder '{level_folder}': {key}")
            skipped += 1
            continue

        lesson_order_raw = m["order"].lower()

        # ── find matching lesson row ──────────────────────────────────────────
        try:
            query = supabase.table("lessons").select("id")
            query = query.eq("stage", stage).eq("level", level)

            if lesson_order_raw in {"checkpoint", "chp"}:
                # Use lesson_external_id instead of lesson_order
                external_id = f"{level}.{lesson_order_raw}"
                print(f"  Checkpoint conversation detected, looking up lesson_external_id='{external_id}'")
                query = query.eq("lesson_external_id", external_id)
            else:
                lesson_order = int(lesson_order_raw)
                print(f"  Regular lesson order: {lesson_order}")
                query = query.eq("lesson_order", lesson_order)

            res = query.maybe_single().execute()

            if res is None or not res.data:
                print(f"MISS  no lesson row found: {key}")
                missing += 1
                continue

            lesson_data = res.data
        except Exception as e:
            print(f"ERROR  database query failed: {e}")
            missing += 1
            continue

        print(f"  Found lesson ID: {lesson_data['id']}")

        # ── update correct audio_url column ──────────────────────────────────
        suffix = m["suffix"] or ""
        if suffix.lower() == "_no_bg":
            col = "conversation_audio_url_no_bg"
        elif suffix.lower() == "_bg":
            col = "conversation_audio_url_bg"
        else:
            col = "conversation_audio_url"

        try:
            supabase.table("lessons").update({col: key}).eq("id", lesson_data["id"]).execute()
            print(f"OK    Updated lesson {lesson_data['id']} [{col}]: {key}")
            updated += 1
        except Exception as e:
            print(f"ERROR  failed to update lesson: {e}")
            missing += 1
            continue

    print(f"\nDONE  updated={updated}  skipped={skipped}  missing={missing}")


if __name__ == "__main__":
    main()

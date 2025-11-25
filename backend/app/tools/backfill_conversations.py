# RCLONE USAGE -
# rclone copy \
#   pailin_audio:"Final/LX/Conversations" \
#   supabase:"lesson-audio/Stage/LX/Conversations" \
#   --include "*_conversation*.mp3" -P
#
# Run:
#    python -m app.tools.backfill_conversations --stage "STAGE" --level X

import os
import re
import argparse
from pathlib import PurePosixPath
from app.config import Config
from supabase import create_client

# ── 1.  CONNECT ────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SERVICE_ROLE = os.environ["SUPABASE_KEY"]
BUCKET = "lesson-audio"

supabase = create_client(SUPABASE_URL, SERVICE_ROLE)

# ── 2.  CONSTANTS ──────────────────────────────────────────────────────────
# Support both your older and newer stage labels
VALID_STAGES = {
    "Beginner",
    "Intermediate",
    "Advanced",
    "Expert",
}

# Accept common folder forms (e.g., "Lower_Intermediate")
def normalize_stage_label(s: str) -> str:
    return s.replace("_", " ").strip()

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

def find_and_update_for_scan_path(scan_path: str, dry_run: bool = False):
    print(f"\nScanning: {scan_path}")
    try:
        test_list = supabase.storage.from_(BUCKET).list(path=scan_path, options={"limit": 1})
        print(f"Bucket access OK: found {len(test_list)} objects in {scan_path}")
    except Exception as e:
        print(f"Bucket access failed: {e}")
        return

    all_objects = list(list_all(BUCKET, scan_path))
    print(f"Total objects found in {scan_path}: {len(all_objects)}")
    if not all_objects:
        return

    updated = skipped = missing = 0

    for obj in all_objects:
        key = obj["name"]  # full bucket path like: Beginner/L2/Conversations/2.3_conversation.mp3
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
        stage = normalize_stage_label(stage_folder)

        if stage not in VALID_STAGES:
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
        suffix = (m["suffix"] or "").lower()
        if suffix == "_no_bg":
            col = "conversation_audio_url_no_bg"
        elif suffix == "_bg":
            col = "conversation_audio_url_bg"
        else:
            col = "conversation_audio_url"

        if dry_run:
            print(f"DRY   Would update {col} to '{key}' for lesson {lesson_data['id']}")
            updated += 1
            continue

        try:
            supabase.table("lessons").update({col: key}).eq("id", lesson_data["id"]).execute()
            print(f"OK    Updated lesson {lesson_data['id']} [{col}]: {key}")
            updated += 1
        except Exception as e:
            print(f"ERROR  failed to update lesson: {e}")
            missing += 1
            continue

    print(f"\nDONE  updated={updated}  skipped={skipped}  missing={missing}")

# ── 4.  MAIN ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Backfill conversation audio URLs for a given stage and level."
    )
    parser.add_argument("--stage", type=str, default="Beginner",
                        help='Stage folder (e.g., "Beginner", "Intermediate", "Advanced", "Expert")')
    parser.add_argument("--level", type=int, default=1,
                        help="Numeric level, e.g. 1, 2, 7")
    parser.add_argument("--dry-run", action="store_true",
                        help="List matches and target columns without updating the database")
    args = parser.parse_args()

    stage_label = normalize_stage_label(args.stage)
    if stage_label not in VALID_STAGES:
        raise SystemExit(f"Invalid --stage '{args.stage}'. Valid: {sorted(VALID_STAGES)}")

    if args.level < 1:
        raise SystemExit("--level must be a positive integer")

    # Conversations subfolder for the single requested level
    scan_path = f"{stage_label.replace(' ', '_')}/L{args.level}/Conversations"
    print(f"Checking bucket: {BUCKET}")
    print(f"Stage: {stage_label}  Level: {args.level}  (path: {scan_path})")
    find_and_update_for_scan_path(scan_path, dry_run=args.dry_run)

if __name__ == "__main__":
    main()

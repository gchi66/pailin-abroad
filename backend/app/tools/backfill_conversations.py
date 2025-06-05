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
STAGES = {
    "Beginner",
    "Lower Intermediate",
    "Upper Intermediate",
    "Advanced",
}

FILE_RE = re.compile(r"(?P<level>\d+)\.(?P<order>\d+|checkpoint)_conversation\.mp3$", re.I)

# ── 3.  HELPERS ────────────────────────────────────────────────────────────
def list_all(bucket: str, path: str = ""):
    """Recursively yield every file in the bucket by traversing folders manually."""
    print(f"Exploring path: '{path}'")

    try:
        items = supabase.storage.from_(bucket).list(path=path)
        print(f"  Found {len(items)} items in '{path}'")

        for item in items:
            item_name = item['name']
            item_path = f"{path}/{item_name}" if path else item_name

            print(f"    Item: {item_name} -> Full path: {item_path}")

            # If it's a folder (no file extension), recurse into it
            if '.' not in item_name:
                print(f"    -> Folder detected, recursing...")
                yield from list_all(bucket, item_path)
            else:
                # It's a file, yield it with full path
                print(f"    -> File detected")
                file_obj = item.copy()
                file_obj['name'] = item_path  # Update name to include full path
                yield file_obj

    except Exception as e:
        print(f"Error listing path '{path}': {e}")

# ── 4.  MAIN ───────────────────────────────────────────────────────────────
def main():
    print(f"Checking bucket: {BUCKET}")

    # Test bucket access
    try:
        test_list = supabase.storage.from_(BUCKET).list(path="", options={"limit": 1})
        print(f"Bucket access test successful: found {len(test_list)} objects in root")
    except Exception as e:
        print(f"Bucket access failed: {e}")
        return

    # Get all objects and show summary
    all_objects = list(list_all(BUCKET))
    print(f"Total objects found: {len(all_objects)}")

    if len(all_objects) == 0:
        print("No objects found in bucket!")
        return
    else:
        print("First few objects:")
        for obj in all_objects[:5]:
            print(f"  {obj}")
        print()

    # Process files
    updated = skipped = missing = 0

    for obj in list_all(BUCKET):
        key  = obj["name"]                        # full bucket path
        name = PurePosixPath(key).name

        print(f"Processing: {key}")

        # Skip folders (they don't have file extensions)
        if not name or '.' not in name:
            print(f"SKIP  folder: {key}")
            skipped += 1
            continue

        if not name.endswith("_conversation.mp3"):
            print(f"SKIP  not conversation file: {key}")
            skipped += 1
            continue

        # Expected path: <Stage>/L<level>/Conversations/<file>
        parts = key.split("/")
        if len(parts) < 4:
            print(f"SKIP  bad path (need 4+ parts, got {len(parts)}): {key}")
            skipped += 1
            continue

        stage_folder, level_folder = parts[0], parts[1]
        stage = stage_folder.replace("_", " ")

        print(f"  Stage folder: '{stage_folder}' -> Stage: '{stage}'")

        if stage not in STAGES:
            print(f"SKIP  unknown stage '{stage}' (valid: {STAGES}): {key}")
            skipped += 1
            continue

        try:
            level = int(level_folder.lstrip("L"))
            print(f"  Level folder: '{level_folder}' -> Level: {level}")
        except ValueError:
            print(f"SKIP  bad level folder '{level_folder}': {key}")
            skipped += 1
            continue

        m = FILE_RE.match(name)
        if not m:
            print(f"SKIP  filename doesn't match pattern '{FILE_RE.pattern}': {name}")
            skipped += 1
            continue

        lesson_order_raw = m["order"]

        if lesson_order_raw == "checkpoint":
            # Checkpoint conversations have lesson_order = 0 in the database
            lesson_order = 0
            print(f"  Checkpoint conversation detected, using order: {lesson_order}")
        else:
            lesson_order = int(lesson_order_raw)
            print(f"  Regular lesson order: {lesson_order}")

        # ── find matching lesson row ──────────────────────────────────────────
        print(f"  Looking for lesson: stage='{stage}', level={level}, order={lesson_order}")

        try:
            res = (
                supabase.table("lessons")
                .select("id")
                .eq("stage", stage)
                .eq("level", level)
                .eq("lesson_order", lesson_order)
                .maybe_single()
                .execute()
            )

            if res is None:
                print(f"MISS  query returned None: {key}")
                missing += 1
                continue

            lesson_data = res.data

            if not lesson_data:
                print(f"MISS  no lesson row found: {key}")
                missing += 1
                continue

        except Exception as e:
            print(f"ERROR  database query failed: {e}")
            missing += 1
            continue

        print(f"  Found lesson ID: {lesson_data['id']}")

        # ── update conversation_audio_url ─────────────────────────────────────
        try:
            supabase.table("lessons").update(
                {"conversation_audio_url": key}
            ).eq("id", lesson_data["id"]).execute()

            print(f"OK    Updated lesson {lesson_data['id']}: {key}")
            updated += 1
            print()

        except Exception as e:
            print(f"ERROR  failed to update lesson: {e}")
            missing += 1
            continue

    print(f"\nDONE  updated={updated}  skipped={skipped}  missing={missing}")


if __name__ == "__main__":
    main()

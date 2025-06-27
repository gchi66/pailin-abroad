"""
Populate the audio_snippets table from objects already
uploaded to the lesson-audio bucket.

Usage
-----
python -m app.tools.backfill_audio_snippets

RCLONE USAGE -
for section in Understand Extra_Tips Practice Common_Mistakes; do
  lc=$(echo "$section" | tr '[:upper:]' '[:lower:]')
  echo "→ $section"
  rclone copy -P -vv --stats 5s --s3-no-head \
    pailin_audio_sa:"Final/LX/${section}" \
    supabase:"lesson-audio/STAGE/LX/${section}" \
    --include "*_${lc}_*.mp3"
done
"""

from __future__ import annotations
import os, re, sys, itertools
from supabase import create_client, Client

# ─── 1. Config ─────────────────────────────────────────────────────────────
STAGES = {
    "Beginner",
    "Lower Intermediate",
    "Upper Intermediate",
    "Advanced",
}

SUPABASE_URL   = os.getenv("SUPABASE_URL")
SERVICE_ROLE   = os.getenv("SUPABASE_KEY")
BUCKET         = "lesson-audio"

if not (SUPABASE_URL and SERVICE_ROLE):
    sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in your env")

sb: Client = create_client(SUPABASE_URL, SERVICE_ROLE)

# ─── 2. Filename pattern ───────────────────────────────────────────────────
# Updated to match your actual folder structure and naming
FILE_RE = re.compile(
    r"""
    (?P<lesson>\d+\.\d+)                 # 1.10
    _(?P<section>understand|practice|extra_tips|
               common_mistakes)
    _(?P<seq>\d{2})                      # 01, 02, …
    _(?P<character>[A-Za-z]+)
    \.mp3$
    """,
    re.X | re.I,
)

# Map the filename sections to database sections
SECTION_MAPPING = {
    "understand": "understand",
    "extra_tips": "extra_tip",
    "common_mistakes": "common_mistake",
    "practice": "practice",
}

# ─── 3. Recursively list all objects in the bucket ─────────────────────────
def list_objects_recursive(prefix: str = "") -> list[str]:
    """Recursively list all object paths in the bucket"""
    all_objects = []

    def _list_folder(folder_prefix: str):
        try:
            resp = sb.storage.from_(BUCKET).list(path=folder_prefix)
            for obj in resp:
                if obj.get("name"):
                    full_path = f"{folder_prefix}/{obj['name']}" if folder_prefix else obj["name"]

                    # If it's a folder (ends with / or has no extension), recurse
                    if obj["name"].endswith("/") or "." not in obj["name"]:
                        _list_folder(full_path.rstrip("/"))
                    else:
                        all_objects.append(full_path)
        except Exception as e:
            print(f"Error listing objects for prefix '{folder_prefix}': {e}")

    _list_folder(prefix)
    return all_objects

# ─── 4. Main ───────────────────────────────────────────────────────────────
def main():
    rows = []

    print("Gathering objects recursively...")

    # Get all objects in the bucket
    all_objects = list_objects_recursive()

    for obj_path in all_objects:
        print(f"Processing: {obj_path}")

        # Skip Conversations folder
        if "/Conversations/" in obj_path:
            print(f"SKIP (Conversations): {obj_path}")
            continue

        # Skip if not an mp3 file
        if not obj_path.endswith(".mp3"):
            print(f"SKIP (not mp3): {obj_path}")
            continue

        # Extract filename from path
        filename = obj_path.split("/")[-1]

        # Try to match the filename pattern
        m = FILE_RE.search(filename)
        if not m:
            print(f"SKIP (no match): {obj_path}")
            continue

        # Extract stage from path (first component)
        path_parts = obj_path.split("/")
        if len(path_parts) < 4:  # Need at least Stage/LX/Section/file.mp3
            print(f"SKIP (invalid path structure): {obj_path}")
            continue

        stage = path_parts[0]
        if stage not in STAGES:
            print(f"SKIP (unknown stage '{stage}'): {obj_path}")
            continue

        # Map the filename section to database section
        section_from_filename = m["section"].lower()
        db_section = SECTION_MAPPING.get(section_from_filename, section_from_filename)

        rows.append({
            "lesson_external_id": m["lesson"],
            "section": db_section,
            "seq": int(m["seq"]),
            "character": m["character"],
            "storage_path": obj_path,
        })
        print(f"ADDED: {obj_path}")

    print(f"\nFound {len(rows)} matching audio files")

    if len(rows) == 0:
        print("No rows to upsert. Exiting.")
        return

    print(f"Upserting {len(rows)} rows...")
    try:
        result = sb.table("audio_snippets").upsert(rows).execute()
        print("✅ Done – audio_snippets table is up to date.")
        print(f"Upserted {len(result.data)} rows")
    except Exception as e:
        print(f"Error upserting: {e}")
        print("Sample row data:")
        if rows:
            print(rows[0])

if __name__ == "__main__":
    main()

"""
Populate the audio_snippets table from objects already uploaded to the
lesson-audio bucket.

rclone:
➜  pailin-abroad git:(master) ✗ rclone copy \
  "pailin_audio:Final/Phrases_Verbs" \
  "supabase:lesson-audio/Phrases_Verbs" \
  --include "phrases_verbs_*.mp3" \
  -P
  or some shit like that


Run:
    python -m app.tools.backfill_audio_snippets
"""

from __future__ import annotations
import os, re, sys
from collections import defaultdict
from supabase import create_client, Client

# ─── 1. Config ─────────────────────────────────────────────────────────────
STAGES = {
    "Beginner",
    "Lower Intermediate",
    "Upper Intermediate",
    "Advanced",
}

SUPABASE_URL = os.getenv("SUPABASE_URL")
SERVICE_ROLE = os.getenv("SUPABASE_KEY")
BUCKET       = "lesson-audio"

if not (SUPABASE_URL and SERVICE_ROLE):
    sys.exit("Set SUPABASE_URL and SUPABASE_KEY in your environment")

sb: Client = create_client(SUPABASE_URL, SERVICE_ROLE)

# ─── 2. Filename patterns ──────────────────────────────────────────────────
# Standard sections (no variant)
STANDARD_FILE_RE = re.compile(
    r"""
    (?P<lesson>\d+\.\d+)
    _
    (?P<section>understand|practice|extra_tips|common_mistakes)
    _
    (?P<seq>\d{1,3})
    (?:_(?P<character>[A-Za-z]+))?
    \.mp3(?:\.mp3)?$
    """,
    re.X | re.I,
)

# Phrases & verbs with variant
PHRASES_FILE_RE = re.compile(
    r"""
    (?P<lesson>\d+\.\d+)
    _
    phrases_verbs
    (?P<variant>\d+)?   # Optional variant number
    _
    (?P<seq>\d{1,3})
    (?:_(?P<character>[A-Za-z]+))?
    \.mp3(?:\.mp3)?$
    """,
    re.X | re.I,
)

SECTION_MAPPING = {
    "understand":      "understand",
    "extra_tips":      "extra_tip",
    "common_mistakes": "common_mistake",
    "practice":        "practice",
}

# ─── 3. Helper function to check if phrases exist ─────────────────────────
def phrase_exists_in_db(lesson_external_id: str, variant: int) -> bool:
    """Check if a phrase with the given lesson and variant exists in the DB"""
    try:
        # First get the lesson_id from lesson_external_id
        lesson_query = sb.table("lessons").select("id").eq("lesson_external_id", lesson_external_id).execute()
        if not lesson_query.data:
            return False

        lesson_id = lesson_query.data[0]["id"]

        # Then check if phrase exists with this lesson_id and variant
        phrase_query = sb.table("phrases").select("id").eq("lesson_id", lesson_id).eq("variant", variant).execute()
        return bool(phrase_query.data)
    except Exception as e:
        print(f"Warning: Could not check phrase existence for {lesson_external_id} variant {variant}: {e}")
        return False

# ─── 4. List objects with pagination (options-dict style) ──────────────────
def list_objects_recursive(prefix: str = "") -> list[str]:
    objects: list[str] = []

    def _walk(p: str):
        page = 0
        while True:
            resp = sb.storage.from_(BUCKET).list(
                p,
                {
                    "limit": 100,
                    "offset": page * 100,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            if not resp:
                break

            for obj in resp:
                name = obj["name"]
                full = f"{p}/{name}" if p else name
                if name.endswith("/") or "." not in name:
                    _walk(full.rstrip("/"))
                else:
                    objects.append(full)

            if len(resp) < 100:
                break
            page += 1

    _walk(prefix)
    return objects

# ─── 5. Main ───────────────────────────────────────────────────────────────
def main() -> None:
    print("Gathering objects …")
    all_objects = list_objects_recursive()
    print(f"Found {len(all_objects)} objects in bucket")

    rows, seen, dupes = [], set(), defaultdict(list)

    for path in all_objects:
        if "/Conversations/" in path or not path.lower().endswith(".mp3"):
            continue

        filename = path.split("/")[-1]
        stage = path.split("/")[0]
        if stage not in STAGES:
            continue

        # Try phrases_verbs pattern first
        phrases_match = PHRASES_FILE_RE.fullmatch(filename)
        if phrases_match:
            lesson = phrases_match["lesson"]
            variant = int(phrases_match["variant"]) if phrases_match["variant"] else 0  # Default to 0
            seq = int(phrases_match["seq"])
            character = phrases_match["character"]

            # Check if this phrase variant exists in DB
            if not phrase_exists_in_db(lesson, variant):
                print(f"Skipping {filename}: phrase variant {variant} not found in DB for lesson {lesson}")
                continue

            key = (lesson, "phrases_verbs", variant, seq)

            if key in seen:
                dupes[key].append(path)
                continue
            seen.add(key)

            rows.append(
                {
                    "lesson_external_id": lesson,
                    "section": "phrases_verbs",
                    "seq": seq,
                    "variant": variant,
                    "character": character or None,
                    "storage_path": path,
                }
            )
            continue

        # Try standard pattern
        standard_match = STANDARD_FILE_RE.fullmatch(filename)
        if standard_match:
            lesson = standard_match["lesson"]
            section = SECTION_MAPPING[standard_match["section"].lower()]
            seq = int(standard_match["seq"])
            character = standard_match["character"]

            key = (lesson, section, seq)

            if key in seen:
                dupes[key].append(path)
                continue
            seen.add(key)

            rows.append(
                {
                    "lesson_external_id": lesson,
                    "section": section,
                    "seq": seq,
                    "variant": None,  # Standard sections don't use variant
                    "character": character or None,
                    "storage_path": path,
                }
            )

    if dupes:
        print("\nSkipped duplicates:")
        for k, ps in dupes.items():
            print(" ", k, "→", ps)

    print(f"\nUpserting {len(rows)} rows …")
    if not rows:
        print("Nothing to do.")
        return

    res = (
        sb.table("audio_snippets")
          .upsert(rows, on_conflict="lesson_external_id,section,seq,variant")
          .execute()
    )
    print(f"✅ Success – {len(res.data)} rows upserted/updated.")

if __name__ == "__main__":
    main()

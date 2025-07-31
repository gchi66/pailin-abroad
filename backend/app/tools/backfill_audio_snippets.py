"""
Populate the audio_snippets table from objects already uploaded to the
lesson-audio bucket.

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

# ─── 2. Filename pattern ───────────────────────────────────────────────────
FILE_RE = re.compile(
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

SECTION_MAPPING = {
    "understand":      "understand",
    "extra_tips":      "extra_tip",
    "common_mistakes": "common_mistake",
    "practice":        "practice",
}

# ─── 3. List objects with pagination (options-dict style) ──────────────────
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

# ─── 4. Main ───────────────────────────────────────────────────────────────
def main() -> None:
    print("Gathering objects …")
    all_objects = list_objects_recursive()
    print(f"Found {len(all_objects)} objects in bucket")

    rows, seen, dupes = [], set(), defaultdict(list)

    for path in all_objects:
        if "/Conversations/" in path or not path.lower().endswith(".mp3"):
            continue

        m = FILE_RE.fullmatch(path.split("/")[-1])
        if not m:
            continue

        stage = path.split("/")[0]
        if stage not in STAGES:
            continue

        section = SECTION_MAPPING[m["section"].lower()]
        key = (m["lesson"], section, int(m["seq"]))

        if key in seen:
            dupes[key].append(path)
            continue
        seen.add(key)

        rows.append(
            {
                "lesson_external_id": m["lesson"],
                "section": section,
                "seq": int(m["seq"]),
                "character": m["character"] or None,
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
          .upsert(rows, on_conflict="lesson_external_id,section,seq")
          .execute()
    )
    print(f"✅ Success – {len(res.data)} rows upserted/updated.")

if __name__ == "__main__":
    main()

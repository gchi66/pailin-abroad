"""
Populate the audio_snippets and phrases_audio_snippets tables from objects
already uploaded to the lesson-audio bucket.

Standard sections (understand, practice, etc.) go to audio_snippets table.
Phrases & verbs audio files go to phrases_audio_snippets table.

File patterns:
- Standard: {lesson}_{section}_{seq}_{character}.mp3
- Phrases: phrases_verbs_{phrase_key}[{variant}]_{seq}.mp3

rclone:
➜  pailin-abroad git:(master) ✗ rclone copy \
  "pailin_audio:Final/Phrases_Verbs" \
  "supabase:lesson-audio/Phrases_Verbs" \
  --include "phrases_verbs_*.mp3" \
  -P

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

# Phrases & verbs with variant - new pattern: phrases_verbs_phrase_key[variant]_seq.mp3
PHRASES_FILE_RE = re.compile(
    r"""
    phrases_verbs
    _
    (?P<phrase_key>[a-z_]+?)     # "a_catch", "cool", etc. (non-greedy)
    (?P<variant>\d+)?            # Optional variant number after phrase_key
    _
    (?P<seq>\d+)
    \.mp3$
    """,
    re.X | re.I,
)

SECTION_MAPPING = {
    "understand":      "understand",
    "extra_tips":      "extra_tip",
    "common_mistakes": "common_mistake",
    "practice":        "practice",
}

# ─── 3. Helper functions ─────────────────────────
def normalize_phrase_for_lookup(phrase_text: str) -> str:
    """Remove punctuation and extra whitespace for phrase matching"""
    return re.sub(r'[^\w\s]', '', phrase_text).strip()

def find_phrase_id(phrase_text: str, variant: int) -> str | None:
    """Find phrase_id by phrase text and variant"""
    try:
        # Get all phrases with the same variant
        phrase_query = sb.table("phrases").select("id, phrase").eq("variant", variant).execute()

        normalized_input = normalize_phrase_for_lookup(phrase_text.upper())

        for row in phrase_query.data:
            normalized_db_phrase = normalize_phrase_for_lookup(row["phrase"])
            if normalized_db_phrase == normalized_input:
                return row["id"]

        return None
    except Exception as e:
        print(f"Warning: Could not find phrase '{phrase_text}' variant {variant}: {e}")
        return None


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

    # Separate collections for different table insertions
    audio_snippets_rows, phrases_audio_rows = [], []
    seen_audio, seen_phrases = set(), set()
    dupes = defaultdict(list)

    for path in all_objects:
        if "/Conversations/" in path or not path.lower().endswith(".mp3"):
            continue

        filename = path.split("/")[-1]

        # 1) Phrases & Verbs first (these live under Phrases_Verbs/, no stage directory)
        phrases_match = PHRASES_FILE_RE.fullmatch(filename)
        if phrases_match:
            phrase_key = phrases_match["phrase_key"]
            variant = int(phrases_match["variant"]) if phrases_match["variant"] else 0
            seq = int(phrases_match["seq"])

            phrase_text = phrase_key.replace("_", " ").upper()
            phrase_id = find_phrase_id(phrase_text, variant)
            if not phrase_id:
                print(f"Skipping {filename}: phrase '{phrase_text}' variant {variant} not found in DB")
                continue

            key = (phrase_id, variant, seq)
            if key in seen_phrases:
                dupes[key].append(path); continue
            seen_phrases.add(key)

            phrases_audio_rows.append({
                "phrase_id": phrase_id,
                "variant": variant,
                "seq": seq,
                "storage_path": path,
            })
            continue  # done with phrases file

        # 2) Standard sections (these live under {Stage}/L{n}/{Section}/...)
        parts = path.split("/")
        stage = parts[0] if parts else ""
        if stage not in STAGES:
            continue

        standard_match = STANDARD_FILE_RE.fullmatch(filename)
        if standard_match:
            lesson = standard_match["lesson"]
            section = SECTION_MAPPING[standard_match["section"].lower()]
            seq = int(standard_match["seq"])
            character = standard_match["character"]

            key = (lesson, section, seq)
            if key in seen_audio:
                dupes[key].append(path); continue
            seen_audio.add(key)

            audio_snippets_rows.append({
                "lesson_external_id": lesson,
                "section": section,
                "seq": seq,
                "character": character or None,
                "storage_path": path,
            })




    if dupes:
        print("\nSkipped duplicates:")
        for k, ps in dupes.items():
            print(" ", k, "→", ps)

    # Insert audio_snippets
    if audio_snippets_rows:
        print(f"\nUpserting {len(audio_snippets_rows)} rows to audio_snippets …")
        res = (
            sb.table("audio_snippets")
              .upsert(audio_snippets_rows, on_conflict="lesson_external_id,section,seq")
              .execute()
        )
        print(f"✅ Success – {len(res.data)} audio_snippets rows upserted/updated.")

    # Insert phrases_audio_snippets
    if phrases_audio_rows:
        print(f"\nUpserting {len(phrases_audio_rows)} rows to phrases_audio_snippets …")
        res = (
            sb.table("phrases_audio_snippets")
              .upsert(phrases_audio_rows, on_conflict="phrase_id,variant,seq")
              .execute()
        )
        print(f"✅ Success – {len(res.data)} phrases_audio_snippets rows upserted/updated.")

    if not audio_snippets_rows and not phrases_audio_rows:
        print("Nothing to do.")

if __name__ == "__main__":
    main()

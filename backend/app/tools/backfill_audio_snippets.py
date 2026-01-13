"""
Populate the audio_snippets and phrases_audio_snippets tables from objects
already uploaded to the lesson-audio bucket.

Standard sections (understand, practice, etc.) go to audio_snippets table.
Phrases & verbs audio files go to phrases_audio_snippets table.

File patterns:
- Standard: {lesson}_{section}_{seq}_{character}.mp3
- Phrases: phrases_verbs_{phrase_key}[{variant}]_{seq}.mp3

rclone for phrases and verbs:
➜  pailin-abroad git:(master) ✗ rclone copy \
  "pailin_audio:Final/Phrases_Verbs" \
  "supabase:lesson-audio/Phrases_Verbs" \
  --include "phrases_verbs_*.mp3" \
  -P

rclone for standard sections:
➜  pailin-abroad git:(master) ✗ rclone copy \
  "pailin_audio:Final/LX" \
  "supabase:lesson-audio/STAGE/LX"  \

Run:
    python -m app.tools.backfill_audio_snippets
"""

from __future__ import annotations
import json
import os, re, sys
from collections import defaultdict
from supabase import create_client, Client

# ─── 1. Config ─────────────────────────────────────────────────────────────
STAGES = {
    "Beginner",
    "Intermediate",
    "Advanced",
    "Expert",
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
    (?P<lesson>\d+\.(?:\d+|chp|checkpoint))
    _
    (?P<section>understand|practice|extra_tips|common_mistakes|apply|culture_note|prepare)
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
    "apply":           "apply",
    "culture_note":    "culture_note",
    "prepare":         "prepare",
}

# ─── 3. Helper functions ─────────────────────────
AUDIO_TAG_RE = re.compile(r"\[audio:\s*([^\]]+?)\s*\]", re.IGNORECASE)

def normalize_phrase_for_lookup(phrase_text: str) -> str:
    """Normalize punctuation/spacing/case for phrase matching."""
    if not phrase_text:
        return ""
    # Replace punctuation with spaces so tokens stay separated.
    cleaned = re.sub(r"[^\w\s]", " ", phrase_text)
    # Collapse whitespace and normalize case for stable matching.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.upper()

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

_AUDIO_TAG_INDEX = None

def _build_audio_tag_index():
    """
    Build an audio_key -> {jsonb: [...], text: [...]} index from phrases content.
    This is used as a fallback when phrase text matching fails.
    """
    global _AUDIO_TAG_INDEX
    if _AUDIO_TAG_INDEX is not None:
        return _AUDIO_TAG_INDEX

    index = {}
    page_size = 1000
    offset = 0

    while True:
        res = (
            sb.table("phrases")
            .select("id, phrase, variant, content_jsonb, content_jsonb_th, content, content_th")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break

        for row in rows:
            row_id = row.get("id")
            phrase = row.get("phrase") or ""
            variant = row.get("variant")

            # Track which keys we've already added per source for this row.
            seen_jsonb = set()
            seen_text = set()

            for field in ("content_jsonb", "content_jsonb_th"):
                val = row.get(field)
                if not val:
                    continue
                try:
                    blob = json.dumps(val, ensure_ascii=True)
                except Exception:
                    continue
                for match in AUDIO_TAG_RE.finditer(blob):
                    key = (match.group(1) or "").strip()
                    if not key or key in seen_jsonb:
                        continue
                    seen_jsonb.add(key)
                    bucket = index.setdefault(key, {"jsonb": [], "text": []})
                    bucket["jsonb"].append({"id": row_id, "phrase": phrase, "variant": variant})

            for field in ("content", "content_th"):
                val = row.get(field) or ""
                if not val:
                    continue
                for match in AUDIO_TAG_RE.finditer(val):
                    key = (match.group(1) or "").strip()
                    if not key or key in seen_text:
                        continue
                    seen_text.add(key)
                    bucket = index.setdefault(key, {"jsonb": [], "text": []})
                    bucket["text"].append({"id": row_id, "phrase": phrase, "variant": variant})

        offset += page_size
        if len(rows) < page_size:
            break

    _AUDIO_TAG_INDEX = index
    return _AUDIO_TAG_INDEX

def find_phrase_id_by_audio_key(audio_key: str, variant: int | None) -> str | None:
    if not audio_key:
        return None
    index = _build_audio_tag_index()
    entry = index.get(audio_key)
    if not entry:
        return None

    candidates = entry["jsonb"] if entry["jsonb"] else entry["text"]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]["id"]

    if variant is not None:
        filtered = [c for c in candidates if c.get("variant") == variant]
        if len(filtered) == 1:
            return filtered[0]["id"]

    norm_phrases = {normalize_phrase_for_lookup(c.get("phrase") or "") for c in candidates}
    print(
        f"Warning: multiple phrases matched audio key '{audio_key}' "
        f"(variants={[c.get('variant') for c in candidates]}, phrases={sorted(norm_phrases)}); skipping"
    )
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

# ─── 5. Update content_jsonb with audio_key ─────────────────────────────────
def update_lesson_sections_with_audio_keys():
    """Update content_jsonb in lesson_sections to include audio_key for nodes with audio_seq"""
    print("\nUpdating lesson_sections content_jsonb with audio_key values...")

    # First, build an index of audio snippets by lesson_external_id, section, and seq
    print("Building audio snippet index...")
    snippets = sb.table("audio_snippets").select("*").execute()

    # Group snippets by lesson_external_id and section
    from collections import defaultdict
    audio_index = defaultdict(lambda: defaultdict(dict))

    for snip in snippets.data:
        lesson_id = snip.get("lesson_external_id")
        section = snip.get("section")
        seq = snip.get("seq")
        audio_key = snip.get("audio_key")

        # Skip if missing key data
        if not (lesson_id and section and seq and audio_key):
            continue

        audio_index[lesson_id][section][seq] = audio_key

    print(f"Built index with {len(snippets.data)} audio snippets")

    # Get all lesson sections with content_jsonb
    print("Fetching lesson sections...")
    sections = sb.table("lesson_sections").select("id,lesson_id,type,content_jsonb").execute()

    updated_count = 0
    for section in sections.data:
        section_id = section.get("id")
        lesson_id_uuid = section.get("lesson_id")
        section_type = section.get("type")
        content_jsonb = section.get("content_jsonb")

        # Skip if no content_jsonb
        if not content_jsonb:
            continue

        # Get the lesson's external ID
        try:
            lesson_res = sb.table("lessons").select("stage,level,lesson_order").eq("id", lesson_id_uuid).limit(1).execute()
            if not lesson_res.data:
                continue

            lesson_data = lesson_res.data[0]
            lesson_external_id = f"{lesson_data['level']}.{lesson_data['lesson_order']}"
        except Exception as e:
            print(f"Error getting lesson external ID: {e}")
            continue

        # Map section type to audio section key
        section_key = SECTION_MAPPING.get(section_type, section_type)

        # Skip if we don't have audio for this lesson/section
        if lesson_external_id not in audio_index or section_key not in audio_index[lesson_external_id]:
            continue

        section_audio = audio_index[lesson_external_id][section_key]

        # Process content_jsonb nodes
        if isinstance(content_jsonb, list):
            updated = False
            for node in content_jsonb:
                if not isinstance(node, dict):
                    continue

                # Add audio_key if node has audio_seq but no audio_key
                if "audio_seq" in node and node["audio_seq"] and "audio_key" not in node:
                    seq = node["audio_seq"]
                    if seq in section_audio:
                        node["audio_key"] = section_audio[seq]
                        updated = True

            if updated:
                try:
                    sb.table("lesson_sections").update({"content_jsonb": content_jsonb}).eq("id", section_id).execute()
                    updated_count += 1
                    print(f"Updated section {section_id} for lesson {lesson_external_id} ({section_type})")
                except Exception as e:
                    print(f"Error updating section {section_id}: {e}")

    print(f"Updated {updated_count} lesson sections with audio_key values")

# ─── 6. Main ───────────────────────────────────────────────────────────────
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
            # Match exact audio tag first if phrase text lookup fails.
            audio_key_tag = f"phrases_verbs_{phrase_key}{variant if variant > 0 else ''}_{seq}"

            phrase_id = find_phrase_id(phrase_text, variant)
            if not phrase_id:
                phrase_id = find_phrase_id_by_audio_key(audio_key_tag, variant)
                if phrase_id:
                    print(f"Fallback matched {filename} via audio tag {audio_key_tag}")
            if not phrase_id:
                print(
                    f"Skipping {filename}: phrase '{phrase_text}' variant {variant} not found in DB "
                    f"(audio tag {audio_key_tag} also not found)"
                )
                continue

            key = (phrase_id, variant, seq)
            if key in seen_phrases:
                dupes[key].append(path); continue
            seen_phrases.add(key)

            # Generate audio_key for phrases following pattern: phrases_verbs_{phrase_key}_{variant}_{seq}
            seq_str = str(seq).zfill(2)  # Zero-pad seq to 2 digits
            variant_str = str(variant) if variant > 0 else ""
            if variant_str:
                audio_key = f"phrases_verbs_{phrase_key}_{variant_str}_{seq_str}"
            else:
                audio_key = f"phrases_verbs_{phrase_key}_{seq_str}"

            phrases_audio_rows.append({
                "phrase_id": phrase_id,
                "variant": variant,
                "seq": seq,
                "storage_path": path,
                "audio_key": audio_key,
            })
            continue  # done with phrases file

        # 2) Standard sections (these live under {Stage}/L{n}/{Section}/...)
        parts = path.split("/")
        stage_raw = parts[0] if parts else ""
        stage = stage_raw.strip()  # remove any weird spaces

        if stage not in STAGES:
            # Debug log so we can see what’s actually coming back
            print(f"Skipping path with unexpected stage={stage_raw!r}: {path}")
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

            # Generate audio_key for ALL section types following the pattern: {lesson}_{section}_{seq}
            seq_str = str(seq).zfill(2)  # Zero-pad seq to 2 digits (01, 02, etc.)
            audio_key = f"{lesson}_{section}_{seq_str}"

            row = {
                "lesson_external_id": lesson,
                "section": section,
                "seq": seq,
                "character": character or None,
                "storage_path": path,
                "audio_key": audio_key  # Add audio_key for all sections
            }

            audio_snippets_rows.append(row)




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
    else:
        # After upserting audio snippets, update content_jsonb in lesson_sections
        update_lesson_sections_with_audio_keys()

if __name__ == "__main__":
    main()

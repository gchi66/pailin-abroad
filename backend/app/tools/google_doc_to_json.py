"""google_doc_to_lesson_json.py  (v2 – multi‑lesson)
────────────────────────────────────────────────────
Convert a *plain‑text* Google‑Doc export into **one or more** lesson JSON
objects ready for Supabase import.

If the file contains several lessons (e.g. "Lesson 3.1", "Lesson 3.2" …)
this script will emit **an array** of lesson blobs; a single‑lesson file
still emits a single object.

Usage
-----
# single or multi‑lesson doc
python google_doc_to_lesson_json.py lesson_docs/en/level_3.txt \
       --stage Beginner > backend/data/level_3.json

# stdout will contain either
{ "lesson": { … } }                # one lesson
# or
[ { "lesson": { … } }, … ]          # many lessons

Importer tip
------------
Your `import_lessons.py` should accept both:
    payload = json.load(fp)
    lessons = payload if isinstance(payload, list) else [payload]

Nothing else changes.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# ───────────────────────────── regex helpers
HEADING_RE = re.compile(r"^([A-Z][A-Z &']+)(?::\s*(.*))?$", re.I)
QUESTION_NUM_RE = re.compile(r'^\s*\d+\.\s*(.+)$')
OPTION_RE = re.compile(r'^\s*([A-Z])\.\s*(.+)$')
ANSWER_KEY_RE = re.compile(r'^\s*Answer key\s*:?\s*(.*)$', re.IGNORECASE)
LESSON_ID_RE = re.compile(r"^Lesson\s+(\d+)\.(\d+)", re.I)
SPEAKER_RE = re.compile(r"^([^:]{1,50}):\s+(.+)")

SECTION_ORDER = [
    "FOCUS",
    "BACKSTORY",
    "CONVERSATION",
    "COMPREHENSION",
    "APPLY",
    "UNDERSTAND",
    "EXTRA TIPS",
    "COMMON MISTAKES",
    "PHRASES & VERBS",
    "CULTURE NOTE",
    "PRACTICE",
    "PINNED COMMENT",
    "TAGS",
]

SECTION_TYPE_MAP = {
    "APPLY": "apply",
    "UNDERSTAND": "understand",
    "EXTRA TIPS": "extra_tip",
    "COMMON MISTAKES": "common_mistake",
    "CULTURE NOTE": "culture_note",
    "PRACTICE": "practice",
    "PINNED COMMENT": "pinned_comment",
}

# ───────────────────────────── utilities

def chunk_by_headings(lines: List[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {}
    current = None
    for ln in lines:
        m = HEADING_RE.match(ln)
        if not m:
            # not a heading → normal content
            if current is not None:
                buckets.setdefault(current, []).append(ln)
            continue

        heading = m.group(1).strip()                  # raw heading text

        is_top_heading = (
            heading.upper() in SECTION_ORDER
            or re.match(r"LESSON\s+\d+\.\d+$", heading, re.I)   # Lesson 3.3 etc.
        )

        if is_top_heading:
            current = heading.upper()                 # new bucket key
            continue                                   # skip the heading line itself

        # Otherwise it's something like 'LESSON FOCUS', 'SORRY', etc.
        # Treat it as normal content under the current section.
        if current is not None:
            buckets.setdefault(current, []).append(ln)

    return buckets

def parse_lesson_header(raw_header: str, stage: str) -> Tuple[Dict, str]:
    m = LESSON_ID_RE.search(raw_header)
    if not m:
        raise ValueError("Missing 'Lesson X.Y' header: " + raw_header)
    level, order = int(m.group(1)), int(m.group(2))
    title = raw_header.split(":", 1)[1].strip() if ":" in raw_header else raw_header
    return (
        {
            "external_id": f"{level}.{order}",
            "stage": stage,
            "level": level,
            "lesson_order": order,
            "title": title,
        },
        title,
    )


def parse_conversation(lines: List[str]) -> List[Dict]:
    transcript = []
    for ln in lines:
        ln = ln.strip()
        if not ln or ln in {"…", "..."}:
            continue
        m = SPEAKER_RE.match(ln)
        if not m:
            continue
        transcript.append(
            {
                "sort_order": len(transcript) + 1,
                "speaker": m.group(1).strip(),
                "line_text": m.group(2).strip(),
            }
        )
    return transcript

def parse_comprehension(lines: List[str]) -> List[Dict]:
    qs = []
    i = 0
    while i < len(lines):
        # 1) Find question prompt
        m_q = QUESTION_NUM_RE.match(lines[i])
        if not m_q:
            i += 1
            continue
        prompt = m_q.group(1).strip()
        i += 1

        # 2) Jump to "Options"
        while i < len(lines) and not lines[i].strip().lower().startswith("options"):
            i += 1
        i += 1  # skip the "Options" line

        # 3) Collect options
        opts = []
        while i < len(lines):
            m_opt = OPTION_RE.match(lines[i])
            if not m_opt:
                break
            opts.append(f"{m_opt.group(1)}. {m_opt.group(2).strip()}")
            i += 1

        # 4) Skip any blank lines, then look for the "Answer key" header
        ans = []
        # ← insert this blank‐line skipper:
        while i < len(lines) and not lines[i].strip():
            i += 1

        if i < len(lines):
            m_ans = ANSWER_KEY_RE.match(lines[i])
            if m_ans:
                key_text = m_ans.group(1).strip()
                # if the header itself has no letters after the colon,
                # pull the next non‐blank line instead
                if not key_text:
                    i += 1
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    key_text = lines[i].strip()
                ans = [a.strip() for a in key_text.split(',') if a.strip()]
                i += 1

        qs.append({
            "sort_order": len(qs) + 1,
            "prompt":     prompt,
            "options":    opts,
            "answer_key": ans,
        })

    return qs


def build_section(section_name: str, lines: List[str], order: int) -> Dict:
    if section_name == "PHRASES & VERBS":
        items = []
        for ln in lines:
            if "=" not in ln:
                continue
            phrase, rest = ln.split("=", 1)
            translation, *notes = rest.split("(")
            item = {"phrase": phrase.strip(), "translation_th": translation.strip()}
            if notes:
                item["notes"] = notes[0].rstrip(") ").strip()
            items.append(item)
        return {"type": "phrases_verbs", "sort_order": order, "items": items}

    mapped = SECTION_TYPE_MAP.get(section_name)
    if not mapped:
        return {}
    return {
        "type": mapped,
        "sort_order": order,
        "content_md": "\n".join(lines).strip(),
    }


def parse_tags(lines: List[str]) -> List[str]:
    return [t.strip() for t in re.split(r",|\n", " ".join(lines)) if t.strip()]

# ───────────────────────────── convert one lesson chunk

def convert_chunk(chunk: str, stage: str) -> Dict:
    lines = [ln.rstrip() for ln in chunk.splitlines()]
    buckets = chunk_by_headings(lines)
    header_line = next((ln for ln in lines if ln.lstrip().upper().startswith("LESSON")), "")
    lesson, _ = parse_lesson_header(header_line, stage)

    lesson["focus"] = "\n".join(buckets.get("FOCUS", [])).strip()
    lesson["backstory"] = "\n".join(buckets.get("BACKSTORY", [])).strip()

    transcript = parse_conversation(buckets.get("CONVERSATION", []))
    comprehension = parse_comprehension(buckets.get("COMPREHENSION", []))

    sections = []
    order = 1
    for sec in SECTION_ORDER:
        if sec in {"FOCUS", "BACKSTORY", "CONVERSATION", "COMPREHENSION", "TAGS"}:
            continue
        if sec not in buckets:
            continue
        built = build_section(sec, buckets[sec], order)
        if built:
            sections.append(built)
            order += 1

    tags = parse_tags(buckets.get("TAGS", []))

    return {
        "lesson": lesson,
        "transcript": transcript,
        "comprehension_questions": comprehension,
        "sections": sections,
        "tags": tags,
    }

# ───────────────────────────── main converter

def convert(doc_text: str, stage: str):
    # Split on every Lesson header (lookahead keeps delimiter)
    chunks = re.split(r"(?=^\s*Lesson\s+\d+\.\d+)", doc_text, flags=re.M | re.I)
    lessons = [convert_chunk(chunk, stage) for chunk in chunks if chunk.strip()]
    return lessons[0] if len(lessons) == 1 else lessons

# ───────────────────────────── CLI entry‑point

def main() -> None:
    parser = argparse.ArgumentParser(description="Google Doc → lesson JSON converter")
    parser.add_argument("input", type=Path, help="Plain‑text file exported from Google Docs")
    parser.add_argument("--stage", default="", help="Stage (e.g. Beginner)")
    args = parser.parse_args()

    try:
        text = args.input.read_text(encoding="utf-8-sig")
    except Exception as exc:
        sys.exit(f"Error reading {args.input}: {exc}")

    try:
        result = convert(text, stage=args.stage)
    except Exception as exc:
        sys.exit(f"Parsing error: {exc}")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("")

if __name__ == "__main__":
    main()

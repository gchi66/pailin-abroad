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
TITLE_RE = re.compile(r'^#{1,6}\s+(.*)$')

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
    cleaned_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()  # Only strip trailing whitespace

        # Skip separator lines but preserve other whitespace
        if re.match(r'^_{5,}$', line.strip()):
            i += 1
            continue

        # Robust heading detection
        is_heading = False
        raw_line = line.strip()

        # Case 1: Standard ALL-CAPS headings
        if (raw_line.upper() == raw_line and
            any(c.isalpha() for c in raw_line) and
            1 <= len(raw_line.split()) <= 5 and
            not raw_line.startswith(('* ', '- ', '> ')) and
            all(c.isupper() or c in " '\"&-.!?()" for c in raw_line)):  # Added !? here
            is_heading = True

        # Case 2: Special pattern headings (like "A VS. AN")
        elif (re.match(r'^[A-Z][A-Z0-9\s\'"&.\-()]+$', raw_line) and
              len(raw_line) <= 50 and
              len(raw_line.split()) <= 5 and
              not raw_line.endswith('.')):
            is_heading = True

        # Case 3: Lesson Focus special case
        elif raw_line.upper() in ("LESSON FOCUS", "FOCUS"):
            is_heading = True

        if is_heading:
            # Look ahead for blank line
            if i+1 < len(lines) and not lines[i+1].strip():
                i += 1  # Skip the blank line after heading
            cleaned_lines.append(f"## {raw_line}")
            i += 1
        else:
            # Preserve original line exactly (with leading whitespace)
            cleaned_lines.append(line)
            i += 1

    # Join with proper newlines and ensure exactly two newlines between sections
    content_md = '\n'.join(cleaned_lines)
    content_md = re.sub(r'\n{3,}', '\n\n', content_md)  # Normalize newlines

    # Handle special section types
    if section_name == "PHRASES & VERBS":
        items = []
        for ln in cleaned_lines:
            if "=" not in ln:
                continue
            phrase, rest = ln.split("=", 1)
            translation, *notes = rest.split("(")
            item = {
                "phrase": phrase.strip(),
                "translation_th": translation.strip()
            }
            if notes:
                item["notes"] = notes[0].rstrip(") ").strip()
            items.append(item)
        return {
            "type": "phrases_verbs",
            "sort_order": order,
            "items": items
        }

    return {
        "type": SECTION_TYPE_MAP.get(section_name, section_name.lower()),
        "sort_order": order,
        "content_md": content_md.strip()
    }


def parse_tags(lines: List[str]) -> List[str]:
    return [t.strip() for t in re.split(r",|\n", " ".join(lines)) if t.strip()]


def parse_practice(lines: List[str]) -> List[Dict]:
    exercises = []
    current_exercise = None
    current_item = None
    collecting_options = False

    # Join all lines into one string first to handle section splitting
    content = "\n".join(lines)

    # Split into exercise sections by "###" headers or "PRACTICE" headers
    sections = re.split(r'(?m)^(?:###\s*|PRACTICE\s+)', content)

    # Skip any intro content before first section
    if not re.search(r'(?i)TYPE:', sections[0]):
        sections = sections[1:]

    for section in sections:
        if not section.strip():
            continue

        section_lines = section.strip().split("\n")
        current_exercise = None
        current_item = None
        collecting_options = False

        for line in section_lines:
            line = line.strip()
            if not line:
                continue

            # Start new exercise
            if line.upper().startswith("TYPE:"):
                current_exercise = {
                    "kind": line.split(":", 1)[1].strip().lower(),
                    "title": "",
                    "prompt": "",
                    "items": [],
                    "sort_order": len(exercises) + 1
                }
                exercises.append(current_exercise)
                collecting_options = False

            # Exercise title
            elif line.upper().startswith("TITLE:"):
                if current_exercise:
                    current_exercise["title"] = line.split(":", 1)[1].strip()

            # Exercise-level prompt
            elif line.upper().startswith("PROMPT:") and not current_item:
                if current_exercise:
                    current_exercise["prompt"] = line.split(":", 1)[1].strip()

            # Start new item (fill-in-the-blank)
            elif line.upper().startswith("ITEM:"):
                if current_exercise and current_exercise["kind"] == "fill_blank":
                    current_item = {
                        "number": line.split(":", 1)[1].strip(),
                        "text": "",
                        "answer": ""
                    }
                    current_exercise["items"].append(current_item)
                    collecting_options = False

            # Start new question (multiple choice, open-ended, or sentence transform)
            elif line.upper().startswith("QUESTION:"):
                if current_exercise:
                    item_number = line.split(":", 1)[1].strip()

                    if current_exercise["kind"] == "multiple_choice":
                        current_item = {
                            "number": item_number,
                            "text": "",
                            "options": [],
                            "answer": ""
                        }
                    elif current_exercise["kind"] == "open":
                        current_item = {
                            "number": item_number,
                            "text": "",
                            "keywords": ""
                        }
                    elif current_exercise["kind"] == "sentence_transform":
                        current_item = {
                            "number": item_number,
                            "stem": "",
                            "correct": None,  # Will be populated if present
                            "answer": ""
                        }
                    else:
                        # Default structure for any other question type
                        current_item = {
                            "number": item_number,
                            "text": "",
                            "answer": ""
                        }

                    current_exercise["items"].append(current_item)
                    collecting_options = False

            # Item text (fill-in-the-blank)
            elif line.upper().startswith("TEXT:"):
                if current_item and "text" in current_item:
                    current_item["text"] = line.split(":", 1)[1].strip()

            # Stem text (sentence transform)
            elif line.upper().startswith("STEM:"):
                if current_item and current_exercise and current_exercise["kind"] == "sentence_transform":
                    current_item["stem"] = line.split(":", 1)[1].strip()

            # Correct/incorrect flag (sentence transform)
            elif line.upper().startswith("CORRECT:"):
                if current_item and current_exercise and current_exercise["kind"] == "sentence_transform":
                    value = line.split(":", 1)[1].strip().lower()
                    current_item["correct"] = (value == "yes")

            # Question prompt (multiple choice or open-ended)
            elif line.upper().startswith("PROMPT:") and current_item:
                if "text" in current_item:
                    current_item["text"] = line.split(":", 1)[1].strip()

            # Options section marker
            elif line.upper().startswith("OPTIONS:"):
                collecting_options = True
                continue

            # Individual multiple choice option
            elif collecting_options and current_item and re.match(r'^[A-Z]\.', line):
                if current_exercise and current_exercise["kind"] == "multiple_choice" and "options" in current_item:
                    current_item["options"].append(line.strip())

            # Answer (various types)
            elif line.upper().startswith("ANSWER:"):
                if current_item and "answer" in current_item:
                    current_item["answer"] = line.split(":", 1)[1].strip()

            # Keywords (open-ended)
            elif line.upper().startswith("KEYWORDS:"):
                if current_item and current_exercise and current_exercise["kind"] == "open" and "keywords" in current_item:
                    current_item["keywords"] = line.split(":", 1)[1].strip()

    return exercises
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
    practice_items = parse_practice(buckets.get("PRACTICE", []))

    sections = []
    order = 1
    for sec in SECTION_ORDER:
        if sec in {"FOCUS", "BACKSTORY", "CONVERSATION", "COMPREHENSION", "TAGS", "PRACTICE"}:
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
        "practice_exercises": practice_items,
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

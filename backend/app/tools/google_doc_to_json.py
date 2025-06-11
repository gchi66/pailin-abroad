"""google_doc_to_json.py  (v2 – multi‑lesson)
────────────────────────────────────────────────────
Convert a *plain‑text* Google‑Doc export into **one or more** lesson JSON
objects ready for Supabase import.

If the file contains several lessons (e.g. "Lesson 3.1", "Lesson 3.2" …)
this script will emit **an array** of lesson blobs; a single‑lesson file
still emits a single object.

Usage
-----
# single or multi‑lesson doc
python google_doc_to_lesson_json.py lesson_docs/en/level_X.txt \
       --stage Beginner \
       --md lesson_docs/en/level_X.md \
       > backend/data/level_X.json

"""

import argparse
import json
import re
import sys
import logging
import unicodedata as ud
from pathlib import Path
from typing import Dict, List, Tuple

try:
    from .markdown_utils import extract_tables, markdown_to_html
    MARKDOWN_IT_AVAILABLE = True
except ImportError:
    MARKDOWN_IT_AVAILABLE = False
    logging.warning("markdown_utils module not found. Tables will remain in markdown format.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── regex helpers
HEADING_RE = re.compile(r"^([A-Z][A-Z &'’‘]+)(?::\s*(.*))?$", re.I)
QUESTION_NUM_RE = re.compile(r'^\s*\d+\.\s*(.+)$')
OPTION_RE = re.compile(r'^\s*([A-Z])\.\s*(.+)$')
ANSWER_KEY_RE = re.compile(r'^\s*Answer key\s*:?\s*(.*)$', re.IGNORECASE)
# Updated to be more flexible with case and whitespace
LESSON_ID_RE = re.compile(r'^\s*(?:LESSON|Lesson)\s+(\d+)\.(\d+)', re.I)
SPEAKER_RE = re.compile(r"^([^:]{1,50}):\s+(.+)")
TITLE_RE = re.compile(r'^#{1,6}\s+(.*)$')
TABLE_TOKEN_RE = re.compile(r"^\s*TABLE(?:-(\d+))?:\s*$", re.I)
PRACTICE_DIRECTIVE_RE = re.compile(
    r'^\s*(TYPE|TITLE|PROMPT|PARAGRAPH|ITEM|QUESTION|TEXT|STEM|CORRECT|'
    r'ANSWER|OPTIONS|KEYWORDS|INPUTS)\s*:',
    re.I
)
BULLET_CHARS = "•◦‣▪–—"        # common GDoc bullets / dashes

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

# ───────────────────────────── utilities/helpers

def chunk_by_headings(lines: List[str]) -> Dict[str, List[str]]:
    buckets: Dict[str, List[str]] = {}
    current = None
    for ln in lines:
        ln_clean = ln.strip()
        m = HEADING_RE.match(ln_clean)
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

def chunk_by_md_headings(md_lines: list[str]) -> dict[str, list[str]]:
    """
    Splits a markdown lesson chunk into sections by headings like '#### UNDERSTAND'.
    Returns a dict mapping section names (UPPERCASE) to lists of lines.
    """
    buckets = {}
    current = None
    lesson_heading_re = re.compile(r'^[\s\x00-\x1f\x7f-\x9f]*#{0,6}\s*[*_]*(?:LESSON|Lesson)\s+\d+\.\d+')

    for ln in md_lines:
        # STOP processing if we hit a new lesson header (unless it's the first line)
        if lesson_heading_re.match(ln.strip()) and buckets:
            break

        m = re.match(r'^####\s*([A-Z &]+)\s*', ln.strip())
        if m:
            heading = m.group(1).strip().upper()
            if heading in SECTION_ORDER:
                current = heading
                continue
            else:
                current = None
                continue
        if current:
            buckets.setdefault(current, []).append(ln)
    return buckets

def add_md_headers(md_lines: list[str]) -> list[str]:
    """
    For markdown lines, add '## ' before all-caps lines that are not already headings.
    """
    out = []
    for ln in md_lines:
        stripped = ln.strip()
        # If already a markdown heading, leave it
        if stripped.startswith("#"):
            out.append(ln)
            continue
        # If ALL CAPS and not a bullet/list, treat as a header
        if (stripped.upper() == stripped and
            any(c.isalpha() for c in stripped) and
            not stripped.startswith(("*", "-", ">")) and
            1 <= len(stripped.split()) <= 5):
            out.append(f"## {stripped}")
        else:
            out.append(ln)
    return out

def split_md_by_lesson(md_lines: list[str]) -> list[list[str]]:
    """
    Split markdown lines into lesson chunks.
    Returns a list of line lists, one per lesson.
    """
    lesson_chunks = []
    current_chunk = []
    lesson_heading_re = re.compile(r'^[\s\x00-\x1f\x7f-\x9f]*#{0,6}\s*[*_]*(?:LESSON|Lesson)\s+\d+\.\d+')

    for ln in md_lines:
        if lesson_heading_re.match(ln):
            # Save the previous chunk if it exists and has content
            if current_chunk:
                lesson_chunks.append(current_chunk)
            # Start new chunk
            current_chunk = [ln]
        else:
            # Add to current chunk
            current_chunk.append(ln)

    # Don't forget the last chunk!
    if current_chunk:
        lesson_chunks.append(current_chunk)

    # Filter out chunks that don't start with a lesson header
    valid_chunks = []
    for chunk in lesson_chunks:
        if chunk and lesson_heading_re.match(chunk[0]):
            valid_chunks.append(chunk)

    logger.debug(f"Found {len(valid_chunks)} valid markdown lesson chunks")
    return valid_chunks



def normalise_markdown_line(ln: str) -> str:
    """
    • Keep original indentation *unless* the line looks like a bullet.
    • If it *is* a bullet (lots of spaces + bullet char / dash / asterisk),
      shrink the indent to max 3 spaces and convert the lead-in to '- '.
    """
    m = re.match(r'^(\s{0,})([' + re.escape(BULLET_CHARS) + r'\-*])\s+(.*)$', ln)
    if not m:
        # Non-bullet line: return untouched
        return ln

    indent, marker, rest = m.groups()

    # Collapse any indent > 3 down to exactly 2 spaces
    new_indent = '  ' if len(indent) > 2 else indent
    return f"{new_indent}- {rest}"

def fix_leading_spaces(lines: list[str]) -> list[str]:
    """
    Backwards-compatible helper used throughout the script.
    Applies normalise_markdown_line() to every line in the block.
    """
    return [normalise_markdown_line(ln) for ln in lines]

def normalise_block(lines: List[str]) -> List[str]:
    """Apply normalise_markdown_line() to every line in a block."""
    return [normalise_markdown_line(ln) for ln in lines]

def parse_lesson_header(raw_header: str, stage: str) -> Tuple[Dict, str]:
    # Debug the raw header
    logger.debug(f"Parsing header: '{raw_header}'")

    # CHECKPOINT?
    m_chp = re.match(r'\s*CHECKPOINT\s+(\d+)', raw_header, re.I)
    if m_chp:
        level = int(m_chp.group(1))
        return (
            {
                "external_id": f"{level}.chp",
                "stage": stage,
                "level": level,
                "lesson_order": 0,
                "title": f"Level {level} Checkpoint",
            },
            f"Level {level} Checkpoint",
        )

    # More flexible pattern matching for the lesson ID
    m = re.search(r'(?:LESSON|Lesson)\s+(\d+)\.(\d+)', raw_header, re.I)
    if not m:
        logger.error(f"Header pattern match failed for: '{raw_header}'")
        raise ValueError("Missing 'Lesson X.Y' header: " + raw_header)

    level, order = int(m.group(1)), int(m.group(2))

    # Extract title more flexibly, looking for a colon
    title_match = re.search(r'(?:LESSON|Lesson)\s+\d+\.\d+\s*:\s*(.*)', raw_header, re.I)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # Fallback to the original behavior
        title = raw_header.split(":", 1)[1].strip() if ":" in raw_header else raw_header

    logger.debug(f"Extracted level={level}, order={order}, title='{title}'")

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

# ______________Quick practice stuff___________

def strip_practice_directives(lines: list[str]) -> list[str]:
    """
    Return a *new* list with every directive line (TYPE:, TITLE:, …)
    removed, but leave all the surrounding explanatory text intact.
    """
    cleaned = []
    for ln in lines:
        if PRACTICE_DIRECTIVE_RE.match(ln.lstrip()):
            continue            # zap the directive
        cleaned.append(ln)
    return cleaned


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
                # pull the next non‑blank line instead
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

def extract_html_tables(md_path: str) -> List[str]:
    """
    Return every <table>…</table> block from the markdown file.
    Uses markdown_utils.extract_tables, which already gives HTML strings.
    """
    if not md_path or not Path(md_path).exists():
        logger.error("Markdown file not found: %s", md_path)
        return []

    content = Path(md_path).read_text(encoding="utf-8")

    if MARKDOWN_IT_AVAILABLE:
        html_tables = extract_tables(content)   # ← your existing helper
        logger.info("Found %d HTML tables", len(html_tables))
        return html_tables
    else:
        logger.warning("markdown_utils not available—no tables extracted")
        return []



def parse_phrases_verbs_items(plain_lines, md_lines=None):
    """
    Parse PHRASES & VERBS section into an items array.
    Each item will have both content (plain text) and content_md (markdown) fields.
    """
    items = []
    current_phrase = None
    current_variant = 1
    current_content = []

    # Regex to match: PHRASE [n] or PHRASE[n]
    header_re = re.compile(r"^(.*?)(?:\s*\[(\d+)\])?$")

    def is_all_caps_header(ln):
        stripped = ln.strip()
        return (
            stripped
            and stripped.upper() == stripped
            and any(c.isalpha() for c in stripped)
            and not stripped.startswith(("*", "-", ">"))
            and 1 <= len(stripped.split()) <= 5
        )

    # Helper to extract markdown content for a phrase
    def extract_md_for_phrase(phrase, md_lines):
        if not md_lines:
            return None
        phrase_re = re.compile(rf"^{re.escape(phrase)}\s*(?:\[\d+\])?\s*$", re.I)
        start = None
        for i, ln in enumerate(md_lines):
            if phrase_re.match(ln.strip()):
                start = i + 1
                break
        if start is None:
            return None
        # Find next all-caps header or end
        end = len(md_lines)
        for j in range(start, len(md_lines)):
            if is_all_caps_header(md_lines[j]):
                end = j
                break
        return "\n".join(md_lines[start:end]).strip()

    # Helper to extract plain text content for a phrase
    def extract_plain_for_phrase(phrase, plain_lines):
        phrase_re = re.compile(rf"^{re.escape(phrase)}\s*(?:\[\d+\])?\s*$", re.I)
        start = None
        for i, ln in enumerate(plain_lines):
            if phrase_re.match(ln.strip()):
                start = i + 1
                break
        if start is None:
            return None
        # Find next all-caps header or end
        end = len(plain_lines)
        for j in range(start, len(plain_lines)):
            if is_all_caps_header(plain_lines[j]):
                end = j
                break
        content_lines = plain_lines[start:end]
        return "\n".join(fix_leading_spaces(content_lines)).strip()

    # Process each line to identify phrases
    for ln in plain_lines:
        if is_all_caps_header(ln):
            # Save previous phrase if exists
            if current_phrase is not None:
                item = {
                    "phrase": current_phrase,
                    "variant": current_variant,
                    "translation_th": "",
                }

                # Extract plain text content
                plain_content = extract_plain_for_phrase(current_phrase, plain_lines)
                if plain_content:
                    item["content"] = plain_content

                # Extract markdown content
                if md_lines:
                    md_content = extract_md_for_phrase(current_phrase, md_lines)
                    if md_content:
                        item["content_md"] = md_content

                items.append(item)

            # Parse new phrase header
            match = header_re.match(ln.strip().lstrip("#").strip())
            if match:
                current_phrase = match.group(1).strip()
                current_variant = int(match.group(2)) if match.group(2) else 1
            else:
                current_phrase = ln.strip().lstrip("#").strip()
                current_variant = 1
            current_content = []
        else:
            current_content.append(ln)

    # Don't forget the last phrase
    if current_phrase:
        item = {
            "phrase": current_phrase,
            "variant": current_variant,
            "translation_th": "",
        }

        # Extract plain text content
        plain_content = extract_plain_for_phrase(current_phrase, plain_lines)
        if plain_content:
            item["content"] = plain_content

        # Extract markdown content
        if md_lines:
            md_content = extract_md_for_phrase(current_phrase, md_lines)
            if md_content:
                item["content_md"] = md_content

        items.append(item)

    return items

def build_section(section_name: str,
                  lines: List[str],
                  order: int,
                  html_tables: List[str] = None,
                  md_buckets: dict[str, list[str]] | None = None) -> Dict:
    """
    Build a section with both plain text content and markdown content.
    """
    out_lines: list[str] = []
    i = 0
    table_counter = 0
    quick_practice_count = 1

    while i < len(lines):
        raw = ud.normalize('NFKD', lines[i]).translate({
            0x2018: ord("'"), 0x2019: ord("'"),
            0x201C: ord('"'), 0x201D: ord('"'),
            0x00A0: ord(' '), 0x200B: None
        }).rstrip()

        if raw.strip().upper().startswith("QUICK PRACTICE"):
            out_lines.append(f"[[QUICK_PRACTICE_{quick_practice_count}]]")
            quick_practice_count += 1
            i += 1
            continue

        m = TABLE_TOKEN_RE.match(raw)
        if m:
            if m.group(1):
                try:
                    table_index = int(m.group(1)) - 1
                except ValueError:
                    table_index = -1
            else:
                table_index = table_counter
                table_counter += 1

            if html_tables and 0 <= table_index < len(html_tables):
                out_lines.append(html_tables[table_index])
            else:
                out_lines.append(f"<!-- TABLE {table_index+1} MISSING -->")

            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue

        stripped = raw.strip()
        is_heading = False

        # Skip visual separator lines like "_______" or "-----"
        if re.match(r'^[_\-]{3,}$', stripped):
            i += 1
            continue

        if (stripped.upper() == stripped and
            any(c.isalpha() for c in stripped) and
            1 <= len(stripped.split()) <= 5 and
            not stripped.startswith(('* ', '- ', '> ')) and
            all(c.isupper() or c in " '''\"&-.!?();:" for c in stripped)):
            is_heading = True
        elif (re.match(r'^[A-Z][A-Z0-9#\s\'''"&.\-();:]+$', stripped) and
              len(stripped) <= 50 and
              len(stripped.split()) <= 10 and
              not stripped.endswith('.')):
            is_heading = True
        elif stripped.upper() in ("LESSON FOCUS", "FOCUS"):
            is_heading = True

        if is_heading:
            # consume a blank line after the heading if present
            if i + 1 < len(lines) and not lines[i + 1].strip():
                i += 1
            out_lines.append(f"## {stripped}")
        else:
            out_lines.append(raw)

        i += 1

    # Process plain text content
    txt_norm = normalise_block(out_lines)
    plain_txt = "\n".join(txt_norm).strip()

    # Process markdown content
    content_md = None
    md_lines_for_section = None
    if md_buckets and section_name in md_buckets:
        md_lines_for_section = md_buckets[section_name]
        md_lines_for_section = add_md_headers(md_lines_for_section)
        content_md = "\n".join(md_lines_for_section)

    # Debug output
    logger.debug(f"Section: {section_name}")
    logger.debug(f"Plain text content: {plain_txt[:100]}...")
    logger.debug(f"Markdown content: {content_md[:100] if content_md else 'None'}...")

    # Handle phrases and verbs section
    if section_name == "PHRASES & VERBS":
        # Pass both plain and markdown lines to the parser
        items = parse_phrases_verbs_items(
            lines,
            md_lines=md_lines_for_section
        )
        section = {
            "type": "phrases_verbs",
            "sort_order": order,
            "items": items
        }
        return section

    # Build standard section
    section = {
        "type": SECTION_TYPE_MAP.get(section_name, section_name.lower()),
        "sort_order": order,
        "content": plain_txt,
    }

    # Add markdown content if available
    if content_md:
        section["content_md"] = content_md

    return section

def parse_tags(lines: List[str]) -> List[str]:
    return [t.strip() for t in re.split(r",|\n", " ".join(lines)) if t.strip()]



def parse_practice(lines: List[str]) -> List[Dict]:
    """
    Parses a plain‑text lesson file into a list of exercise dicts.
    Adds support for an optional PARAGRAPH: block used by some
    fill‑blank exercises. Existing formats continue to work.
    """
    exercises: List[Dict] = []
    current_exercise = None
    current_item = None
    collecting_options = False
    collecting_paragraph = False
    seen = set()  # (kind, prompt) within this lesson

    # Flatten into one big string so we can split by headers
    content = "\n".join(lines)

    # Split at "### ..." or "PRACTICE ..." markers
    sections = re.split(r'(?m)^(?:###\s*|PRACTICE\s+)', content)

    # Drop any intro stuff before the first TYPE:
    if not re.search(r'(?i)TYPE:', sections[0]):
        sections = sections[1:]

    directive_re = re.compile(
        r'^(TYPE:|TITLE:|PROMPT:|PARAGRAPH:|ITEM:|QUESTION:|TEXT:|STEM:|CORRECT:|ANSWER:|OPTIONS:|KEYWORDS:|INPUTS:)',
        re.I
    )

    for section in sections:
        if not section.strip():
            continue

        section_lines = section.strip().split("\n")

        current_exercise = None
        current_item = None
        collecting_options = False
        collecting_paragraph = False

        for raw_line in section_lines:
            line = raw_line.strip()

            if not line:
                continue

            # ---------- start new exercise ----------
            if line.upper().startswith("TYPE:"):
                current_exercise = {
                    "kind": line.split(":", 1)[1].strip().lower(),
                    "title": "",
                    "prompt": "",
                    "paragraph": "",
                    "items": [],
                    "sort_order": len(exercises) + 1
                }
                exercises.append(current_exercise)

                # ---- Duplicate prompt check ----
                prompt = current_exercise["prompt"] or ""
                key = (current_exercise["kind"], prompt)
                if key in seen:
                    # make it unique without changing meaning
                    current_exercise["prompt"] = f"{prompt} – #{current_exercise['sort_order']}"
                seen.add((current_exercise["kind"], current_exercise["prompt"]))

                current_item = None
                collecting_options = False
                continue

            # ----- exercise‑level fields -----
            if line.upper().startswith("TITLE:"):
                current_exercise["title"] = line.split(":", 1)[1].strip()
                continue

            if line.upper().startswith("PROMPT:") and not current_item:
                current_exercise["prompt"] = line.split(":", 1)[1].strip()
                continue

            # ---------- handle PARAGRAPH block ----------
            if line.upper().startswith("PARAGRAPH:"):
                collecting_paragraph = True
                current_exercise["paragraph"] = line.split(":", 1)[1].lstrip()
                continue  # next line

            if collecting_paragraph:
                # A new directive ends the paragraph
                if directive_re.match(line):
                    collecting_paragraph = False
                    # fall through to normal directive handling
                else:
                    current_exercise["paragraph"] += ("\n" if current_exercise["paragraph"] else "") + line
                    continue  # stay in paragraph collection mode

            # ---------- items ----------
            if line.upper().startswith("ITEM:"):
                if current_exercise["kind"] == "fill_blank":
                    current_item = {
                        "number": line.split(":", 1)[1].strip(),
                        "text": "",        # remains empty for paragraph‑style
                        "answer": ""
                    }
                else:
                    # future‑proof: default item shape
                    current_item = {
                        "number": line.split(":", 1)[1].strip(),
                        "text": "",
                        "answer": ""
                    }
                current_exercise["items"].append(current_item)
                collecting_options = False
                continue

            if line.upper().startswith("QUESTION:"):
                item_number = line.split(":", 1)[1].strip()
                if current_exercise["kind"] == "multiple_choice":
                    current_item = {"number": item_number, "text": "", "options": [], "answer": ""}
                elif current_exercise["kind"] == "open":
                    current_item = {"number": item_number, "text": "", "keywords": ""}
                elif current_exercise["kind"] == "sentence_transform":
                    current_item = {"number": item_number, "stem": "", "correct": None, "answer": ""}
                else:
                    current_item = {"number": item_number, "text": "", "answer": ""}
                current_exercise["items"].append(current_item)
                collecting_options = False
                continue

            # ---------- item‑level fields ----------
            if line.upper().startswith("TEXT:"):
                if current_item and "text" in current_item:
                    current_item["text"] = line.split(":", 1)[1].strip()
                continue

            if line.upper().startswith("STEM:"):
                if current_item and current_exercise["kind"] == "sentence_transform":
                    current_item["stem"] = line.split(":", 1)[1].strip()
                continue

            if line.upper().startswith("CORRECT:"):
                if current_item and current_exercise["kind"] == "sentence_transform":
                    value = line.split(":", 1)[1].strip().lower()
                    current_item["correct"] = (value == "yes")
                    if value == "yes":
                        current_item["answer"] = ""  # no rewrite needed
                continue

            if line.upper().startswith("OPTIONS:"):
                collecting_options = True
                continue

            if collecting_options and current_item and re.match(r'^[A-Z]\.', line):
                current_item.setdefault("options", []).append(line.strip())
                continue

            if line.upper().startswith("ANSWER:"):
                if current_item and "answer" in current_item:
                    # keep empty for already‑correct transforms
                    if not (current_exercise["kind"] == "sentence_transform" and current_item.get("correct") is True):
                        current_item["answer"] = line.split(":", 1)[1].strip()
                continue

            if line.upper().startswith("KEYWORDS:"):
                if current_item and current_exercise["kind"] == "open":
                    current_item["keywords"] = line.split(":", 1)[1].strip()
                continue

            if line.upper().startswith("INPUTS:"):
                if current_item:
                    current_item["inputs"] = int(line.split(":", 1)[1].strip())
                continue

    return exercises
# ───────────────────────────── convert one lesson chunk

def convert_chunk(chunk: str, stage: str, html_tables: List[str], md_lines: list[str] = None) -> Dict:
    """
    Convert a chunk of text into a lesson object.
    Now properly handles both plain text and markdown content.
    """
    lines = [ln.rstrip() for ln in chunk.splitlines()]

    # Process markdown lines if provided
    md_buckets = None
    if md_lines:
        logger.debug(f"Processing {len(md_lines)} markdown lines")
        md_buckets = chunk_by_md_headings(md_lines)
        logger.debug(f"Markdown buckets: {list(md_buckets.keys())}")

        # Debug: show first few lines of each bucket
        for bucket_name, bucket_lines in md_buckets.items():
            logger.debug(f"Bucket {bucket_name}: {len(bucket_lines)} lines")
            for i, line in enumerate(bucket_lines[:3]):
                logger.debug(f"  Line {i}: {repr(line)}")

    # Debug the first few lines to help identify formatting issues
    logger.debug("First 10 lines of plain text:")
    for i, line in enumerate(lines[:10]):
        logger.debug(f"Line {i}: '{line}'")

    buckets = chunk_by_headings(lines)
    logger.debug(f"Plain text buckets: {list(buckets.keys())}")

    # Find header line more reliably
    header_line = ""
    for ln in lines:
        if re.search(r'(?:LESSON|Lesson)\s+\d+\.\d+', ln, re.I):
            header_line = ln
            logger.debug(f"Found lesson header: '{header_line}'")
            break
        if re.match(r'\s*CHECKPOINT\s+\d+', ln, re.I):
            header_line = ln
            break

    if not header_line:
        logger.error("No lesson header found in chunk")
        logger.error(f"Chunk starts with: {chunk[:200]}")
        raise ValueError("Missing 'Lesson X.Y' header in document chunk")

    lesson, _ = parse_lesson_header(header_line, stage)

    lesson["focus"] = "\n".join(buckets.get("FOCUS", [])).strip()
    lesson["backstory"] = "\n".join(buckets.get("BACKSTORY", [])).strip()

    transcript = parse_conversation(buckets.get("CONVERSATION", []))
    comprehension = parse_comprehension(buckets.get("COMPREHENSION", []))

    # Parse practice items
    practice_items = parse_practice(buckets.get("PRACTICE", []))
    embedded_practice = parse_practice(buckets.get("UNDERSTAND", []))

    if embedded_practice:
        for ex in embedded_practice:
            ex["sort_order"] = len(practice_items) + 1
            practice_items.append(ex)
        buckets["UNDERSTAND"] = strip_practice_directives(buckets["UNDERSTAND"])

    # Build sections
    tags = parse_tags(buckets.get("TAGS", []))
    sections = []
    order = 1

    for sec in SECTION_ORDER:
        if sec in {"FOCUS", "BACKSTORY", "CONVERSATION", "COMPREHENSION", "TAGS", "PRACTICE"}:
            continue
        if sec not in buckets:
            continue

        built = build_section(sec, buckets[sec], order, html_tables=html_tables, md_buckets=md_buckets)
        if built:
            sections.append(built)
            order += 1

    return {
        "lesson": lesson,
        "transcript": transcript,
        "comprehension_questions": comprehension,
        "practice_exercises": practice_items,
        "sections": sections,
        "tags": tags,
    }

def convert(doc_text: str, stage: str, html_tables: List[str], md_lines: list[str] = None):
    # Split plain text into lesson chunks
    raw_chunks = re.split(
        r"(?=^\s*(?:LESSON|Lesson)\s+\d+\.\d+|CHECKPOINT\s+\d+)",
        doc_text,
        flags=re.M | re.I
    )

    # Filter out empty chunks
    chunks = [chunk for chunk in raw_chunks if chunk.strip()]

    # Split markdown into lesson chunks
    md_chunks = []
    if md_lines:
        md_chunks = split_md_by_lesson(md_lines)

    # Ensure we have matching counts or pad with None
    while len(md_chunks) < len(chunks):
        md_chunks.append(None)

    logger.info(f"Processing {len(chunks)} plain text chunks and {len(md_chunks)} markdown chunks")

    lessons = []
    for i, chunk in enumerate(chunks):
        md_chunk = md_chunks[i] if i < len(md_chunks) else None

        # Debug logging
        logger.debug(f"Processing lesson {i+1}:")
        logger.debug(f"  Plain text chunk size: {len(chunk)} chars")
        logger.debug(f"  Markdown chunk: {'Yes' if md_chunk else 'No'} ({len(md_chunk) if md_chunk else 0} lines)")

        lessons.append(convert_chunk(chunk, stage, html_tables, md_chunk))

    logger.debug(f"Processed {len(lessons)} lessons")
    return lessons[0] if len(lessons) == 1 else lessons

def main() -> None:
    try:
        logger.info("Starting document conversion")
        parser = argparse.ArgumentParser()
        parser.add_argument("input", help="Input text file")
        parser.add_argument("--stage", required=True, help="Lesson stage")
        parser.add_argument("--md", default="", help="Markdown file path")
        parser.add_argument("--debug", action="store_true")
        args = parser.parse_args()

        logger.debug(f"Args: {args}")
        if args.debug:
            logging.getLogger().setLevel(logging.DEBUG)

        if not Path(args.input).exists():
            logger.error(f"Input file not found: {args.input}")
            sys.exit(1)

        text = Path(args.input).read_text(encoding='utf-8')
        logger.debug(f"Read {len(text)} chars from {args.input}")
        html_tables = extract_html_tables(args.md) if args.md else []
        md_lines = []
        if args.md and Path(args.md).exists():
            md_lines = Path(args.md).read_text(encoding='utf-8').splitlines()

        result = convert(text, stage=args.stage, html_tables=html_tables, md_lines=md_lines)

        # Get count of transcript lines, handling both single and multi-lesson formats
        if isinstance(result, list):
            transcript_count = sum(len(lesson.get('transcript', [])) for lesson in result)
            lesson_count = len(result)
            logger.info(f"Converted {lesson_count} lessons with total {transcript_count} transcript lines")
        else:
            transcript_count = len(result.get('transcript', []))
            logger.info(f"Converted 1 lesson with {transcript_count} transcript lines")

        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        logger.info("Successfully wrote JSON output")

    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

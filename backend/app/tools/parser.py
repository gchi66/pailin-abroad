"""parser.py (v4 – Rich, style‑preserving Google Docs Parser)
────────────────────────────────────────────────────
Convert Google Docs directly to lesson JSON objects using the Google Docs API.
This version extracts all information (headers, transcript, comprehension, practice, etc.),
maps them onto the rich schema from your old JSON, and preserves style (bold, italic, underline)
as well as indent information.
Usage
-----
python -m app.tools.parser <document_id> --stage Beginner --output lesson.json
(Optional: use --raw-output to also dump the raw doc JSON.)
"""

from __future__ import annotations
import argparse
import json
import re
import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Union

from .docs_fetch import fetch_doc      # fetch_doc uses the Google Docs API
from .docwalker import paragraphs      # returns a list of paragraphs with indent and markdown formatting

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── regex helpers (from old parser)
HEADING_RE = re.compile(r"^([A-Z][A-Z &''']+)(?::\s*(.*))?$", re.I)
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-]{2,60}$")
QUESTION_NUM_RE = re.compile(r'^\s*\d+\.\s*(.+)$')
OPTION_RE = re.compile(r'^\s*([A-Z])\.\s*(.+)$')
ANSWER_KEY_RE = re.compile(r'^\s*Answer key\s*:?\s*(.*)$', re.IGNORECASE)
LESSON_ID_RE = re.compile(r'^\s*(?:LESSON|Lesson)\s+(\d+)\.(\d+)', re.I)
SPEAKER_RE = re.compile(r"^([^:]{1,50}):\s+(.+)")
PRACTICE_DIRECTIVE_RE = re.compile(
    r'^\s*(TYPE:|TITLE:|PROMPT:|PARAGRAPH:|ITEM:|QUESTION:|TEXT:|STEM:|CORRECT:|'
    r'ANSWER:|OPTIONS:|KEYWORDS:|INPUTS:)',
    re.I
)

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

# ───────────────────────────── helper functions
def is_subheader(text: str, style: str) -> bool:
    """
    True for HEADING_3…6 *or* for a paragraph that is entirely ALL-CAPS
    (2-60 chars, digits & basic punctuation allowed).
    """
    if style.startswith("HEADING_") and style not in {"HEADING_1", "HEADING_2"}:
        return True
    return bool(UPPER_SUB_RE.match(text.strip()))

# ───────────────────────────── New style-based extraction functions

def paragraphs_with_style(doc_json) -> List[Tuple[str, str]]:
    """
    Yield (text, style) tuples for each paragraph in the doc.
    The text is built using the existing docwalker logic (which applies bold, italic, underline markers)
    and style is taken from paragraphStyle.namedStyleType.
    """
    paragraphs_list = []
    for para in doc_json.get("body", {}).get("content", []):
        p = para.get("paragraph")
        if not p:
            continue
        style = p.get("paragraphStyle", {}).get("namedStyleType", "")
        text = "".join(
            r.get("textRun", {}).get("content", "")
            for r in p.get("elements", [])
        ).replace("\u000b", "\n").strip()
        if text:
            paragraphs_list.append((text, style))
    return paragraphs_list

def extract_sections(doc_json) -> List[Tuple[str, List[str]]]:
    """
    Returns a list of (header, [lines]) tuples for each section.
    A section header is detected either by a paragraph whose style starts with "HEADING"
    or if the paragraph text (trimmed and uppercased, with trailing colon removed) equals one of the special headers.
    Special headers include: FOCUS, LESSON FOCUS, BACKSTORY, CONVERSATION, COMPREHENSION,
    PRACTICE, UNDERSTAND, CULTURE NOTE, and TAGS.
    All subsequent paragraphs are collected as lines.
    """
    sections = []
    current_header = None
    current_lines = []
    special_headers = {
        "FOCUS",
        "BACKSTORY",
        "CONVERSATION",
        "COMPREHENSION",
        "PRACTICE",
        "UNDERSTAND",
        "CULTURE NOTE",
        "COMMON MISTAKES",
        "EXTRA TIPS",
        "PINNED COMMENT",
        "TAGS"
    }

    for text, style in paragraphs_with_style(doc_json):
        stripped = text.strip()
        # Remove any trailing colon for header comparison.
        header_candidate = stripped.upper().rstrip(":")
        if style.startswith("HEADING") or header_candidate in special_headers:
            if current_header is not None:
                sections.append((current_header, current_lines))
            # Use the normalized header (without a trailing colon) if applicable
            header_key = header_candidate if header_candidate in special_headers else stripped
            current_header = header_key
            current_lines = []
        else:
            if current_header is not None:
                current_lines.append((text, style))
    if current_header is not None:
        sections.append((current_header, current_lines))
    return sections

def split_lessons_by_header(sections: List[Tuple[str, List[str]]]) -> List[List[Tuple[str, List[str]]]]:
    """
    Split sections into lessons based on the lesson header (matching LESSON_ID_RE).
    Returns a list where each element is a list of (header, lines) for one lesson.
    """
    lessons = []
    current_lesson = []
    for header, lines in sections:
        if LESSON_ID_RE.match(header):
            if current_lesson:
                lessons.append(current_lesson)
            current_lesson = [(header, lines)]
        else:
            if current_lesson:
                current_lesson.append((header, lines))
    if current_lesson:
        lessons.append(current_lesson)
    return lessons

# ───────────────────────────── GoogleDocsParser class

class GoogleDocsParser:
    def __init__(self):
        pass

    def parse_lesson_header(self, raw_header: str, stage: str) -> Tuple[Dict, str]:
        logger.debug(f"Parsing lesson header: '{raw_header}'")
        m_chp = re.match(r'\s*CHECKPOINT\s+(\d+)', raw_header, re.I)
        if m_chp:
            level = int(m_chp.group(1))
            return ({
                "external_id": f"{level}.chp",
                "stage": stage,
                "level": level,
                "lesson_order": 0,
                "title": f"Level {level} Checkpoint",
            }, f"Level {level} Checkpoint")
        m = re.search(r'(?:LESSON|Lesson)\s+(\d+)\.(\d+)', raw_header, re.I)
        if not m:
            logger.error(f"Lesson header pattern match failed for: '{raw_header}'")
            raise ValueError("Missing 'Lesson X.Y' header: " + raw_header)
        level, order = int(m.group(1)), int(m.group(2))
        title_match = re.search(r'(?:LESSON|Lesson)\s+\d+\.\d+\s*:\s*(.*)', raw_header, re.I)
        if title_match:
            title = title_match.group(1).strip()
        else:
            title = raw_header.split(":", 1)[1].strip() if ":" in raw_header else raw_header
        logger.debug(f"Extracted level={level}, order={order}, title='{title}'")
        return ({
            "external_id": f"{level}.{order}",
            "stage": stage,
            "level": level,
            "lesson_order": order,
            "title": title,
        }, title)

    def parse_raw_transcript(self, lines: List[str]) -> List[Dict]:
        """
        Create a transcript array from raw conversation lines.
        Each nonempty line becomes an entry with no speaker.
        """
        transcript = []
        for i, line in enumerate(lines):
            text = line.strip()
            if text:
                transcript.append({
                    "sort_order": i + 1,
                    "speaker": "",
                    "line_text": text,
                    "indent": 0
                })
        return transcript

    def build_lesson_from_sections(self,
                               lesson_sections: List[Tuple[str, List[Tuple[str, str]]]],
                               stage: str) -> Dict:
        """
        Assemble one lesson object, adding Markdown “## ” sub-headers for any
        paragraph whose Google-Docs style starts with HEADING_3…6.
        """
        # ── lesson header ─────────────────────────────────────────────
        lesson_header, _ = lesson_sections[0]
        lesson_info, _ = self.parse_lesson_header(lesson_header, stage)
        lesson = lesson_info.copy()

        # main fields
        lesson["focus"] = ""
        lesson["backstory"] = ""

        transcript_lines: List[str] = []
        comp_lines: List[str] = []
        practice_lines: List[str] = []
        tags_lines: List[str] = []

        other_sections: List[Dict] = []

        for header, lines in lesson_sections[1:]:
            norm_header = header.strip().upper().rstrip(":")
            # split (text, style) pairs
            texts_only = [t for t, _ in lines]

            if norm_header == "FOCUS":
                lesson["focus"] = "\n".join(texts_only).strip()
            elif norm_header == "BACKSTORY":
                lesson["backstory"] = "\n".join(texts_only).strip()
            elif norm_header == "CONVERSATION":
                transcript_lines.extend(texts_only)
            elif norm_header == "COMPREHENSION":
                comp_lines.extend(texts_only)
            elif norm_header == "PRACTICE":
                practice_lines.extend(texts_only)
            elif norm_header == "TAGS":
                tags_lines.extend(texts_only)
            else:
                # ── build one rich section with “## ” sub-headers ──
                body_parts: List[str] = []
                for text, style in lines:
                    if is_subheader(text, style):
                        body_parts.append("## " + text.strip())
                    else:
                        body_parts.append(text)
                other_sections.append({
                    "type": SECTION_TYPE_MAP.get(norm_header, norm_header.lower()),
                    "sort_order": len(other_sections) + 1,
                    "content": "\n".join(body_parts).strip()
                })

        # ── convert the remaining pieces ─────────────────────────────
        transcript = self.parse_conversation_from_lines(transcript_lines)
        comprehension = self.parse_comprehension(comp_lines)
        practice_exercises = self.parse_practice(practice_lines)
        tags = self.parse_tags(tags_lines)

        return {
            "lesson": lesson,
            "transcript": transcript,
            "comprehension_questions": comprehension,
            "practice_exercises": practice_exercises,
            "sections": other_sections,
            "tags": tags,
        }

    def parse_conversation_from_lines(self, lines: List[str]) -> List[Dict]:
        """
        Extract transcript entries from conversation lines.
        For each line starting with a speaker followed by a colon,
        it extracts the speaker and removes it from the line_text.
        Lines that do not start with a speaker are appended to the previous entry.
        """
        transcript = []
        current_entry = None
        # Use the SPEAKER_RE defined earlier: it captures everything before the first colon as speaker,
        # then the rest of the line as the speech text.
        for raw in lines:
            line = raw.strip()
            if not line:
                continue

            m = SPEAKER_RE.match(line)
            if m:
                speaker, text_rest = m.groups()
                # Create a new transcript entry:
                current_entry = {
                    "sort_order": len(transcript) + 1,
                    "speaker": speaker.strip(),
                    "line_text": text_rest.strip(),
                    "indent": 0
                }
                transcript.append(current_entry)
            else:
                # If the line doesn't match, append it to the previous entry if it exists
                if current_entry:
                    current_entry["line_text"] += " " + line
        return transcript

    def parse_comprehension(self, lines: List[str]) -> List[Dict]:
        """
        Build a list of comprehension-question objects in the format:

            {
                "sort_order": 1,
                "prompt": "…",
                "options": ["A. …", "B. …", …],
                "answer_key": ["C"]
            }

        Expected structure in the doc:

            Prompt
            1. Question text
            Options
            A. …
            B. …
            …
            Answer key: C
            2. Next question …
            …
        """
        questions: List[Dict] = []
        cur_q: Dict | None = None
        options: List[str] = []
        answer_key: List[str] = []

        for raw in lines:
            # Handle \n that slipped through by splitting each paragraph
            for piece in raw.splitlines():
                line = piece.strip()
                if not line or line.lower() in {"prompt", "options"}:
                    continue

                # New question line
                m_q = QUESTION_NUM_RE.match(line)
                if m_q:
                    if cur_q:                       # flush previous
                        cur_q["options"] = options
                        cur_q["answer_key"] = answer_key
                        questions.append(cur_q)

                    prompt = re.sub(r"\bOptions\b$", "", m_q.group(1)).strip()
                    cur_q = {
                        "sort_order": len(questions) + 1,
                        "prompt": prompt,
                    }
                    options, answer_key = [], []
                    continue

                # Option lines
                if OPTION_RE.match(line):
                    options.append(line)
                    continue

                # Answer key
                m_ans = ANSWER_KEY_RE.match(line)
                if m_ans:
                    answer_key = [x.strip() for x in re.split(r"[,\s/]+", m_ans.group(1)) if x.strip()]
                    continue

                # Extra text before “Options” – append to prompt
                if cur_q and not options:
                    cur_q["prompt"] += " " + line

        if cur_q:                                   # flush final
            cur_q["options"] = options
            cur_q["answer_key"] = answer_key
            questions.append(cur_q)

        return questions

    def parse_practice(self, lines: List[str]) -> List[Dict]:
        """
        Convert the flat “directive” block into structured exercises.

        Markers handled:
          TYPE: <multiple_choice | open | ...>
          TITLE: <exercise title>
          PROMPT: <prompt shown above the items>
          PARAGRAPH: <optional explanatory paragraph>
          QUESTION: <n>
          TEXT: <stem>
          OPTIONS:                # the very next lines are A. / B. / …
          ANSWER: <letter(s)>     # for MC
          KEYWORDS: <kw list>     # for open items
          PINNED COMMENT          # everything after this goes into a pinned_comment string
        """
        import re
        exercises: List[Dict] = []
        cur_ex: Dict | None = None  # current exercise being built
        cur_items: List[Dict] = []
        collecting_opts = False

        def flush_exercise():
            nonlocal cur_ex, cur_items
            if cur_ex is not None:
                cur_ex["items"] = cur_items
                exercises.append(cur_ex)
            cur_ex, cur_items = None, []

        def new_exercise(kind: str):
            flush_exercise()
            return {
                "kind": kind,
                "title": "",
                "prompt": "",
                "paragraph": "",
                "items": [],
                "sort_order": len(exercises) + 1,
            }

        # Flatten all lines into a single string and iterate line by line.
        practice_text = "\n".join(lines)
        for line in practice_text.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check for block-level directives
            m_type = re.match(r'^TYPE:\s*(\w+)', line, re.I)
            if m_type:
                cur_ex = new_exercise(m_type.group(1).lower())
                continue

            if cur_ex is None:
                # Skip lines before the first TYPE:
                continue

            if line.startswith("TITLE:"):
                cur_ex["title"] = line.split(":", 1)[1].strip()
                continue
            if line.startswith("PROMPT:"):
                cur_ex["prompt"] = line.split(":", 1)[1].strip()
                continue
            if line.startswith("PARAGRAPH:"):
                cur_ex["paragraph"] = line.split(":", 1)[1].strip()
                continue

            # Item-level directives.
            if line.startswith("QUESTION:"):
                number = line.split(":", 1)[1].strip()
                # Create a new question entry.
                cur_items.append({"number": number})
                collecting_opts = False
                continue

            if line.startswith("TEXT:"):
                # Only proceed if there's an item to update.
                if not cur_items:
                    # Log warning or create a new item automatically.
                    cur_items.append({})
                cur_items[-1]["text"] = line.split(":", 1)[1].strip()
                continue

            if line.startswith("OPTIONS:"):
                collecting_opts = True
                # Ensure the current item has an options list.
                if not cur_items:
                    cur_items.append({})
                cur_items[-1]["options"] = []
                continue

            if line.startswith("ANSWER:"):
                # Only update if there's an existing item.
                if not cur_items:
                    cur_items.append({})
                cur_items[-1]["answer"] = line.split(":", 1)[1].strip()
                collecting_opts = False
                continue

            if line.startswith(("KEYWORDS:", "PINNED COMMENT")):
                kw = line.split(":", 1)[1].strip() if ":" in line else ""
                if kw:
                    if not cur_items:
                        cur_items.append({})
                    cur_items[-1]["keywords"] = kw
                collecting_opts = False
                continue

            # Item bullet lines (e.g., "A. option text")
            m_opt = re.match(r'^\s*([A-Z])\.\s*(.+)$', line)
            if collecting_opts and m_opt:
                if not cur_items:
                    cur_items.append({})
                cur_items[-1].setdefault("options", []).append(line)
                continue

            # Optionally, if not collecting options, append free text to the current question's text.
            if cur_items and not collecting_opts:
                cur_items[-1]["text"] = cur_items[-1].get("text", "") + " " + line

        flush_exercise()
        return exercises



    def parse_tags(self, lines: List[str]) -> List[str]:
        """
        Parse tags as comma-separated phrases, preserving multi-word tags.
        """
        tags_text = " ".join(lines)
        return [tag.strip() for tag in tags_text.split(",") if tag.strip()]

    def convert_document(self, document_id: str, stage: str) -> Union[Dict, List[Dict]]:
        logger.info(f"Converting document {document_id}")
        doc_json = fetch_doc(document_id)
        if not doc_json:
            logger.error("Failed to fetch document")
            return {}
        sections = extract_sections(doc_json)
        lessons = split_lessons_by_header(sections)
        results = []
        for lesson_sections in lessons:
            try:
                lesson_data = self.build_lesson_from_sections(lesson_sections, stage)
                results.append(lesson_data)
            except Exception as e:
                logger.error(f"Error processing a lesson: {e}")
        return results if len(results) > 1 else results[0]


def parse_google_doc(doc_json) -> List[List[Tuple[str, List[str]]]]:
    sections = extract_sections(doc_json)
    lessons = split_lessons_by_header(sections)
    return lessons


def main():
    parser = argparse.ArgumentParser(description='Convert Google Docs to rich lesson JSON')
    parser.add_argument('document_id', help='Google Docs document ID')
    parser.add_argument('--stage', required=True, help='Lesson stage (e.g., Beginner)')
    parser.add_argument('--raw-output', help='File to write raw JSON output (optional)')
    parser.add_argument('--output', help='File to write processed JSON output (default: stdout)')
    args = parser.parse_args()

    try:
        docs_parser = GoogleDocsParser()
        raw_doc = fetch_doc(args.document_id)
        if args.raw_output:
            with open(args.raw_output, 'w', encoding='utf-8') as f:
                json.dump(raw_doc, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote raw document JSON to {args.raw_output}")
        result = docs_parser.convert_document(args.document_id, args.stage)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote processed output to {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        logger.info("Document conversion successful")
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()

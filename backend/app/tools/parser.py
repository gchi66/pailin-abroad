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
from collections import Counter
import argparse
import json
import re
import sys
import logging
import dataclasses
from pathlib import Path
from typing import Dict, List, Tuple, Union

from .docs_fetch import fetch_doc      # fetch_doc uses the Google Docs API
from .docwalker import paragraph_nodes, Node      # returns a list of paragraphs with indent and markdown formatting
from .textutils import is_subheader  # now from textutils, not parser

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── regex helpers (from old parser)
HEADING_RE = re.compile(r"^([A-Z][A-Z &''']+)(?::\s*(.*))?$", re.I)
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-!?$%#]{2,60}$")
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

AUDIO_SECTION_HEADERS = {
    "PRACTICE",
    "COMMON MISTAKES",
    "CULTURE NOTE",
    "UNDERSTAND",
    "EXTRA TIPS",
    "APPLY",
}

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
    or if the paragraph text (trimmed and uppercased, with trailing colon removed) equals one of the special headers,
    or if it starts with 'CHECKPOINT'.
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
        header_candidate = stripped.upper().rstrip(":")
        is_checkpoint = header_candidate.startswith("CHECKPOINT")
        if style.startswith("HEADING") or header_candidate in special_headers or is_checkpoint:
            if current_header is not None:
                sections.append((current_header, current_lines))
            header_key = header_candidate if (header_candidate in special_headers or is_checkpoint) else stripped
            current_header = header_key
            current_lines = []
        else:
            if current_header is not None:
                current_lines.append((text, style))
    if current_header is not None:
        sections.append((current_header, current_lines))
    return sections

def split_lessons_by_header(sections: list[tuple[str, list[tuple[str, str]]]]
                            ) -> list[list[tuple[str, list[tuple[str, str]]]]]:
    """Break the full-doc section list into one sub-list per lesson."""
    lessons, current = [], []
    for header, lines in sections:
        # ORIGINAL: if LESSON_ID_RE.match(header):
        if LESSON_ID_RE.match(header) or header.upper().startswith("CHECKPOINT"):
            if current:
                lessons.append(current)
            current = [(header, lines)]
        else:
            if current:
                current.append((header, lines))
    if current:
        lessons.append(current)
    return lessons

def tag_audio_sequences(doc_json):
    current_header = None
    seq_counter = {h: 0 for h in AUDIO_SECTION_HEADERS}
    tagged_nodes = []

    for n in paragraph_nodes(doc_json):
        # Are we entering a new heading?
        if n.kind == "heading":
            header_text = "".join(s.text for s in n.inlines).strip().upper().rstrip(":")
            if header_text in AUDIO_SECTION_HEADERS:
                current_header = header_text              # inside audio section
            elif header_text.startswith(("LESSON", "CHECKPOINT")):
                current_header = None                     # reset between lessons
            continue

        # If inside an audio section and on a bullet, number it
        if current_header and n.kind == "list_item":
            seq_counter[current_header] += 1
            n_dict = dataclasses.asdict(n)
            n_dict["audio_seq"] = seq_counter[current_header]
            n_dict["audio_section"] = SECTION_TYPE_MAP.get(
                current_header, current_header.lower()
            )
            tagged_nodes.append(n_dict)
        else:
            tagged_nodes.append(dataclasses.asdict(n))

    return tagged_nodes

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

    def parse_phrases_verbs(self, lines: List[Tuple[str, str]]) -> List[dict]:
        """
        Parse PHRASES & VERBS section into an items array.
        Each item will have: phrase, variant, translation_th, content.
        Subheading detection is supported (all-caps or heading style lines, including punctuation like 'OH!').
        """
        items = []
        current = None
        current_variant = 1
        current_content = []
        current_translation = ""
        header_re = re.compile(r"^(.*?)(?:\s*\[(\d+)\])?$")

        for text, style in lines:
            if is_subheader(text, style):
                # Save previous item
                if current is not None:
                    items.append({
                        "phrase": current,
                        "variant": current_variant,
                        "translation_th": current_translation.strip(),
                        "content": "\n".join(current_content).strip()
                    })
                # Parse new header
                match = header_re.match(text.strip().lstrip("#").strip())
                if match:
                    current = match.group(1).strip()
                    current_variant = int(match.group(2)) if match.group(2) else 1
                else:
                    current = text.strip().lstrip("#").strip()
                    current_variant = 1
                current_content = []
                current_translation = ""
            elif text.strip().startswith("[TH]"):
                current_translation = text.strip()[4:].strip()
            else:
                current_content.append(text)
        # Don't forget the last item
        if current is not None:
            items.append({
                "phrase": current,
                "variant": current_variant,
                "translation_th": current_translation.strip(),
                "content": "\n".join(current_content).strip()
            })
        return items



    def build_lesson_from_sections(
        self,
        lesson_sections: list[tuple[str, list[tuple[str, str]]]],
        stage: str,
        doc_json,
    ) -> dict:
        # ---- header & bucket bookkeeping -----------------------------------
        lesson_header, _ = lesson_sections[0]
        lesson_info, _   = self.parse_lesson_header(lesson_header, stage)
        lesson           = lesson_info.copy()
        lesson["focus"]      = ""
        lesson["backstory"]  = ""

        transcript_lines:      list[str] = []
        comp_lines:            list[str] = []
        practice_lines:        list[str] = []
        tags_lines:            list[str] = []
        pinned_comment_lines:  list[str] = []
        other_sections:        list[dict] = []

        # One pass: every paragraph, already tagged with audio_seq where needed
        tagged_nodes = tag_audio_sequences(doc_json)

        # --------------------------------------------------------------------
        for header, lines in lesson_sections[1:]:
            norm_header = header.strip().upper().rstrip(":")
            texts_only  = [t for t, _ in lines]

            # ---- simple text buckets ---------------------------------------
            if   norm_header == "FOCUS":
                lesson["focus"] = "\n".join(texts_only).strip()
                continue
            elif norm_header == "BACKSTORY":
                lesson["backstory"] = "\n".join(texts_only).strip()
                continue
            elif norm_header == "CONVERSATION":
                transcript_lines += texts_only
                continue
            elif norm_header == "COMPREHENSION":
                comp_lines += texts_only
                continue
            elif norm_header == "PRACTICE":
                practice_lines += texts_only
                continue
            elif norm_header == "TAGS":
                tags_lines += texts_only
                continue
            elif norm_header == "PHRASES & VERBS":
                items = self.parse_phrases_verbs(lines)
                other_sections.append({
                    "type":       "phrases_verbs",
                    "sort_order": len(other_sections) + 1,
                    "items":      items,
                })
                continue
            elif norm_header == "PINNED COMMENT":
                pinned_comment_lines += texts_only
                continue
            elif norm_header.startswith("CHECKPOINT"):
                other_sections.append({
                    "type":       "checkpoint",
                    "sort_order": len(other_sections) + 1,
                    "content":    "\n".join(texts_only).strip(),
                })
                continue

            # ---- rich-text + (optional) audio bullets ----------------------
            RICH_AUDIO_HEADERS = {
                "UNDERSTAND", "EXTRA TIPS", "CULTURE NOTE", "COMMON MISTAKES"
            }

            if norm_header in RICH_AUDIO_HEADERS:
                section_key = SECTION_TYPE_MAP.get(norm_header, norm_header.lower())
                node_list: list[dict] = []

                # Collect just the paragraphs whose *plain text* matches this section
                wanted = Counter(texts_only)
                for n in tagged_nodes:
                    plain = "".join(s["text"] for s in n["inlines"]).strip()
                    if wanted[plain] == 0:
                        continue
                    node_list.append(n)            # already carries audio_seq if bullet
                    wanted[plain] -= 1
                    if wanted[plain] == 0:
                        del wanted[plain]
                    if not wanted:
                        break

                # fallback plain-text (Markdown) version
                body_parts = [
                    f"## {t.strip()}" if is_subheader(t, style) else t
                    for t, style in lines
                ]

                other_sections.append({
                    "type":          section_key,
                    "sort_order":    len(other_sections) + 1,
                    "content_jsonb": node_list,
                    "content":       "\n".join(body_parts).strip(),
                })
            else:
                # ---- legacy / plain-text section (e.g. APPLY) -------------
                body_parts = [
                    f"## {t.strip()}" if is_subheader(t, style) else t
                    for t, style in lines
                ]
                other_sections.append({
                    "type":       SECTION_TYPE_MAP.get(norm_header, norm_header.lower()),
                    "sort_order": len(other_sections) + 1,
                    "content":    "\n".join(body_parts).strip(),
                })

        # --------------------------------------------------------------------
        lesson_obj = {
            "lesson":                  lesson,
            "transcript":              self.parse_conversation_from_lines(transcript_lines),
            "comprehension_questions": self.parse_comprehension(comp_lines),
            "practice_exercises":      self.parse_practice(practice_lines),
            "sections":                other_sections,
            "tags":                    self.parse_tags(tags_lines),
        }
        if pinned_comment_lines:
            lesson_obj["pinned_comment"] = "\n".join(pinned_comment_lines).strip()

        return lesson_obj


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
                lesson_data = self.build_lesson_from_sections(lesson_sections, stage, doc_json)
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

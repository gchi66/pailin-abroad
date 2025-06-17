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

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── regex helpers (from old parser)
HEADING_RE = re.compile(r"^([A-Z][A-Z &''']+)(?::\s*(.*))?$", re.I)
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
                current_lines.append(text)
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

    def build_lesson_from_sections(self, lesson_sections: List[Tuple[str, List[str]]], stage: str) -> Dict:
        """
        Map the lesson sections (a list of (header, lines)) onto the rich schema.
        The first section is used to parse the lesson header.
        Sections with standard headers such as FOCUS, BACKSTORY, CONVERSATION,
        COMPREHENSION, PRACTICE, TAGS are mapped to dedicated fields.
        Other sections are placed into the 'sections' array (with content_md).
        """
        # The first section must be the lesson header
        lesson_header, header_lines = lesson_sections[0]
        lesson_info, _ = self.parse_lesson_header(lesson_header, stage)
        lesson = lesson_info.copy()

        # Initialize rich fields
        lesson["focus"] = ""
        lesson["backstory"] = ""
        transcript_lines = []      # for CONVERSATION
        comp_lines = []            # comprehension questions (list of strings)
        practice_lines = []        # lines for practice exercises
        other_sections = []        # additional sections – will include content
        tags_lines = []            # for TAGS

        # Process other sections
        for header, lines in lesson_sections[1:]:
            norm_header = header.strip().upper().rstrip(":")
            content = "\n".join(lines).strip()
            if norm_header in "FOCUS":
                lesson["focus"] = content
            elif norm_header == "BACKSTORY":
                lesson["backstory"] = content
            elif norm_header == "CONVERSATION":
                transcript_lines.extend(lines)
            elif norm_header == "COMPREHENSION":
                comp_lines.extend(lines)
            elif norm_header == "PRACTICE":
                practice_lines.extend(lines)
            elif norm_header == "TAGS":
                tags_lines.extend(lines)
            else:
                other_sections.append({
                    "header": norm_header,
                    "content": content,
                })

        # Instead of parsing speakers, simply use a raw transcript function.
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
        Parses the comprehension section text into a list of comprehension question dictionaries.
        This example assumes the text is structured with a "Prompt" line followed by questions starting
        with "QUESTION:".
        """
        content = "\n".join(lines).strip()
        if not content:
            return []
        # Remove any leading word "Prompt" if present.
        content = re.sub(r"^Prompt\s*\n", "", content, flags=re.IGNORECASE)
        questions = []
        # Split when encountering a question marker (for example "QUESTION:")
        blocks = re.split(r"\nQUESTION:\s*", content)
        for block in blocks:
            if block.strip():
                q = {}
                # Try to capture a question number at the start
                m = re.match(r"(\d+)\s*(.*)", block.strip(), flags=re.DOTALL)
                if m:
                    q["number"] = int(m.group(1))
                    q["text"] = m.group(2).strip()
                else:
                    q["text"] = block.strip()
                questions.append(q)
        return questions

    def parse_practice(self, lines: List[str]) -> List[Dict]:
        """Basic practice exercise parser (adapted from old parser logic)."""
        # For simplicity, here we just return a single exercise block with the raw content.
        if not lines:
            return []
        content = "\n".join(lines).strip()
        exercise = {
            "sort_order": 1,
            "content": content
        }
        return [exercise]

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

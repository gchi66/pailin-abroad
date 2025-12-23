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
from .docwalker import paragraph_nodes, Node
from .textutils import is_subheader

SCOPES = ['https://www.googleapis.com/auth/documents.readonly']

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ───────────────────────────── regex helpers
HEADING_RE = re.compile(r"^([A-Z][A-Z &''']+)(?::\s*(.*))?$", re.I)
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-!?$%#]{2,60}$")
QUESTION_NUM_RE = re.compile(r'^\s*\d+\.\s*(.+)$')
OPTION_RE = re.compile(r'^\s*([A-Z])\.\s*(.+)$')
BULLET_RE = re.compile(r"^\s*[–—\-*•●▪◦·・►»]\s+")
ANSWER_KEY_RE = re.compile(r'^\s*Answer key\s*:?\s*(.*)$', re.IGNORECASE)
AUDIO_TAG_RE = re.compile(r'\[audio:\s*([^\]]+?)\s*\]', re.IGNORECASE)
IMG_TAG_RE = re.compile(r'\[img:\s*([^\]]+?)\s*\]', re.IGNORECASE)
ALT_TEXT_RE = re.compile(r'ALT[\s-]*TEXT\s*:\s*(.+)', re.IGNORECASE | re.DOTALL)
LESSON_ID_RE = re.compile(r'^\s*(?:LESSON|Lesson)\s+(\d+)\.(\d+)', re.I)
SPEAKER_RE = re.compile(r"^([^:]{1,50}):\s+(.+)")
SPEAKER_RE_TH = re.compile(r'^([\u0E00-\u0E7F][^:]{0,50}):\s*(.+)$')
TH = re.compile(r'[\u0E00-\u0E7F]')
EN = re.compile(r'[A-Za-z]')
PRACTICE_DIRECTIVE_RE = re.compile(
    r'^\s*(TYPE:|TITLE:|PROMPT:|PARAGRAPH:|ITEM:|QUESTION:|TEXT:|STEM:|CORRECT:|'
    r'ANSWER:|OPTIONS:|KEYWORDS:|INPUTS:)',
    re.I
)

SECTION_ORDER = [
    "FOCUS",
    "BACKSTORY",
    "CONVERSATION",
    "PREPARE",
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
    "PREPARE",
    "COMMON MISTAKES",
    "CULTURE NOTE",
    "UNDERSTAND",
    "EXTRA TIPS",
    "APPLY",
    "PHRASES & VERBS",
}

SECTION_TYPE_MAP = {
    "APPLY": "apply",
    "UNDERSTAND": "understand",
    "EXTRA TIPS": "extra_tip",
    "COMMON MISTAKES": "common_mistake",
    "CULTURE NOTE": "culture_note",
    "PRACTICE": "practice",
    "PINNED COMMENT": "pinned_comment",
    "PHRASES & VERBS": "phrases_verbs",
    "PREPARE": "prepare",
}


# ───────────────────────────── helper functions

def _has_en(s: str | None) -> bool:
    return bool(s and EN.search(s))

def _has_th(s: str | None) -> bool:
    return bool(s and TH.search(s))

def _plain_text(elems: list[dict]) -> str:
    """Concatenate all textRun content inside a list of Google-Docs elements."""
    parts = [el.get("textRun", {}).get("content", "") for el in elems]
    return "".join(parts).strip()

def _table_block(elem: dict, tbl_id: int) -> dict:
    """Convert a Google-Docs table element to a minimal table node."""
    rows = []
    for row in elem["table"]["tableRows"]:
        row_cells = []
        for cell in row["tableCells"]:
            cell_lines = []
            for para in cell.get("content", []):
                if "paragraph" in para:
                    cell_lines.append(_plain_text(para["paragraph"]["elements"]))
            row_cells.append("\n".join(cell_lines))
        rows.append(row_cells)

    return {
        "kind":  "table",
        "type":  "table",
        "id":    f"table-{tbl_id}",
        "rows":  len(rows),
        "cols":  len(rows[0]) if rows else 0,
        "cells": rows,
    }

def _count_th(s: str) -> int:
    return len(TH.findall(s or ""))

def _count_en(s: str) -> int:
    return len(EN.findall(s or ""))

def _norm_header_str(s: str | None) -> str:
    if not s: return ""
    return re.sub(r"\s+", " ", (s or "").replace("\u000b", " ").strip())

def _lesson_key(s: str | None) -> str | None:
    if not s: return None
    m = LESSON_ID_RE.search(s)
    return f"{m.group(1)}.{m.group(2)}" if m else None

def _extract_audio_key(inlines: list[dict] | None) -> str | None:
    """Return the first [audio:...] key found in inline text."""
    if not inlines:
        return None
    for inline in inlines:
        text = inline.get("text")
        if not text:
            continue
        match = AUDIO_TAG_RE.search(text)
        if match:
            return (match.group(1) or "").strip()
    return None

def _norm2(s: str) -> str:
    # robust normalization for matching docwalker nodes to section lines
    return re.sub(r"\s+", " ", (s or "").replace("\u000b", " ").replace("\n", " ").strip())

def _lang_of_entry(e: dict) -> str:
    """
    Classify an entry as 'TH', 'EN', or 'MIXED' with robust heuristics:
    1) If speaker has Thai, it's TH.
    2) Else if speaker has Latin (and no Thai), it's EN.
    3) Else decide by counts in line_text; use dominance so a few acronyms (USC/PM) don't flip TH.
    """
    spk = (e.get("speaker") or "").strip()
    txt = (e.get("line_text") or "").strip()

    if TH.search(spk):
        return "TH"
    if EN.search(spk) and not TH.search(spk):
        return "EN"

    th = _count_th(txt)
    en = _count_en(txt)
    if th and not en:
        return "TH"
    if en and not th:
        return "EN"


    if th >= en + 3:
        return "TH"
    if en >= th + 3:
        return "EN"
    return "MIXED"


# ───────────────────────────── module-level bilingual helpers
def split_en_th(line: str):
    if not line: return None, None
    line = line.strip()

    # "EN (TH)" pattern
    m = re.match(r'^(.*?)\s*\(([\u0E00-\u0E7F].*?)\)\s*$', line)
    if m:
        en = m.group(1).strip() or None
        th = m.group(2).strip() or None
        return en, th

    # "EN … TH" pattern (first Thai char starts TH)
    # Look for the first Thai character
    thai_start = -1
    for i, ch in enumerate(line):
        if '\u0E00' <= ch <= '\u0E7F':  # Thai Unicode range
            thai_start = i
            break

    if thai_start >= 0:
        # Find a good split point - prefer splitting at word boundaries
        # Look backwards from thai_start to find a space
        split_point = thai_start
        for i in range(thai_start - 1, -1, -1):
            if line[i] == ' ':
                split_point = i + 1
                break

        en = line[:split_point].strip() or None
        th = line[split_point:].strip() or None
        return en, th

    # mono language
    if TH.search(line):
        return None, line.strip() or None
    return line.strip() or None, None

def node_plain_text(node):
    if "text" in node and isinstance(node["text"], str):
        return node["text"]
    if "inlines" in node:
        return ''.join(run.get("text", "") for run in node["inlines"])
    return ""


def bilingualize_headers_th(nodes, default_level=3):
    FOCUS_EN = "LESSON FOCUS"
    FOCUS_TH = "จุดเน้นบทเรียน"
    KNOWN_TITLE_PREFIXES = {
        "QUICK PRACTICE",
        "AFFIRMATIVE & NEGATIVE SENTENCES",
        "MAKING QUESTIONS",
        "USES OF ‘WAS’ AND ‘WERE’",
        "PAST TENSE TO-BE VERBS",
    }

    def _clone_node(node: dict) -> dict:
        clone = dict(node)
        if "inlines" in clone and isinstance(clone["inlines"], list):
            clone["inlines"] = [dict(run) for run in clone["inlines"]]
        return clone

    def _apply_bilingual_text(node: dict, en: str | None, th: str | None) -> dict:
        label_parts = [part.strip() for part in (en, th) if part and part.strip()]
        label = " ".join(label_parts) if label_parts else node_plain_text(node)

        node["kind"] = "heading"
        node["level"] = node.get("level", default_level)
        node["text"] = {"en": en, "th": th}

        inlines = node.get("inlines")
        if inlines:
            first = dict(inlines[0])
            first["text"] = label
            first.setdefault("bold", False)
            first.setdefault("italic", False)
            first.setdefault("underline", False)
            first.setdefault("link", None)
            node["inlines"] = [first]
        else:
            node["inlines"] = [{
                "text": label,
                "bold": False,
                "italic": False,
                "underline": False,
                "link": None,
            }]
        return node

    def _looks_like_known_title(en_part: str | None) -> bool:
        if not en_part:
            return False
        upper = en_part.strip().upper()
        return any(upper.startswith(prefix) for prefix in KNOWN_TITLE_PREFIXES)

    out = []

    for original in nodes:
        node = _clone_node(original)

        if node.get("kind") == "paragraph":
            para_text = node_plain_text(node).strip()
            if para_text.upper() == FOCUS_EN:
                out.append(_apply_bilingual_text(node, FOCUS_EN, FOCUS_TH))
                continue

        if node.get("kind") in {"heading", "header"}:
            if isinstance(node.get("text"), dict):
                text_en = (node["text"].get("en") or "").strip().upper()
                if text_en == FOCUS_EN and not node["text"].get("th"):
                    node["text"] = {**node["text"], "th": FOCUS_TH}

            s = node_plain_text(node)
            en, th = split_en_th(s)
            if en or th:
                out.append(_apply_bilingual_text(node, en, th))
            else:
                out.append(node)
            continue

        if node.get("kind") == "paragraph":
            s = node_plain_text(node)
            has_th = bool(TH.search(s))
            has_en = bool(re.search(r'[A-Za-z]', s))

            looks_like_title = False
            en_part = None
            if has_en:
                en_part, _ = split_en_th(s)
                if en_part:
                    en_stripped = en_part.strip()
                    looks_like_title = (
                        (en_stripped and en_stripped.upper() == en_stripped and re.search(r'[A-Z]', en_stripped))
                        or _looks_like_known_title(en_part)
                    )

            if has_th and (looks_like_title or node.get("is_bold_header")):
                en, th = split_en_th(s)
                if en or th:
                    node.pop("style", None)
                    out.append(_apply_bilingual_text(node, en, th))
                    continue

        out.append(node)

    return out


def pair_transcript_bilingual(entries: list[dict]) -> list[dict]:
    """
    Merge EN+TH transcript lines into single rows with speaker_th / line_text_th.
    Robust to Thai lines containing a few Latin tokens (e.g., USC, 6PM, In-N-Out).
    """
    out = []
    i = 0
    order = 1

    while i < len(entries):
        a = dict(entries[i])  # copy
        la = _lang_of_entry(a)

        # Look ahead
        b = entries[i + 1] if i + 1 < len(entries) else None
        lb = _lang_of_entry(b) if b else None

        # ── Case C: inline mixed EN+TH in the same entry (only when speaker isn't clearly TH)
        # e.g., "Good morning (สวัสดีตอนเช้า)" or "EN … TH" in one line
        if la == "MIXED":
            # Try to split inline TH from the text only, not the speaker
            en_txt, th_txt = split_en_th(a.get("line_text", ""))
            spk_th = None
            if th_txt:
                # If author inlined a Thai speaker ("ไพลิน: ..."), extract it
                mth = SPEAKER_RE_TH.match(th_txt)
                if mth:
                    spk_th, th_txt = mth.group(1).strip(), mth.group(2).strip()

            merged = a
            if en_txt is not None:
                merged["line_text"] = en_txt
            merged["speaker_th"]   = spk_th
            merged["line_text_th"] = th_txt
            merged["sort_order"]   = order
            out.append(merged)
            i += 1
            order += 1
            continue

        # ── Case A: EN-only (or EN-dominant) followed by TH-only (or TH-dominant)
        if la == "EN" and b and lb == "TH":
            merged = a
            merged["speaker_th"]   = b.get("speaker")
            merged["line_text_th"] = b.get("line_text")
            merged["sort_order"]   = order
            out.append(merged)
            i += 2
            order += 1
            continue

        # ── Case B: TH-only (or TH-dominant) followed by EN-only (or EN-dominant)
        if la == "TH" and b and lb == "EN":
            merged = dict(b)
            merged["speaker_th"]   = a.get("speaker")
            merged["line_text_th"] = a.get("line_text")
            merged["sort_order"]   = order
            out.append(merged)
            i += 2
            order += 1
            continue

        # ── TH-only with no pair → keep as TH-only row (blank EN fields)
        if la == "TH":
            out.append({
                "sort_order":   order,
                "speaker":      "",
                "line_text":    "",
                "indent":       a.get("indent", 0),
                "speaker_th":   a.get("speaker"),
                "line_text_th": a.get("line_text"),
            })
            i += 1
            order += 1
            continue

        # ── EN-only (or fallback) → keep as-is
        a["sort_order"] = order
        out.append(a)
        i += 1
        order += 1

    return out


# ───────────────────────────── Style-based extraction functions

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

    Now processes ALL content elements (paragraphs AND tables) to avoid skipping lessons with tables.
    """
    sections = []
    current_header = None
    current_lines = []
    table_counter = 0
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

    # Process ALL content elements, not just paragraphs
    for elem in doc_json.get("body", {}).get("content", []):
        # Handle paragraphs (including headers)
        if "paragraph" in elem:
            para = elem["paragraph"]
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            raw_text = "".join(
                r.get("textRun", {}).get("content", "")
                for r in para.get("elements", [])
            ).replace("\u000b", "\n")
            text = raw_text.strip()

            # Preserve blank lines inside a section as explicit entries
            if not text:
                if current_header is not None:
                    current_lines.append(("", style))
                continue

            stripped = text
            header_candidate = stripped.upper().rstrip(":")
            is_checkpoint = header_candidate.startswith("CHECKPOINT")

            # Check if this is a section header
            if style.startswith("HEADING") or header_candidate in special_headers or is_checkpoint:
                if current_header is not None:
                    sections.append((current_header, current_lines))
                header_key = header_candidate if (header_candidate in special_headers or is_checkpoint) else stripped
                current_header = header_key
                current_lines = []
            else:
                # Regular paragraph content
                if current_header is not None:
                    current_lines.append((text, style))

        # Handle tables - add them as placeholder text to preserve document order
        elif "table" in elem:
            table_counter += 1
            table_placeholder = f"TABLE-{table_counter}:"
            if current_header is not None:
                current_lines.append((table_placeholder, ""))

    # Don't forget the last section
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


def tag_nodes_with_sections(doc_json):
    """
    Walk every element (paragraph *and* table) in body.content,
    tag it with lesson / section context and (for bullets) audio indices.
    """
    current_lesson  = None
    current_section = None
    seq_counter     = {h: 0 for h in AUDIO_SECTION_HEADERS}
    table_counter   = 0
    tagged_nodes    = []

    for elem in doc_json["body"]["content"]:
        # ── paragraph / heading ───────────────────────────────────────────
        if "paragraph" in elem:
            para_nodes = list(paragraph_nodes({
                "body":  {"content": [elem]},
                "lists": doc_json.get("lists", {}),   # <-- critical
            }))
            if not para_nodes:
                continue
            n = para_nodes[0]

            if n.kind == "heading":
                hdr = "".join(s.text for s in n.inlines).strip()
                up  = hdr.upper().rstrip(":")
                if LESSON_ID_RE.match(up) or up.startswith("CHECKPOINT"):
                    current_lesson      = hdr
                    current_lesson_key  = _lesson_key(hdr)
                    current_lesson_norm = _norm_header_str(hdr)
                    current_lesson_en, current_lesson_th = split_en_th(hdr)
                    current_section     = None
                    seq_counter         = {h: 0 for h in AUDIO_SECTION_HEADERS}
                elif up in SECTION_ORDER:
                    current_section = up

            nd = dataclasses.asdict(n)
            if current_lesson:
                nd["lesson_context"]       = current_lesson          # keep legacy
                nd["lesson_key"]           = current_lesson_key      # durable key: "1.14"
                nd["lesson_context_norm"]  = current_lesson_norm
                nd["lesson_context_en"]    = current_lesson_en       # NEW
                nd["lesson_context_th"]    = current_lesson_th       # NEW
            if current_section:
                nd["section_context"] = current_section

            audio_key = _extract_audio_key(nd.get("inlines"))
            if audio_key:
                nd["audio_key"] = audio_key

            if current_section in AUDIO_SECTION_HEADERS and n.kind == "list_item":
                seq_counter[current_section] += 1
                nd["audio_seq"]     = seq_counter[current_section]
                nd["audio_section"] = SECTION_TYPE_MAP.get(
                    current_section, current_section.lower())

            tagged_nodes.append(nd)
            continue

        # ── table ─────────────────────────────────────────────────────────
        if "table" in elem:
            table_counter += 1
            tbl = _table_block(elem, table_counter)
            if current_lesson:
                tbl["lesson_context"] = current_lesson
            if current_section:
                tbl["section_context"] = current_section
            tagged_nodes.append(tbl)

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
            # Dynamically compute max lesson order for this level
            # This assumes self.lessons_by_level is set before calling this method
            max_order = 0
            if hasattr(self, "lessons_by_level") and self.lessons_by_level.get(level):
                max_order = max(l.get("lesson_order", 0) for l in self.lessons_by_level[level])
            else:
                logger.warning(f"lessons_by_level not set or no lessons for level {level}, defaulting checkpoint order to 1")
                max_order = 0
            return ({
                "external_id": f"{level}.chp",
                "stage": stage,
                "level": level,
                "lesson_order": max_order + 1,
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


    def parse_phrases_verbs(
        self,
        lines: List[Tuple[str, str]],
        doc_nodes: list[dict],
        lesson_header_raw: str,
        lang: str = "en",
    ) -> List[dict]:
        """
        Parse PHRASES & VERBS section into an items array.
        Each item has:
        phrase, phrase_th, variant, content (plain),
        and content_jsonb / content_jsonb_th preserving bullets and formatting.
        """
        import re

        items: List[dict] = []
        current_phrase: str | None = None
        current_phrase_th: str | None = None
        current_variant: int = 0
        node_buffer: list[dict] = []
        text_buffer: list[str] = []

        # ---------------- regex helpers ----------------
        TH_RX = re.compile(r"[\u0E00-\u0E7F]")                 # Thai block
        HEADER_TRAILING_VARIANT_RX = re.compile(r"\[\s*\d+\s*\]\s*$")  # [1], [ 2 ], etc.

        # ---------------- small utils ------------------
        def _strip_bullets_tabs(s: str) -> str:
            return re.sub(r"^[\t \-–—*•●▪◦·・►»]+", "", (s or "").strip())

        def parse_phrase_and_variant(raw_header: str) -> tuple[str, str, int]:
            """
            Accept bilingual headers and bracketed variants, e.g.:
            'COOL! เยี่ยมเลย [1]' -> ('COOL!', 'เยี่ยมเลย', 1)
            'COOL! [1] เยี่ยมเลย' -> ('COOL!', 'เยี่ยมเลย', 1)
            "LET'S SEE [1]"       -> ("LET'S SEE", '', 1)
            'COOL! เยี่ยมเลย'     -> ('COOL!', 'เยี่ยมเลย', 0)
            """
            s = _strip_bullets_tabs(raw_header.lstrip("#"))
            m = re.search(r"\[\s*(\d+)\s*\]\s*$", s)
            if m:
                variant = int(m.group(1))
                s = s[: m.start()].strip()
            else:
                variant = 0
            en, th = split_en_th(s)  # your existing helper
            phrase = en or s
            phrase_th = th or ""
            return phrase, phrase_th, variant

        def _norm(s: str) -> str:
            s = (s or "").replace("\u000b", " ").replace("\n", " ")
            s = re.sub(r"\([\u0E00-\u0E7F0-9\s.,!?;:'\"-]*\)", "", s)  # drop Thai-ish parens
            s = re.sub(r"\s+", " ", s).strip()
            s = re.sub(r"^[–—\-*•●▪◦·・►»]\s*", "", s)  # strip leading bullets
            return s

        def _flush():
            nonlocal current_phrase, current_phrase_th, current_variant, node_buffer, text_buffer
            if current_phrase is None:
                return
            item = {
                "phrase": current_phrase,
                "phrase_th": current_phrase_th,
                "variant": current_variant,
                "content": "\n".join(text_buffer).strip(),
            }
            if lang == "th":
                item["content_jsonb_th"] = node_buffer
            else:
                item["content_jsonb"] = node_buffer
            items.append(item)
            # reset
            current_phrase = None
            current_phrase_th = None
            current_variant = 0
            node_buffer = []
            text_buffer = []

        # -------- build section-scoped and lesson-wide maps --------
        scoped_nodes: dict[str, list[dict]] = {}
        lesson_wide_nodes: dict[str, list[dict]] = {}

        LKEY = _lesson_key(lesson_header_raw)          # e.g., "1.16"
        LCTXN = _norm_header_str(lesson_header_raw)    # tolerant compare

        for n in doc_nodes:
            if "inlines" not in n:
                continue

            nk = n.get("lesson_key") or _lesson_key(n.get("lesson_context"))
            if LKEY and nk and nk != LKEY:
                continue
            if LKEY and not nk:
                lc = n.get("lesson_context")
                if lc and _norm_header_str(lc) != LCTXN:
                    continue

            plain = "".join(s.get("text", "") for s in n.get("inlines", []))
            key = _norm(plain)
            if not key:
                continue

            lesson_wide_nodes.setdefault(key, []).append(n)
            if n.get("section_context") == "PHRASES & VERBS":
                scoped_nodes.setdefault(key, []).append(n)

        # --------------------- node utilities ----------------------
        def _clone_node(n: dict) -> dict:
            c = n.copy()
            if "inlines" in c:
                c["inlines"] = [i.copy() for i in c["inlines"]]
            return c

        def _trim_node_text(node: dict, desired_text: str) -> None:
            text = (desired_text or "").strip()
            inlines = node.get("inlines") or []
            if not inlines:
                node["inlines"] = [
                    {
                        "text": text,
                        "bold": False,
                        "italic": False,
                        "underline": False,
                        "link": None,
                    }
                ]
                return
            first = inlines[0].copy()
            first["text"] = text
            first.setdefault("bold", False)
            first.setdefault("italic", False)
            first.setdefault("underline", False)
            node["inlines"] = [first]

        def _pick_with_fallback(bucket_map: dict[str, list[dict]], key: str) -> tuple[dict | None, str | None]:
            if bucket_map.get(key):
                return bucket_map[key][0], key
            for k, bucket in bucket_map.items():
                if bucket and (key in k or k in key):
                    return bucket[0], k
            best = None; best_k = None; best_score = 0.0
            a = set(key.split())
            if not a:
                return None, None
            for k, bucket in bucket_map.items():
                if not bucket:
                    continue
                b = set(k.split())
                if not b:
                    continue
                score = len(a & b) / max(len(a), len(b))
                if score > 0.45 and score > best_score:
                    best, best_k, best_score = bucket[0], k, score
            return best, best_k

        def _is_bullet_node(node: dict) -> bool:
            return bool(
                node.get("kind") == "list_item"
                or node.get("bullet")
                or node.get("resolvedListGlyph", {}).get("glyphSymbol")
            )

        def _take_node(raw: str) -> dict | None:
            def _remove_from_other_maps(node: dict) -> None:
                norm_text = _norm("".join(span.get("text", "") for span in node.get("inlines", [])))
                if norm_text in lesson_wide_nodes:
                    bucket = lesson_wide_nodes[norm_text]
                    for idx, candidate in enumerate(bucket):
                        if candidate is node:
                            bucket.pop(idx)
                            if not bucket:
                                lesson_wide_nodes.pop(norm_text, None)
                            break

                if norm_text in scoped_nodes:
                    bucket = scoped_nodes[norm_text]
                    for idx, candidate in enumerate(bucket):
                        if candidate is node:
                            bucket.pop(idx)
                            if not bucket:
                                scoped_nodes.pop(norm_text, None)
                            break

            def _try_maps(norm_key: str) -> dict | None:
                chosen, k = _pick_with_fallback(scoped_nodes, norm_key)
                if chosen:
                    result = _clone_node(chosen)
                    if chosen.get("kind") == "list_item":
                        result["kind"] = "list_item"
                    scoped_nodes[k].remove(chosen)
                    if not scoped_nodes[k]:
                        scoped_nodes.pop(k, None)
                    _remove_from_other_maps(chosen)
                    return result
                chosen, k = _pick_with_fallback(lesson_wide_nodes, norm_key)
                if chosen:
                    result = _clone_node(chosen)
                    if chosen.get("kind") == "list_item":
                        result["kind"] = "list_item"
                    lesson_wide_nodes[k].remove(chosen)
                    if not lesson_wide_nodes[k]:
                        lesson_wide_nodes.pop(k, None)
                    _remove_from_other_maps(chosen)
                    return result
                return None

            pieces = re.split(r"(?:\u000b|\n)+", (raw or "").strip())
            for part in pieces:
                p = part.strip()
                if not p:
                    continue
                hit = _try_maps(_norm(p))
                if hit:
                    _trim_node_text(hit, p)
                    return hit

            norm_key = _norm(raw)
            hit = _try_maps(norm_key)
            if hit:
                _trim_node_text(hit, raw)
                return hit

            m = TH_RX.search(raw or "")
            if m:
                left = (raw[: m.start()] or "").strip()
                right = (raw[m.start():] or "").strip()
                for piece in (left, right):
                    if piece:
                        hit = _try_maps(_norm(piece))
                        if hit:
                            _trim_node_text(hit, piece)
                            return hit
            return None

        def _synth_node(kind: str, text: str, is_bullet: bool = False) -> dict:
            return {
                "kind": "list_item" if is_bullet else kind,
                "level": None,
                "inlines": [{"text": text, "bold": False, "italic": False, "underline": False}],
                "indent": 0,
                "detection_indent": 0,
                "indent_level": 0,
                "indent_start_pts": 0,
                "indent_first_line_pts": 0,
                "indent_first_line_level": 0,
                "lesson_context": lesson_header_raw,
                "section_context": "PHRASES & VERBS",
            }

        def looks_like_header(chunk: str, style: str, piece_index: int) -> bool:
            """
            Treat as header if:
            - ends with [n], OR
            - (first piece only) text is ALL CAPS (ignoring Thai) and short/title-ish.
            """
            s = _strip_bullets_tabs(chunk)

            # 1) Explicit variant marker always wins
            if HEADER_TRAILING_VARIANT_RX.search(s):
                return True

            # Only the first split piece may be checked for ALL CAPS header
            if piece_index > 0:
                return False

            # Remove Thai for EN-only check
            ascii_only = TH_RX.sub("", s).strip()
            if not ascii_only:
                return False

            # Must have at least one A–Z, and NO lowercase letters
            if not re.search(r"[A-Z]", ascii_only):
                return False
            if re.search(r"[a-z]", ascii_only):
                return False

            # Token/length heuristics
            tokens = re.findall(r"[A-Z0-9'&]+", ascii_only)
            if not (1 <= len(tokens) <= 8):
                return False
            if len(ascii_only) > 50:
                return False

            return True

        # -------------------------- main loop --------------------------
        for raw_text, style in lines:
            if not raw_text:
                continue

            pieces = re.split(r"(?:\u000b|\n)+", raw_text)
            for i, piece in enumerate(pieces):
                text = (piece or "").strip()
                if not text:
                    continue

                if looks_like_header(text, style, i):
                    _flush()
                    current_phrase, current_phrase_th, current_variant = parse_phrase_and_variant(text)
                    node_buffer = []
                    text_buffer = []
                    continue

                # normal line → try to attach real node
                text_buffer.append(text)
                node = _take_node(text)
                if node is not None:
                    if _is_bullet_node(node):
                        node["kind"] = "list_item"
                    node_buffer.append(node)
                else:
                    is_bullet = False
                    norm_text = _norm(text)

                    for node_list in scoped_nodes.values():
                        for n in node_list:
                            node_text = "".join(s.get("text", "") for s in n.get("inlines", []))
                            if _norm(node_text) == norm_text and _is_bullet_node(n):
                                is_bullet = True
                                break
                        if is_bullet:
                            break

                    if not is_bullet:
                        for node_list in lesson_wide_nodes.values():
                            for n in node_list:
                                node_text = "".join(s.get("text", "") for s in n.get("inlines", []))
                                if _norm(node_text) == norm_text and _is_bullet_node(n):
                                    is_bullet = True
                                    break
                            if is_bullet:
                                break

                    node_buffer.append(_synth_node("paragraph", text, is_bullet))

        _flush()
        return items




    ################################################################################
    def build_lesson_from_sections(
        self,
        lesson_sections: list[tuple[str, list[tuple[str, str]]]],
        stage: str,
        doc_json,
        lang: str = 'en'
    ) -> dict:
        # ---- header & bucket bookkeeping -----------------------------------
        lesson_header, header_lines = lesson_sections[0]
        lesson_header_raw = lesson_header
        lesson_info, _   = self.parse_lesson_header(lesson_header, stage)
        lesson           = lesson_info.copy()
        lesson["focus"]      = ""
        lesson["backstory"]  = ""

        if lang == "th":
            title_text = (lesson.get("title") or "").strip()
            rx = globals().get("TH_RX") if "TH_RX" in globals() else re.compile(r"[\u0E00-\u0E7F]")
            match = rx.search(title_text)
            if match:
                lesson["title"] = title_text[match.start():].strip()


        header_img = None
        for raw_text, _style in (header_lines or []):
            text = (raw_text or "").strip()
            if not text:
                continue
            match = re.match(r"\[\s*header_img\s*:\s*([^\]]+)\]", text, re.IGNORECASE)
            if match:
                header_img = match.group(1).strip()
                break
        if header_img:
            lesson["header_img"] = header_img

        # Add these right after the header parse:
        LKEY  = _lesson_key(lesson_header_raw)
        LCTXN = _norm_header_str(lesson_header_raw)

        def _same_lesson(n: dict) -> bool:
            nk = n.get("lesson_key") or _lesson_key(n.get("lesson_context"))
            if LKEY and nk and nk != LKEY:
                return False
            if LKEY and not nk:
                lc = n.get("lesson_context")
                if lc and _norm_header_str(lc) != LCTXN:
                    return False
            return True

        transcript_lines:      list[str] = []
        comp_lines:            list[str] = []
        practice_lines:        list[str] = []
        tags_lines:            list[str] = []
        pinned_comment_lines:  list[str] = []
        other_sections:        list[dict] = []
        embedded_practice_lines: list[str] = []

        tagged_nodes = tag_nodes_with_sections(doc_json)
        table_nodes = {n["id"]: n for n in tagged_nodes
            if n.get("kind") == "table"
            and _same_lesson(n)
        }

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
                for raw_text, _style in lines:
                    text = (raw_text or "").replace("\u000b", "\n")
                    for piece in text.splitlines():
                        piece = piece.strip()
                        if piece:
                            transcript_lines.append(piece)
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
                items = self.parse_phrases_verbs(lines, tagged_nodes, lesson_header_raw, lang=lang)
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
                "UNDERSTAND", "EXTRA TIPS", "CULTURE NOTE", "COMMON MISTAKES", "PREPARE"
            }
            if norm_header in RICH_AUDIO_HEADERS:
                # Add directive regex for quick practice harvesting
                directive_re = re.compile(
                    r"^(TYPE:|TITLE:|PROMPT:|PARAGRAPH:|ITEM:|QUESTION:|STEM:|TEXT:|OPTIONS:|ANSWER:|CORRECT:|KEYWORDS:|INPUTS:)",
                    re.I
                )
                qp_chunk, keep_lines = [], []

                node_list: list[dict] = []
                # Track tables added to prevent duplicates within this section
                table_ids_added = set()
                last_qp_directive: str | None = None

                for text_line, style in lines:
                    line_stripped = (text_line or "").strip()
                    upper = line_stripped.upper()

                    # keep the visible header
                    if upper.startswith("QUICK PRACTICE"):
                        keep_lines.append((text_line, style))
                        continue

                    # ---- start of a new directive block ----
                    directive_match = directive_re.match(line_stripped)
                    if directive_match:
                        directive_name = directive_match.group(1).rstrip(":").upper()
                        if directive_name == "TYPE":
                            if qp_chunk:                            # flush the previous block
                                embedded_practice_lines.extend(qp_chunk)
                                qp_chunk = []
                                last_qp_directive = None
                        qp_chunk.append(line_stripped)
                        last_qp_directive = directive_name
                        continue

                    # ---- continuation lines for directives ----
                    if qp_chunk:
                        if not line_stripped:
                            qp_chunk.append(line_stripped)
                            continue

                        # Check for section headers FIRST, before checking for Thai
                        if len(line_stripped) < 100:
                            upper_check = line_stripped.upper()
                            # Remove Thai to check if English part is all caps
                            en_only = TH.sub('', line_stripped).strip()
                            if en_only and upper_check[:len(en_only)] == en_only and not re.match(r'^[A-Z]\.\s', line_stripped):
                                # This is a header, flush and continue
                                embedded_practice_lines.extend(qp_chunk)
                                qp_chunk = []
                                last_qp_directive = None
                                keep_lines.append((text_line, style))
                                continue

                        if TH.search(line_stripped):
                            qp_chunk.append(line_stripped)
                            continue

                        if last_qp_directive in {"TITLE", "PROMPT", "PARAGRAPH", "TEXT", "STEM"}:
                            qp_chunk.append(line_stripped)
                        continue

                    # ---- normal prose (including table placeholders) ----
                    if qp_chunk:                               # flush finished block
                        print(f"DEBUG: Flushing qp_chunk (normal prose) with {len(qp_chunk)} lines")
                        embedded_practice_lines.extend(qp_chunk)
                        qp_chunk = []
                        last_qp_directive = None
                    keep_lines.append((text_line, style))

                # flush any trailing block
                if qp_chunk:
                    print(f"DEBUG: Flushing trailing qp_chunk with {len(qp_chunk)} lines")
                    embedded_practice_lines.extend(qp_chunk)
                    last_qp_directive = None

                # keep_lines now holds the real prose + table placeholders in correct order
                lines = keep_lines

                section_key = SECTION_TYPE_MAP.get(norm_header, norm_header.lower())

                # Create a mapping of text to nodes for this lesson and section
                text_to_nodes = {}
                orig_kind_by_text = {}
                for n in tagged_nodes:
                    if not _same_lesson(n):
                        continue
                    if "inlines" in n:
                        plain = "".join(s["text"] for s in n["inlines"])
                        k = _norm2(plain)
                        if not k:
                            continue
                        text_to_nodes.setdefault(k, []).append(n)
                        # remember the strongest original kind we’ve seen for this text
                        if n.get("kind") in {"list_item", "numbered_item"}:
                            orig_kind_by_text[k] = n["kind"]

                # Process lines in order, preserving the original sequence
                quick_practice_titles = [
                    ex["title"]
                    for ex in self.parse_practice(embedded_practice_lines + practice_lines)
                    if (ex.get("title", "").lower().startswith("quick practice"))
                ]
                quick_practice_idx = 0

                skip_alt_indexes: set[int] = set()
                line_idx = 0
                while line_idx < len(lines):
                    if line_idx in skip_alt_indexes:
                        line_idx += 1
                        continue

                    text_line, style = lines[line_idx]
                    text_line = text_line.strip()
                    if not text_line:
                        # Preserve blank lines as spacer nodes to control vertical gaps in the renderer
                        node_list.append({
                            "kind": "spacer",
                            "level": None,
                            "inlines": [],
                            "indent": 0,
                            "lesson_context": lesson_header_raw,
                            "section_context": norm_header
                        })
                        line_idx += 1
                        continue

                    # Inline image detection
                    img_match = IMG_TAG_RE.search(text_line)
                    if img_match:
                        image_key = (img_match.group(1) or "").strip()
                        if image_key:
                            alt_text = None
                            lookahead = line_idx + 1
                            while lookahead < len(lines):
                                next_text = (lines[lookahead][0] or "").strip()
                                if not next_text:
                                    lookahead += 1
                                    continue
                                alt_match = ALT_TEXT_RE.match(next_text)
                                if alt_match:
                                    alt_text = (alt_match.group(1) or "").strip()
                                    skip_alt_indexes.add(lookahead)
                                break

                            node_list.append({
                                "kind": "image",
                                "image_key": image_key,
                                "alt_text": alt_text,
                                "lesson_context": lesson_header_raw,
                                "section_context": norm_header
                            })
                        line_idx += 1
                        continue

                    # ── Handle table placeholders in their correct position ──
                    if text_line.upper().startswith("TABLE-") and text_line.endswith(":"):
                        table_id = text_line.lower().rstrip(":")
                        tbl = table_nodes.get(table_id)
                        if tbl and table_id not in table_ids_added:
                            # Create a copy to avoid modifying the original
                            table_copy = tbl.copy()
                            node_list.append(table_copy)
                            table_ids_added.add(table_id)
                        line_idx += 1
                        continue

                    # Find matching nodes for this text
                    norm_key = _norm2(text_line)
                    matching_nodes = text_to_nodes.get(norm_key, [])

                    # --- PATCH: Replace Quick Practice heading with full title ---
                    is_quick_practice_heading = (
                        any(word in text_line.lower() for word in ["quick practice"]) and is_subheader(text_line, style)
                    )
                    if is_quick_practice_heading and quick_practice_idx < len(quick_practice_titles):
                        # Replace heading node's text with the full title
                        full_title = quick_practice_titles[quick_practice_idx]
                        quick_practice_idx += 1
                        # If matching node exists, update its inlines text
                        if matching_nodes:
                            node = matching_nodes[0].copy()  # Create a copy
                            for inline in node["inlines"]:
                                inline["text"] = full_title
                            node_list.append(node)
                            matching_nodes.remove(matching_nodes[0])  # Remove from original list
                        else:
                            # Synthetic heading node
                            synthetic_node = {
                                "kind": "heading",
                                "level": None,
                                "inlines": [{"text": full_title, "bold": False, "italic": False, "underline": False}],
                                "indent": 0,
                                "lesson_context": lesson_header_raw,
                                "section_context": norm_header
                            }
                            node_list.append(synthetic_node)
                        line_idx += 1
                        continue

                    if matching_nodes:
                        # Prefer nodes explicitly tagged for this audio section, else same section, else first
                        audio_nodes   = [n for n in matching_nodes if n.get("audio_section") == section_key]
                        section_nodes = [n for n in matching_nodes if n.get("section_context") == norm_header]

                        chosen_node = audio_nodes[0] if audio_nodes else (section_nodes[0] if section_nodes else matching_nodes[0])

                        node_copy = chosen_node.copy()
                        if "inlines" in node_copy:
                            node_copy["inlines"] = [inline.copy() for inline in node_copy["inlines"]]
                        node_list.append(node_copy)

                        # consume it so the same node isn't reused
                        matching_nodes.remove(chosen_node)
                    else:
                        # --- Fallback: try a tiny fuzzy match in this lesson-wide map ---
                        best = None
                        best_key = None
                        best_score = 0.0
                        a = set(norm_key.split())
                        if a:
                            for k, bucket in text_to_nodes.items():
                                if not bucket:
                                    continue
                                b = set(k.split())
                                if not b:
                                    continue
                                score = len(a & b) / max(len(a), len(b))
                                if score > 0.6 and score > best_score:
                                    best = bucket[0]
                                    best_key = k
                                    best_score = score

                        if best is not None:
                            node_copy = best.copy()
                            if "inlines" in node_copy:
                                node_copy["inlines"] = [inline.copy() for inline in node_copy["inlines"]]
                            node_list.append(node_copy)
                            # consume it
                            text_to_nodes[best_key].remove(best)
                        else:
                            # Last resort: synthesize, but preserve bullets if we’ve ever seen this exact text as a list/numbered item in this lesson

                            synthetic_kind = "paragraph"
                            orig = orig_kind_by_text.get(norm_key)
                            # 1) Prefer original kind when Thai (bilingual lines often break matching)
                            if lang == 'th' and orig in {"list_item", "numbered_item"}:
                                synthetic_kind = orig
                            else:
                                parts = re.split(r"(?:\u000b|\n)+", text_line.strip())
                                part_kinds = [orig_kind_by_text.get(_norm2(p)) for p in parts if p.strip()]
                                if "numbered_item" in part_kinds:
                                    synthetic_kind = "numbered_item"  # <-- prefer numbered if seen
                                elif "list_item" in part_kinds:
                                    synthetic_kind = "list_item"
                                elif bool(re.match(r"^[•●◦○∙·]\s", text_line)):
                                    synthetic_kind = "list_item"

                                # 3) Last fallback: visible bullet glyphs only
                                if synthetic_kind == "paragraph":
                                    looks_bullety = bool(re.match(r"^[•●◦○∙·]\s", text_line))
                                    if looks_bullety:
                                        synthetic_kind = "list_item"

                            node_list.append({
                                "kind": synthetic_kind,
                                "level": None,
                                "inlines": [{"text": text_line, "bold": False, "italic": False, "underline": False}],
                                "indent": 0,
                                "detection_indent": 0,
                                "indent_level": 0,
                                "indent_start_pts": 0,
                                "indent_first_line_pts": 0,
                                "indent_first_line_level": 0,
                                "lesson_context": lesson_header_raw,
                                "section_context": norm_header
                            })

                    # If the current node we just appended is a paragraph immediately after an audio list_item,
                    # and it "looks attached" (same indent OR italic), merge its inlines into the previous node
                    # so that only one list_item/audio button renders (mini-conversation style).
                    if node_list:
                        curr = node_list[-1]
                        prev = node_list[-2] if len(node_list) >= 2 else None
                        if (
                            curr.get("kind") == "paragraph"
                            and prev
                            and prev.get("kind") == "list_item"
                            and prev.get("audio_key")
                        ):
                            para_text = "".join((inl.get("text", "") or "") for inl in curr.get("inlines", [])).strip()
                            looks_like_speaker = bool(re.match(r"^[^:\n]{1,50}:\s+", para_text))
                            same_indent = curr.get("indent") == prev.get("indent")
                            has_italic = any((inl.get("italic") for inl in curr.get("inlines", [])))
                            has_text = any((inl.get("text", "").strip() for inl in curr.get("inlines", [])))
                            if has_text and (same_indent or has_italic or looks_like_speaker):
                                node_list.pop()  # remove the paragraph node
                                prev_inlines = prev.get("inlines", [])
                                if prev_inlines:
                                    prev_inlines.append({"text": "\n", "bold": False, "italic": False, "underline": False})
                                prev_inlines.extend(curr.get("inlines", []))
                                prev["inlines"] = prev_inlines

                    line_idx += 1

                # fallback plain-text (Markdown) version
                body_parts = []
                for t, style in lines:
                    stripped = (t or "").strip()
                    if not stripped:
                        body_parts.append(t)
                        continue
                    if IMG_TAG_RE.search(stripped):
                        continue
                    if ALT_TEXT_RE.match(stripped):
                        continue
                    body_parts.append(
                        f"## {t.strip()}" if is_subheader(t, style) else t
                    )

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
        parsed_transcript = self.parse_conversation_from_lines(transcript_lines)
        if lang == 'th':
            parsed_transcript = pair_transcript_bilingual(parsed_transcript)
            for sec in other_sections:
                if "content_jsonb" in sec and isinstance(sec["content_jsonb"], list):
                    sec["content_jsonb"] = bilingualize_headers_th(sec["content_jsonb"])

        # --------------------------------------------------------------------
        lesson_obj = {
            "lesson":                  lesson,
            "transcript":              parsed_transcript,
            "comprehension_questions": self.parse_comprehension(comp_lines, lang=lang),
            "practice_exercises":      self.parse_practice(embedded_practice_lines + practice_lines, lang=lang),
            "sections":                other_sections,
            "tags":                    self.parse_tags(tags_lines),
        }

        practice_titles = [
            (idx, exercise.get("title", ""), exercise.get("title_th"))
            for idx, exercise in enumerate(lesson_obj["practice_exercises"])
            if isinstance(exercise.get("title"), str)
        ]

        def _inject_quick_practice_headings():
            quick_entries = [
                (title, title_th, p_idx)
                for p_idx, title, title_th in practice_titles
                if isinstance(title, str) and title.upper().startswith("QUICK PRACTICE")
            ]
            if not quick_entries:
                return

            for section in lesson_obj["sections"]:
                if section.get("type") != "understand":
                    continue

                for jsonb_key in ["content_jsonb", "content_jsonb_th"]:
                    if jsonb_key not in section:
                        continue

                    content_nodes = section.get(jsonb_key, [])
                    if not content_nodes:
                        continue

                    context_source = content_nodes[0] if content_nodes else {}

                    existing_labels = set()
                    for node in content_nodes:
                        node_text = node.get("text", {})
                        if isinstance(node_text, dict):
                            if node_text.get("en"):
                                existing_labels.add(node_text["en"].strip())
                            if node_text.get("th"):
                                existing_labels.add(node_text["th"].strip())
                        inline_text = "".join(run.get("text", "") or "" for run in node.get("inlines", [])).strip()
                        if inline_text:
                            existing_labels.add(inline_text)

                    anchor_idx = None
                    for idx, node in enumerate(content_nodes):
                        node_text = node.get("text", {})
                        inline_text = "".join(run.get("text", "") or "" for run in node.get("inlines", [])).strip()
                        en_label = (node_text.get("en") or inline_text or "").upper()
                        th_label = (node_text.get("th") or "").strip()
                        if "MAKING QUESTIONS" in en_label or ("การสร้างประโยคคำถาม" in th_label):
                            anchor_idx = idx
                            break

                    numeric_entries = []
                    trailing_entries = []
                    for title, title_th, p_idx in quick_entries:
                        if re.match(r"^QUICK PRACTICE\s*\d+", (title or "").upper()):
                            numeric_entries.append((title, title_th, p_idx))
                        else:
                            trailing_entries.append((title, title_th, p_idx))

                    insert_idx = anchor_idx if anchor_idx is not None else len(content_nodes)

                    def _add_heading(title_en: str, title_th: str | None):
                        nonlocal insert_idx
                        label_en = (title_en or "").strip()
                        label_th = (title_th or "").strip() if title_th else ""
                        display_label = label_en or label_th

                        if not display_label:
                            return

                        if display_label in existing_labels:
                            return
                        if label_en and label_en in existing_labels:
                            return
                        if label_th and label_th in existing_labels:
                            return

                        heading_node = {
                            "kind": "heading",
                            "level": 3,
                            "inlines": [{
                                "text": display_label,
                                "bold": False,
                                "italic": False,
                                "underline": False,
                                "link": None,
                            }],
                            "lesson_context": context_source.get("lesson_context") if context_source else None,
                            "lesson_key": context_source.get("lesson_key") if context_source else None,
                            "lesson_context_norm": context_source.get("lesson_context_norm") if context_source else None,
                            "lesson_context_en": context_source.get("lesson_context_en") if context_source else None,
                            "lesson_context_th": context_source.get("lesson_context_th") if context_source else None,
                            "section_context": "UNDERSTAND",
                            "text": {
                                "en": label_en or display_label,
                                "th": label_th or None,
                            }
                        }

                        content_nodes.insert(insert_idx, heading_node)
                        insert_idx += 1
                        existing_labels.add(display_label)
                        if label_en:
                            existing_labels.add(label_en)
                        if label_th:
                            existing_labels.add(label_th)

                    for title, title_th, p_idx in numeric_entries:
                        practice = lesson_obj["practice_exercises"][p_idx]
                        effective_th = title_th or practice.get("title_th")
                        _add_heading(title, effective_th)

                    for title, title_th, p_idx in trailing_entries:
                        practice = lesson_obj["practice_exercises"][p_idx]
                        effective_th = title_th or practice.get("title_th")
                        insert_position = len(content_nodes)
                        insert_idx = insert_position
                        _add_heading(title, effective_th)

                    # CRITICAL: Write the modified list back to the section!
                    section[jsonb_key] = content_nodes

        _inject_quick_practice_headings()

        def _populate_quick_practice_items_th():
            if lang != 'th':
                return

            understand_section = next(
                (sec for sec in lesson_obj["sections"]
                 if sec.get("type") == "understand" and isinstance(sec.get("content_jsonb"), list)),
                None
            )
            if not understand_section:
                return

            content_nodes = understand_section["content_jsonb"]
            heading_spans = []
            for idx, node in enumerate(content_nodes):
                if node.get("kind") != "heading":
                    continue
                text_data = node.get("text", {}) or {}
                label_en = (text_data.get("en") or "").strip()
                if label_en.upper().startswith("QUICK PRACTICE"):
                    heading_spans.append(idx)

            if not heading_spans:
                return

            heading_spans.append(len(content_nodes))

            practice_map = {
                (exercise.get("title") or "").strip().upper(): exercise
                for exercise in lesson_obj["practice_exercises"]
                if (exercise.get("title") or "").strip().upper().startswith("QUICK PRACTICE")
            }

            for span_index in range(len(heading_spans) - 1):
                start_idx = heading_spans[span_index]
                end_idx = heading_spans[span_index + 1]
                heading_node = content_nodes[start_idx]
                heading_text = (heading_node.get("text", {}) or {}).get("en") or ""
                exercise_key = heading_text.strip().upper()
                exercise = practice_map.get(exercise_key)
                if not exercise:
                    continue
                if exercise.get("items_th"):
                    continue

                candidate_nodes = content_nodes[start_idx + 1:end_idx]
                thai_lines = []
                for node in candidate_nodes:
                    if node.get("kind") == "heading":
                        break
                    inline_text = "".join(run.get("text", "") for run in node.get("inlines", [])).strip()
                    if not inline_text:
                        continue
                    for chunk in re.split(r"(?:\r?\n)+", inline_text):
                        chunk = chunk.strip()
                        if not chunk:
                            continue
                        en_part, th_part = split_en_th(chunk)
                        if th_part:
                            thai_lines.append(th_part)
                        elif TH.search(chunk) and not EN.search(chunk):
                            thai_lines.append(chunk)

                if not thai_lines:
                    continue

                items_th = []
                for idx_item, item in enumerate(exercise.get("items", [])):
                    if idx_item >= len(thai_lines):
                        break
                    th_text = thai_lines[idx_item]
                    entry = {
                        "number": item.get("number"),
                        "text": th_text,
                    }
                    if "answer" in item:
                        entry["answer"] = item["answer"]
                    if "keywords" in item:
                        entry["keywords"] = item["keywords"]
                    if "inputs" in item:
                        entry["inputs"] = item["inputs"]
                    items_th.append(entry)

                if items_th:
                    exercise["items_th"] = items_th

        _populate_quick_practice_items_th()

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

    def parse_comprehension(self, lines: list[str], lang: str = "en") -> list[dict]:
        """
        Keeps Thai translations on the NEXT line(s) for each option.
        Example option output (single string with newline):
        "A. He's excited.\nเขาตื่นเต้น"
        """
        questions: list[dict] = []
        cur_q: dict | None = None
        options: list[str] = []
        answer_key: list[str] = []

        # When lang == "th", we collect an EN option, then append 1+ TH lines
        pending_en: str | None = None
        pending_th: list[str] = []

        def flush_pending():
            nonlocal pending_en, pending_th, options
            if pending_en is not None:
                if pending_th:
                    options.append(pending_en + "\n" + "\n".join(pending_th))
                else:
                    options.append(pending_en)
            pending_en = None
            pending_th = []

        def is_thai_continuation(s: str) -> bool:
            # Thai chars, and not a new option, not an answer key, not a new question
            return (
                _has_th(s)
                and not OPTION_RE.match(s)
                and not ANSWER_KEY_RE.match(s)
                and not QUESTION_NUM_RE.match(s)
            )

        for raw in (lines or []):
            for piece in (raw or "").splitlines():
                line = piece.strip()
                if not line or line.lower() in {"prompt", "options"}:
                    continue

                # New question
                m_q = QUESTION_NUM_RE.match(line)
                if m_q:
                    flush_pending()
                    if cur_q:
                        cur_q["options"] = options
                        cur_q["answer_key"] = answer_key
                        questions.append(cur_q)
                    cur_q = {
                        "sort_order": len(questions) + 1,
                        "prompt": re.sub(r"\bOptions\b$", "", m_q.group(1)).strip(),
                    }
                    options, answer_key = [], []
                    continue

                # Answer key
                m_ans = ANSWER_KEY_RE.match(line)
                if m_ans:
                    flush_pending()
                    answer_key = [x.strip() for x in re.split(r"[,\s/]+", m_ans.group(1)) if x.strip()]
                    continue

                # Option line (A./B./C.)
                if OPTION_RE.match(line):
                    flush_pending()
                    if lang == "th" and not _has_th(line):
                        # EN only — wait for Thai continuation lines
                        pending_en = line
                        pending_th = []
                    else:
                        options.append(line)
                    continue

                # Thai continuation lines after an English option
                if lang == "th" and pending_en and is_thai_continuation(line):
                    pending_th.append(line)
                    continue

                # Extra text before any options → belongs to prompt
                if cur_q and not options and not pending_en:
                    cur_q["prompt"] = (cur_q["prompt"] + " " + line).strip()

        # Final flush
        flush_pending()
        if cur_q:
            cur_q["options"] = options
            cur_q["answer_key"] = answer_key
            questions.append(cur_q)

        return questions


    def parse_practice(self, lines: List[str], lang: str = 'en') -> List[Dict]:
        """
        Convert the flat "directive" block into structured exercises.

        Markers handled:
        TYPE: <multiple_choice | open | fill_blank | ...>
        TITLE: <exercise title>
        PROMPT: <prompt shown above the items>
        PARAGRAPH: <optional explanatory paragraph>
        QUESTION: <n> or ITEM: <n>
        TEXT: <stem>
        STEM: <stem> (alternative to TEXT)
        OPTIONS:                # the very next lines are A. / B. / …
        ANSWER: <letter(s)>     # for MC or fill_blank
        KEYWORDS: <kw list>     # for open items
        PINNED COMMENT          # everything after this goes into a pinned_comment string
        """
        import re
        exercises: List[Dict] = []
        cur_ex: Dict | None = None  # current exercise being built
        cur_items: List[Dict] = []
        collecting_opts = False
        collecting_text = False  # New flag for multi-line text collection
        collecting_paragraph = False  # New flag for multi-line paragraph collection
        item_complete = False  # Track completion of current item

        def normalize_inputs(value) -> int:
            """Ensure inputs is a positive int, defaulting to 1."""
            try:
                n = int(str(value).strip())
                return n if n > 0 else 1
            except (TypeError, ValueError):
                return 1

        def append_text(target: dict, key: str, value: str, newline: bool = False):
            if not value:
                return
            value = value.strip()
            if not value:
                return
            existing = target.get(key)
            if existing:
                if newline:
                    sep = "\n" if not existing.endswith("\n") else ""
                    target[key] = f"{existing}{sep}{value}"
                else:
                    sep = " " if not existing.endswith(" ") else ""
                    target[key] = f"{existing}{sep}{value}"
            else:
                target[key] = value

        def set_bilingual(target: dict, key_en: str, key_th: str, value: str):
            value = (value or "").strip()
            if not value:
                target[key_en] = ""
                return
            en_part, th_part = split_en_th(value)
            target[key_en] = en_part if en_part is not None else value
            if th_part:
                target[key_th] = th_part

        def append_bilingual(target: dict, key_en: str, key_th: str, value: str, newline: bool = False):
            value = (value or "").strip()
            if not value:
                return
            en_part, th_part = split_en_th(value)
            if en_part:
                append_text(target, key_en, en_part, newline=newline)
            elif not th_part:
                append_text(target, key_en, value, newline=newline)
            if th_part:
                append_text(target, key_th, th_part, newline=newline)

        def flush_exercise():
            nonlocal cur_ex, cur_items, item_complete
            if cur_ex is not None:
                if cur_ex.get("kind") in {"open", "open_ended"}:
                    for item in cur_items:
                        if "inputs" not in item or item["inputs"] in (None, ""):
                            item["inputs"] = 1
                        else:
                            item["inputs"] = normalize_inputs(item["inputs"])
                cur_ex["items"] = cur_items
                items_th_collection = []
                for item in cur_items:
                    th_text = item.get("text_th")
                    if th_text:
                        th_entry = {}
                        if "number" in item:
                            th_entry["number"] = item["number"]
                        th_entry["text"] = th_text
                        for key in ("answer", "keywords", "inputs", "options", "correct"):
                            if key in item and item[key] not in (None, ""):
                                th_entry[key] = item[key]
                        items_th_collection.append(th_entry)
                cur_ex["items_th"] = items_th_collection
                exercises.append(cur_ex)
            cur_ex, cur_items = None, []
            item_complete = False

        def new_exercise(kind: str):
            flush_exercise()
            return {
                "kind": kind,
                "title": "",
                "prompt": "",
                "paragraph": "",
                "items": [],
                "sort_order": len(exercises) + 1,
                "title_th": None,
                "prompt_th": "",
                "paragraph_th": "",
                "items_th": [],
            }

        # Flatten all lines into a single string and iterate line by line.
        practice_text = "\n".join(lines)
        for line in practice_text.splitlines():
            original_line = line  # Keep original for text collection
            line = line.strip()
            upper_line = line.upper()

            if not line:
                # If we're collecting text or paragraph, preserve empty lines as line breaks
                if collecting_text and cur_items:
                    current_text = cur_items[-1].get("text", "")
                    if current_text and not current_text.endswith("\n"):
                        cur_items[-1]["text"] = current_text + "\n"
                elif collecting_paragraph and cur_ex:
                    current_paragraph = cur_ex.get("paragraph", "")
                    if current_paragraph and not current_paragraph.endswith("\n"):
                        cur_ex["paragraph"] = current_paragraph + "\n"
                continue

            # Check for block-level directives
            m_type = re.match(r'^TYPE:\s*(\w+)', line, re.I)
            if m_type:
                cur_ex = new_exercise(m_type.group(1).lower())
                collecting_text = False
                collecting_opts = False
                continue

            if cur_ex is None:
                # Skip lines before the first TYPE:
                continue

            if upper_line.startswith("TITLE:"):
                value = line.split(":", 1)[1].strip()
                set_bilingual(cur_ex, "title", "title_th", value)
                collecting_text = False
                collecting_paragraph = False
                continue
            if upper_line.startswith("PROMPT:"):
                value = line.split(":", 1)[1].strip()
                set_bilingual(cur_ex, "prompt", "prompt_th", value)
                collecting_text = False
                collecting_paragraph = False
                continue
            if upper_line.startswith("PARAGRAPH:"):
                # Get the content after the colon
                content = line.split(":", 1)[1].strip() if ":" in line else ""

                if content:
                    set_bilingual(cur_ex, "paragraph", "paragraph_th", content)
                    collecting_paragraph = False
                else:
                    # Empty PARAGRAPH: line, start collecting multi-line paragraph
                    cur_ex["paragraph"] = ""
                    cur_ex["paragraph_th"] = cur_ex.get("paragraph_th", "")
                    collecting_paragraph = True
                collecting_text = False
                continue

            # Item-level directives - handle both QUESTION: and ITEM:
            if upper_line.startswith(("QUESTION:", "ITEM:")):
                number = line.split(":", 1)[1].strip()
                # Create a new question/item entry.
                cur_items.append({"number": number})
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                item_complete = False
                continue

            # --- TEXT/STEM for any exercise type ---
            if upper_line.startswith(("TEXT:", "STEM:")):
                if not cur_items:
                    cur_items.append({})
                    item_complete = False

                # Get the content after the colon
                content = line.split(":", 1)[1].strip() if ":" in line else ""

                if content:
                    # There's content on the same line (English text)
                    cur_items[-1]["text"] = content
                    cur_items[-1]["text_th"] = ""  # Initialize empty Thai
                    collecting_text = True  # Keep collecting for Thai on next line
                else:
                    # Empty TEXT: line, start collecting multi-line
                    cur_items[-1]["text"] = ""
                    cur_items[-1]["text_th"] = ""
                    collecting_text = True
                collecting_opts = False
                continue

            if upper_line.startswith("OPTIONS:"):
                collecting_opts = True
                collecting_text = False
                collecting_paragraph = False
                # Ensure the current item has an options list.
                if not cur_items:
                    cur_items.append({})
                    item_complete = False
                cur_items[-1]["options"] = []
                continue

            if upper_line.startswith("INPUTS:"):
                if cur_items and cur_ex and cur_ex.get("kind") in {"open", "open_ended"}:
                    value = line.split(":", 1)[1].strip() if ":" in line else ""
                    cur_items[-1]["inputs"] = value or 1
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            if upper_line.startswith("CORRECT:"):
                # Handle CORRECT: directive for sentence_transform exercises
                if not cur_items:
                    cur_items.append({})
                    item_complete = False
                correct_value = line.split(":", 1)[1].strip()
                # Build the text field in the expected format
                cur_items[-1]["correct"] = correct_value
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            if upper_line.startswith("ANSWER:"):
                # Only update if there's an existing item.
                if not cur_items:
                    cur_items.append({})
                    item_complete = False
                cur_items[-1]["answer"] = line.split(":", 1)[1].strip()
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                item_complete = True
                continue

            if upper_line.startswith("KEYWORDS:") or upper_line.startswith("PINNED COMMENT"):
                kw = line.split(":", 1)[1].strip() if ":" in line else ""
                if kw:
                    if not cur_items:
                        cur_items.append({})
                        item_complete = False
                    cur_items[-1]["keywords"] = kw
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            # Item bullet lines (e.g., "A. option text")
            m_opt = re.match(r'^\s*([A-Z])\.\s*(.+)$', line)
            if collecting_opts and m_opt:
                if not cur_items:
                    cur_items.append({})
                cur_items[-1].setdefault("options", []).append(line)
                continue

            # Multi-line text collection
            if collecting_text and cur_items:
                stripped = line.strip()
                if not stripped:
                    continue

                # Check if this is a directive line
                directive_re_check = re.compile(
                    r'^\s*(TYPE:|TITLE:|PROMPT:|PARAGRAPH:|ITEM:|QUESTION:|TEXT:|STEM:|CORRECT:|'
                    r'ANSWER:|OPTIONS:|KEYWORDS:|INPUTS:)',
                    re.I
                )
                if directive_re_check.match(upper_line):
                    collecting_text = False
                    # Don't continue - let it process this directive
                else:
                    # This is a continuation line
                    # If we already have English text but no Thai, this is the Thai line
                    if cur_items[-1].get("text") and not cur_items[-1].get("text_th"):
                        cur_items[-1]["text_th"] = stripped
                        collecting_text = False  # Done collecting
                    else:
                        # Otherwise append to English text
                        if cur_items[-1].get("text"):
                            cur_items[-1]["text"] = cur_items[-1]["text"] + " " + stripped
                        else:
                            cur_items[-1]["text"] = stripped
                    continue

            # Multi-line paragraph collection
            if collecting_paragraph and cur_ex:
                append_bilingual(cur_ex, "paragraph", "paragraph_th", original_line, newline=True)
                continue

            # Fallback: if not collecting options, text, or paragraph and we have items, append to current item's text
            if cur_items and not collecting_opts and not collecting_text and not collecting_paragraph and not item_complete:
                append_bilingual(cur_items[-1], "text", "text_th", original_line, newline=True)

        flush_exercise()

        def extract_media_fields(text: str):
            if not isinstance(text, str):
                return text, None, None, None

            image_key = None
            audio_key = None

            def _strip_img(match):
                nonlocal image_key
                if image_key is None:
                    image_key = (match.group(1) or "").strip()
                return ""

            def _strip_audio(match):
                nonlocal audio_key
                if audio_key is None:
                    audio_key = (match.group(1) or "").strip()
                return ""

            cleaned = IMG_TAG_RE.sub(_strip_img, text)
            cleaned = AUDIO_TAG_RE.sub(_strip_audio, cleaned)
            alt_text = None
            alt_match = ALT_TEXT_RE.search(cleaned)
            if alt_match:
                alt_text = (alt_match.group(1) or "").strip()
                cleaned = cleaned[:alt_match.start()].rstrip()

            cleaned = cleaned.strip()
            return cleaned, image_key, alt_text, audio_key

        for exercise in exercises:
            for item in exercise.get("items", []):
                text_value = item.get("text")
                cleaned_text, image_key, alt_text, audio_key = extract_media_fields(text_value)
                if image_key:
                    item["image_key"] = image_key
                if alt_text:
                    item["alt_text"] = alt_text
                if audio_key:
                    item["audio_key"] = audio_key
                if isinstance(cleaned_text, str):
                    item["text"] = cleaned_text
                th_text_value = item.get("text_th")
                if isinstance(th_text_value, str):
                    cleaned_th, _, _, _ = extract_media_fields(th_text_value)
                    item["text_th"] = cleaned_th

            if exercise.get("items_th") is None:
                exercise["items_th"] = []

            if exercise.get("items_th"):
                for idx, item_th in enumerate(exercise["items_th"]):
                    if idx < len(exercise.get("items", [])):
                        src_item = exercise["items"][idx]
                        if src_item.get("audio_key") and "audio_key" not in item_th:
                            item_th["audio_key"] = src_item["audio_key"]
                        if src_item.get("image_key") and "image_key" not in item_th:
                            item_th["image_key"] = src_item["image_key"]
                        if src_item.get("alt_text") and "alt_text" not in item_th:
                            item_th["alt_text"] = src_item["alt_text"]
            else:
                exercise["items_th"] = []

            if exercise.get("prompt_th") is not None:
                exercise["prompt_th"] = exercise["prompt_th"].strip() or ""
            if exercise.get("paragraph_th") is not None:
                exercise["paragraph_th"] = exercise["paragraph_th"].strip()

        # Build items_th array from text_th fields in items
        for ex in exercises:
            if ex.get("items") and not ex.get("items_th"):
                items_th = []
                for item in ex["items"]:
                    if item.get("text_th"):
                        # Build Thai version of item
                        th_item = {}
                        if "number" in item:
                            th_item["number"] = item["number"]
                        th_item["text"] = item["text_th"]  # Thai text goes in "text" field
                        if "answer" in item:
                            th_item["answer"] = item["answer"]  # Answer stays same
                        if "image_key" in item:
                            th_item["image_key"] = item["image_key"]
                        if "audio_key" in item:
                            th_item["audio_key"] = item["audio_key"]
                        if "alt_text" in item:
                            th_item["alt_text"] = item["alt_text"]
                        items_th.append(th_item)

                if items_th:
                    ex["items_th"] = items_th

        return exercises



    def parse_tags(self, lines: List[str]) -> List[str]:
        """
        Parse tags as comma-separated phrases, preserving multi-word tags.
        """
        tags_text = " ".join(lines)
        return [tag.strip() for tag in tags_text.split(",") if tag.strip()]

    def convert_document(self, document_id: str, stage: str, lang: str = 'en') -> Union[Dict, List[Dict]]:
        logger.info(f"Converting document {document_id}")
        doc_json = fetch_doc(document_id)
        if not doc_json:
            logger.error("Failed to fetch document")
            return {}
        sections = extract_sections(doc_json)
        lessons = split_lessons_by_header(sections)

        # Build lessons_by_level for dynamic checkpoint ordering
        lessons_by_level = {}
        for lesson_sections in lessons:
            header = lesson_sections[0][0] if lesson_sections and lesson_sections[0] else None
            m = re.search(r'(?:LESSON|Lesson)\s+(\d+)\.(\d+)', header or "", re.I)
            if m:
                level = int(m.group(1))
                order = int(m.group(2))
                lessons_by_level.setdefault(level, []).append({"lesson_order": order})
        self.lessons_by_level = lessons_by_level

        results = []
        for lesson_sections in lessons:
            try:
                lesson_data = self.build_lesson_from_sections(lesson_sections, stage, doc_json, lang=lang)
                results.append(lesson_data)
            except Exception as e:
                logger.error(f"Error processing a lesson: {e}")
        return results if len(results) > 1 else (results[0] if results else [])


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
    parser.add_argument('--lang', choices=['en','th'], default='en', help='Language of this doc')
    args = parser.parse_args()

    try:
        docs_parser = GoogleDocsParser()
        raw_doc = fetch_doc(args.document_id)
        if args.raw_output:
            with open(args.raw_output, 'w', encoding='utf-8') as f:
                json.dump(raw_doc, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote raw document JSON to {args.raw_output}")
        result = docs_parser.convert_document(args.document_id, args.stage, lang=args.lang)
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

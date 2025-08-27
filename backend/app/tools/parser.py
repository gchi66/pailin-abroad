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

# ───────────────────────────── regex helpers
HEADING_RE = re.compile(r"^([A-Z][A-Z &''']+)(?::\s*(.*))?$", re.I)
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-!?$%#]{2,60}$")
QUESTION_NUM_RE = re.compile(r'^\s*\d+\.\s*(.+)$')
OPTION_RE = re.compile(r'^\s*([A-Z])\.\s*(.+)$')
ANSWER_KEY_RE = re.compile(r'^\s*Answer key\s*:?\s*(.*)$', re.IGNORECASE)
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
    # "EN (TH)" pattern
    m = re.match(r'^(.*?)\s*\(([\u0E00-\u0E7F].*?)\)\s*$', line)
    if m:
        en = m.group(1).strip() or None
        th = m.group(2).strip() or None
        return en, th
    # "EN … TH" pattern (first Thai char starts TH)
    idx = next((i for i, ch in enumerate(line) if TH.match(ch)), -1)
    if idx >= 0:
        en = line[:idx].strip() or None
        th = line[idx:].strip() or None
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
    out = []

    for n in nodes:
        # PATCH: Handle LESSON FOCUS specifically first
        if n.get("kind") == "paragraph":
            # Check if this paragraph is exactly "LESSON FOCUS"
            para_text = node_plain_text(n).strip()
            if para_text.upper() == FOCUS_EN:
                out.append({
                    "kind": "heading",
                    "level": 3,
                    "text": {"en": FOCUS_EN, "th": FOCUS_TH},
                    "lesson_context": n.get("lesson_context"),
                    "section_context": n.get("section_context"),
                })
                continue

        # PATCH: For existing headings, check if they're LESSON FOCUS and need Thai
        if n.get("kind") in {"heading", "header"}:
            # Check if this is a LESSON FOCUS heading that needs Thai translation
            if isinstance(n.get("text"), dict):
                text_en = (n["text"].get("en") or "").strip().upper()
                if text_en == FOCUS_EN and not n["text"].get("th"):
                    n = {**n, "text": {**n["text"], "th": FOCUS_TH}}
                    out.append(n)
                    continue

            # Your existing heading logic
            s = node_plain_text(n)
            en, th = split_en_th(s)
            if en or th:
                out.append({
                    "kind": "heading",
                    "level": n.get("level", default_level),
                    "text": {"en": en, "th": th}
                })
            else:
                out.append(n)
            continue

        # Your existing paragraph logic (fallback for bilingual headings)
        if n.get("kind") == "paragraph":
            s = node_plain_text(n)
            has_th = bool(TH.search(s))
            has_en = bool(re.search(r'[A-Za-z]', s))
            looks_like_title = has_en and s.strip().upper() == s.strip()  # ALL CAPS EN

            if has_th and (looks_like_title or n.get("is_bold_header")):
                en, th = split_en_th(s)
                if en or th:
                    out.append({
                        "kind": "heading",
                        "level": default_level,
                        "text": {"en": en, "th": th}
                    })
                    continue

        out.append(n)

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
            text = "".join(
                r.get("textRun", {}).get("content", "")
                for r in para.get("elements", [])
            ).replace("\u000b", "\n").strip()

            if not text:
                continue

            stripped = text.strip()
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
            para_nodes = list(paragraph_nodes({"body": {"content": [elem]}}))
            if not para_nodes:
                continue
            n = para_nodes[0]

            if n.kind == "heading":
                hdr = "".join(s.text for s in n.inlines).strip()
                up  = hdr.upper().rstrip(":")
                if LESSON_ID_RE.match(up) or up.startswith("CHECKPOINT"):
                    current_lesson  = hdr
                    current_section = None
                    seq_counter     = {h: 0 for h in AUDIO_SECTION_HEADERS}
                elif up in SECTION_ORDER:
                    current_section = up

            nd = dataclasses.asdict(n)
            if current_lesson:
                nd["lesson_context"] = current_lesson
            if current_section:
                nd["section_context"] = current_section

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
        lang: str = 'en'
    ) -> dict:
        # ---- header & bucket bookkeeping -----------------------------------
        lesson_header, _ = lesson_sections[0]
        lesson_header_raw = lesson_header
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
        embedded_practice_lines: list[str] = []

        tagged_nodes = tag_nodes_with_sections(doc_json)
        table_nodes = {n["id"]: n for n in tagged_nodes
            if n.get("kind") == "table"
            and n.get("lesson_context") == lesson_header_raw
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
                # Add directive regex for quick practice harvesting
                directive_re = re.compile(
                    r"^(TYPE:|TITLE:|PROMPT:|QUESTION:|STEM:|TEXT:|OPTIONS:|ANSWER:|CORRECT:|KEYWORDS:)",
                    re.I
                )
                qp_chunk, keep_lines = [], []

                node_list: list[dict] = []
                # Track tables added to prevent duplicates within this section
                table_ids_added = set()

                for text_line, style in lines:
                    upper = text_line.strip().upper()

                    # keep the visible header
                    if upper.startswith("QUICK PRACTICE"):
                        keep_lines.append((text_line, style))
                        continue

                    # ---- start of a new directive block ----
                    if upper.startswith("TYPE:"):
                        if qp_chunk:                            # flush the previous block
                            embedded_practice_lines.extend(qp_chunk)
                            qp_chunk = []
                        qp_chunk.append(text_line.strip())
                        continue

                    # ---- other directive lines ----
                    if directive_re.match(upper):
                        qp_chunk.append(text_line.strip())
                        continue

                    # ---- normal prose (including table placeholders) ----
                    if qp_chunk:                               # flush finished block
                        embedded_practice_lines.extend(qp_chunk)
                        qp_chunk = []
                    keep_lines.append((text_line, style))

                # flush any trailing block
                if qp_chunk:
                    embedded_practice_lines.extend(qp_chunk)

                # keep_lines now holds the real prose + table placeholders in correct order
                lines = keep_lines

                section_key = SECTION_TYPE_MAP.get(norm_header, norm_header.lower())

                # Create a mapping of text to nodes for this lesson and section
                text_to_nodes = {}
                for n in tagged_nodes:
                    if n.get("lesson_context") == lesson_header_raw:
                        if "inlines" in n:
                            plain = "".join(s["text"] for s in n["inlines"]).strip()
                            if plain:
                                if plain not in text_to_nodes:
                                    text_to_nodes[plain] = []
                                text_to_nodes[plain].append(n)

                # Process lines in order, preserving the original sequence
                quick_practice_titles = [ex["title"] for ex in self.parse_practice(embedded_practice_lines + practice_lines) if (ex.get("title", "").lower().startswith("quick practice"))]
                quick_practice_idx = 0

                for text_line, style in lines:
                    text_line = text_line.strip()
                    if not text_line:
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
                        continue

                    # Find matching nodes for this text
                    matching_nodes = text_to_nodes.get(text_line, [])

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
                        continue

                    if matching_nodes:
                        # Prefer nodes with the correct audio_section
                        audio_nodes = [n for n in matching_nodes if n.get("audio_section") == section_key]
                        section_nodes = [n for n in matching_nodes if n.get("section_context") == norm_header]

                        # Choose the best match
                        if audio_nodes:
                            chosen_node = audio_nodes[0]
                        elif section_nodes:
                            chosen_node = section_nodes[0]
                        else:
                            chosen_node = matching_nodes[0]

                        # Create a copy to avoid modifying the original
                        node_copy = chosen_node.copy()
                        if "inlines" in node_copy:
                            node_copy["inlines"] = [inline.copy() for inline in node_copy["inlines"]]

                        node_list.append(node_copy)
                        # Remove the used node to avoid duplicates
                        matching_nodes.remove(chosen_node)
                    else:
                        # If no matching node found, create a synthetic one
                        synthetic_node = {
                            "kind": "paragraph",
                            "level": None,
                            "inlines": [{"text": text_line, "bold": False, "italic": False, "underline": False}],
                            "indent": 0,
                            "lesson_context": lesson_header_raw,
                            "section_context": norm_header
                        }
                        node_list.append(synthetic_node)

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
            "practice_exercises":      self.parse_practice(embedded_practice_lines + practice_lines),
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


    def parse_practice(self, lines: List[str]) -> List[Dict]:
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
            original_line = line  # Keep original for text collection
            line = line.strip()

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

            if line.startswith("TITLE:"):
                cur_ex["title"] = line.split(":", 1)[1].strip()
                collecting_text = False
                collecting_paragraph = False
                continue
            if line.startswith("PROMPT:"):
                cur_ex["prompt"] = line.split(":", 1)[1].strip()
                collecting_text = False
                collecting_paragraph = False
                continue
            if line.startswith("PARAGRAPH:"):
                # Get the content after the colon
                content = line.split(":", 1)[1].strip() if ":" in line else ""

                if content:
                    # There's content on the same line
                    cur_ex["paragraph"] = content
                    collecting_paragraph = False
                else:
                    # Empty PARAGRAPH: line, start collecting multi-line paragraph
                    cur_ex["paragraph"] = ""
                    collecting_paragraph = True
                collecting_text = False
                continue

            # Item-level directives - handle both QUESTION: and ITEM:
            if line.startswith(("QUESTION:", "ITEM:")):
                number = line.split(":", 1)[1].strip()
                # Create a new question/item entry.
                cur_items.append({"number": number})
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            # --- TEXT/STEM for any exercise type ---
            if line.startswith(("TEXT:", "STEM:")):
                if not cur_items:
                    cur_items.append({})

                # Get the content after the colon
                content = line.split(":", 1)[1].strip() if ":" in line else ""

                if content:
                    # There's content on the same line
                    cur_items[-1]["text"] = content
                    collecting_text = False
                else:
                    # Empty TEXT: line, start collecting multi-line text
                    cur_items[-1]["text"] = ""
                    collecting_text = True
                collecting_opts = False
                continue

            if line.startswith("OPTIONS:"):
                collecting_opts = True
                collecting_text = False
                collecting_paragraph = False
                # Ensure the current item has an options list.
                if not cur_items:
                    cur_items.append({})
                cur_items[-1]["options"] = []
                continue

            if line.startswith("CORRECT:"):
                # Handle CORRECT: directive for sentence_transform exercises
                if not cur_items:
                    cur_items.append({})
                correct_value = line.split(":", 1)[1].strip()
                # Build the text field in the expected format
                cur_items[-1]["correct"] = correct_value
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            if line.startswith("ANSWER:"):
                # Only update if there's an existing item.
                if not cur_items:
                    cur_items.append({})
                cur_items[-1]["answer"] = line.split(":", 1)[1].strip()
                collecting_opts = False
                collecting_text = False
                collecting_paragraph = False
                continue

            if line.startswith(("KEYWORDS:", "PINNED COMMENT")):
                kw = line.split(":", 1)[1].strip() if ":" in line else ""
                if kw:
                    if not cur_items:
                        cur_items.append({})
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
                current_text = cur_items[-1].get("text", "")
                if current_text:
                    cur_items[-1]["text"] = current_text + "\n" + original_line
                else:
                    cur_items[-1]["text"] = original_line
                continue

            # Multi-line paragraph collection
            if collecting_paragraph and cur_ex:
                current_paragraph = cur_ex.get("paragraph", "")
                if current_paragraph:
                    cur_ex["paragraph"] = current_paragraph + "\n" + original_line
                else:
                    cur_ex["paragraph"] = original_line
                continue

            # Fallback: if not collecting options, text, or paragraph and we have items, append to current item's text
            if cur_items and not collecting_opts and not collecting_text and not collecting_paragraph:
                existing_text = cur_items[-1].get("text", "")
                if existing_text:
                    cur_items[-1]["text"] = existing_text + " " + line
                else:
                    cur_items[-1]["text"] = line

        flush_exercise()
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

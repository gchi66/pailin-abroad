"""topic_parser.py – Parser for 'Topic Library' Google Docs
────────────────────────────────────────────────────────────

Use this file to parse standalone Topic Library docs (e.g. COUNTABLE & UNCOUNTABLE NOUNS).
This parser is similar to parser.py for lessons, but simplified:

- Each document produces a SINGLE rich section.
- No transcript, comprehension, audio headers, or lesson metadata.
- All formatting (bold, italic, underline) must be preserved.
- Paragraphs, headers, and misc_item nodes must be preserved.
- The schema of `content_jsonb` must be IDENTICAL to lesson rich sections.

Usage
-----
python -m app.tools.topic_parser <document_id> --output data/topic_library.json [--lang th]
(Optional: use --raw-output to also dump the raw doc JSON.)
"""

from __future__ import annotations
import argparse
import copy
import dataclasses
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Union

from .docs_fetch import fetch_doc
from .docwalker import paragraph_nodes, Node
from .textutils import is_subheader

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ───────────────────────────── Bilingual helpers (from parser.py)

TH = re.compile(r'[\u0E00-\u0E7F]')
EN = re.compile(r'[A-Za-z]')
IMG_TAG_RE = re.compile(r'\[img:\s*([^\]]+?)\s*\]', re.IGNORECASE)
ALT_TEXT_RE = re.compile(r'ALT[\s-]*TEXT\s*:\s*(.+)', re.IGNORECASE | re.DOTALL)


def split_en_th(line: str):
    """Split a line into English and Thai components."""
    if not line:
        return None, None
    line = line.strip()

    # "EN (TH)" pattern
    m = re.match(r'^(.*?)\s*\(([\u0E00-\u0E7F].*?)\)\s*$', line)
    if m:
        en = m.group(1).strip() or None
        th = m.group(2).strip() or None
        return en, th

    # "EN … TH" pattern (first Thai char starts TH)
    thai_start = -1
    for i, ch in enumerate(line):
        if '\u0E00' <= ch <= '\u0E7F':
            thai_start = i
            break

    if thai_start >= 0:
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
    """Extract plain text from a node."""
    if "text" in node and isinstance(node["text"], str):
        return node["text"]
    if "inlines" in node:
        return ''.join(run.get("text", "") for run in node["inlines"])
    return ""


def _extract_img_key(text: str | None) -> str | None:
    if not text:
        return None
    match = IMG_TAG_RE.search(text)
    if not match:
        return None
    key = (match.group(1) or "").strip()
    return key or None


def bilingualize_headers_th(nodes, default_level=4):
    """Convert appropriate paragraphs and headings to bilingual format."""
    FOCUS_EN = "LESSON FOCUS"
    FOCUS_TH = "จุดเน้นบทเรียน"
    out = []

    def _combined_inline(node, en_text, th_text):
        combined = " ".join(filter(None, [en_text, th_text])).strip()
        if not combined:
            combined = node_plain_text(node).strip()
        template = (node.get("inlines") or [{}])[0]
        return [{
            "text": combined or "",
            "bold": template.get("bold", False),
            "italic": template.get("italic", False),
            "underline": template.get("underline", False)
        }]

    def _update_heading(node, level, en_text, th_text):
        heading = {**node}
        heading["kind"] = "heading"
        heading["level"] = level
        text_dict = {}
        if en_text:
            text_dict["en"] = en_text
        if th_text:
            text_dict["th"] = th_text
        if text_dict:
            heading["text"] = text_dict
        heading["inlines"] = _combined_inline(node, en_text, th_text)
        heading.pop("is_bold_header", None)
        return heading

    for n in nodes:
        # Handle LESSON FOCUS specifically
        if n.get("kind") == "paragraph":
            para_text = node_plain_text(n).strip()
            if para_text.upper() == FOCUS_EN:
                out.append(_update_heading(n, 3, FOCUS_EN, FOCUS_TH))
                continue

        # For existing headings, apply bilingual split
        if n.get("kind") in {"heading", "header"}:
            # Check if this is a LESSON FOCUS heading that needs Thai translation
            if isinstance(n.get("text"), dict):
                text_en = (n["text"].get("en") or "").strip().upper()
                if text_en == FOCUS_EN and not n["text"].get("th"):
                    out.append(_update_heading(n, n.get("level", default_level), FOCUS_EN, FOCUS_TH))
                    continue

            # Apply bilingual split to ALL headings
            s = node_plain_text(n)
            en, th = split_en_th(s)
            if en or th:
                out.append(_update_heading(n, n.get("level", default_level), en, th))
            else:
                out.append(n)
            continue

        # Only apply bilingual conversion to paragraphs
        if n.get("kind") == "paragraph":
            s = node_plain_text(n)
            has_th = bool(TH.search(s))
            has_en = bool(re.search(r'[A-Za-z]', s))

            # Check if this looks like a title
            looks_like_title = False
            if has_en:
                en_part, _ = split_en_th(s)
                if en_part:
                    en_stripped = en_part.strip()
                    looks_like_title = en_stripped and en_stripped.upper() == en_stripped and re.search(r'[A-Z]', en_stripped)

            if has_th and (looks_like_title or n.get("is_bold_header")):
                en, th = split_en_th(s)
                if en or th:
                    out.append(_update_heading(n, default_level, en, th))
                    continue

        out.append(n)

    return out


# ───────────────────────────── Helper functions

def _slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def get_heading_text(node: dict) -> str:
    """Extract text content from a heading node."""
    if isinstance(node.get("text"), dict):
        # Bilingual heading - prefer English, fallback to Thai
        return node["text"].get("en") or node["text"].get("th") or ""
    return node_plain_text(node)


def _extract_title_from_doc(doc_json: dict) -> str:
    """Extract title from document metadata or first heading."""
    # Try document title first
    title = doc_json.get("title", "").strip()
    if title:
        return title

    # Fallback: find first heading in content
    for elem in doc_json.get("body", {}).get("content", []):
        if "paragraph" in elem:
            para = elem["paragraph"]
            style = para.get("paragraphStyle", {}).get("namedStyleType", "")
            if style.startswith("HEADING") or style == "TITLE":
                text = "".join(
                    r.get("textRun", {}).get("content", "")
                    for r in para.get("elements", [])
                ).strip()
                if text:
                    return text

    return "Untitled Topic"


TABLE_HEADING_RE = re.compile(r'^TABLE[-\s]*\d+[:：]?$' , re.IGNORECASE)


def _table_block(elem: dict, tbl_id: int, label: str | None = None) -> dict:
    """Convert a Google-Docs table element to a minimal table node."""
    rows = []
    max_cols = 0
    active_rowspans: dict[int, int] = {}
    for row in elem["table"]["tableRows"]:
        row_cells = []
        # Decrement active rowspans as we move to a new row.
        for col in list(active_rowspans.keys()):
            active_rowspans[col] -= 1
            if active_rowspans[col] <= 0:
                del active_rowspans[col]
        col_idx = 0
        for cell in row["tableCells"]:
            while col_idx in active_rowspans:
                col_idx += 1
            cell_lines = []
            for para in cell.get("content", []):
                if "paragraph" in para:
                    text = "".join(
                        r.get("textRun", {}).get("content", "")
                        for r in para["paragraph"]["elements"]
                    )
                    cell_lines.append(text.strip())
            cell_text = "\n".join(cell_lines)
            cell_style = cell.get("tableCellStyle", {})
            colspan = cell_style.get("columnSpan", 1)
            rowspan = cell_style.get("rowSpan", 1)
            if rowspan and rowspan > 1:
                for c in range(col_idx, col_idx + (colspan or 1)):
                    active_rowspans[c] = max(active_rowspans.get(c, 0), rowspan - 1)
            if (colspan and colspan > 1) or (rowspan and rowspan > 1):
                cell_payload = {"text": cell_text}
                if colspan and colspan > 1:
                    cell_payload["colspan"] = colspan
                if rowspan and rowspan > 1:
                    cell_payload["rowspan"] = rowspan
                row_cells.append(cell_payload)
            else:
                row_cells.append(cell_text)
            col_idx += colspan or 1
        rows.append(row_cells)
        if active_rowspans:
            max_cols = max(max_cols, col_idx, max(active_rowspans) + 1)
        else:
            max_cols = max(max_cols, col_idx)

    table_node = {
        "kind": "table",
        "type": "table",
        "id": f"table-{tbl_id}",
        "rows": len(rows),
        "cols": max_cols if rows else 0,
        "cells": rows,
    }

    if label:
        table_node["table_label"] = label.strip()

    return table_node


# ───────────────────────────── TopicParser class

class TopicParser:
    def __init__(self):
        pass

    def parse_topic_document(self, document_id: str, lang: str = 'en') -> list[dict]:
        """Parse multiple topics from one Google Doc, return array."""
        logger.info(f"Parsing topic document {document_id} (lang={lang})")

        doc_json = fetch_doc(document_id)
        if not doc_json:
            logger.error("Failed to fetch document")
            return []

        # Collect all nodes from the document
        all_nodes = []
        table_counter = 0
        pending_table_label: str | None = None

        for elem in doc_json.get("body", {}).get("content", []):
            if "paragraph" in elem:
                para_nodes = list(paragraph_nodes(
                    {
                        "body": {"content": [elem]},
                        "lists": doc_json.get("lists", {}),
                    },
                    include_text_color=True,
                ))

                for node in para_nodes:
                    node_dict = dataclasses.asdict(node)

                    # Preserve inline links for topic library

                    # Preserve blank paragraphs as spacer nodes to control vertical gaps.
                    if node_dict.get("kind") == "paragraph":
                        if not node_plain_text(node_dict).strip():
                            all_nodes.append({
                                "kind": "spacer",
                                "level": None,
                                "inlines": [],
                                "indent": 0,
                            })
                            continue
                        is_all_bold = False
                        inlines = node_dict.get("inlines") or []
                        if inlines:
                            non_empty = [
                                span for span in inlines
                                if isinstance(span, dict) and (span.get("text") or "").strip()
                            ]
                            is_all_bold = bool(non_empty) and all(span.get("bold") for span in non_empty)

                        if is_all_bold or is_subheader(node_plain_text(node_dict), node_dict.get("style", "")):
                            node_dict["kind"] = "heading"
                            node_dict["level"] = node_dict.get("level") or 4
                            node_dict["is_subheader"] = True

                    # Detect TABLE-XX headings/paragraphs and treat them as labels for the next table
                    if node_dict.get("kind") in {"heading", "header", "paragraph"}:
                        heading_text = node_plain_text(node_dict).strip()
                        if heading_text and TABLE_HEADING_RE.match(heading_text):
                            pending_table_label = heading_text
                            continue
                        else:
                            pending_table_label = None

                    all_nodes.append(node_dict)

            elif "table" in elem:
                table_counter += 1
                table_node = _table_block(elem, table_counter, label=pending_table_label)
                if isinstance(pending_table_label, str) and pending_table_label.upper().endswith("-M:"):
                    table_node["table_visibility"] = "mobile"
                pending_table_label = None
                all_nodes.append(table_node)

        # Handle inline [img:...] tags and ALT-TEXT lines before topic split
        processed_nodes = []
        skip_until_index = None
        for idx, node in enumerate(all_nodes):
            if skip_until_index is not None and idx <= skip_until_index:
                continue

            if node.get("kind") == "paragraph":
                text = node_plain_text(node)
                image_key = _extract_img_key(text)
                if image_key:
                    alt_text = None
                    lookahead = idx + 1
                    while lookahead < len(all_nodes):
                        next_node = all_nodes[lookahead]
                        if next_node.get("kind") == "spacer":
                            lookahead += 1
                            continue
                        if next_node.get("kind") != "paragraph":
                            break
                        next_text = node_plain_text(next_node).strip()
                        if not next_text:
                            lookahead += 1
                            continue
                        alt_match = ALT_TEXT_RE.match(next_text)
                        if alt_match:
                            alt_text = (alt_match.group(1) or "").strip()
                            skip_until_index = lookahead
                        break

                    processed_nodes.append({
                        "kind": "image",
                        "image_key": image_key,
                        "alt_text": alt_text,
                        "inlines": [],
                        "indent": 0,
                        "level": None,
                    })
                    continue

            processed_nodes.append(node)

        # Split into topics based on level 3 headings (but ignore TABLE-XX headings)
        topics = []
        current_topic = None
        current_nodes = []

        for node in processed_nodes:
            # Check if this is a real topic heading (level 3) but not a table heading
            is_topic_heading = (
                node.get("kind") == "heading" and
                node.get("level") == 3 and
                not get_heading_text(node).upper().startswith("TABLE-")
            )

            if is_topic_heading:
                if current_topic:
                    slug_value = _slugify(current_topic["slug_source"]) or _slugify(current_topic["display_name"]) or "topic"
                    topics.append({
                        "name": current_topic["display_name"],
                        "slug": slug_value,
                        "content_jsonb": current_nodes,
                        "tags": []
                    })
                raw_heading = node_plain_text(node).strip()
                en_head, th_head = split_en_th(raw_heading)
                display_name = " ".join(filter(None, [en_head, th_head])) or raw_heading
                slug_source = en_head or raw_heading
                current_topic = {
                    "display_name": display_name.strip(),
                    "slug_source": slug_source.strip() if slug_source else display_name.strip(),
                    "en_text": en_head,
                    "th_text": th_head
                }
                current_nodes = []
            else:
                current_nodes.append(node)

        # Don't forget last topic
        if current_topic:
            slug_value = _slugify(current_topic["slug_source"]) or _slugify(current_topic["display_name"]) or "topic"
            topics.append({
                "name": current_topic["display_name"],
                "slug": slug_value,
                "content_jsonb": current_nodes,
                "tags": []
            })

        # Merge stray headings that produced empty topic shells back into the previous topic
        merged_topics: list[dict] = []
        for topic in topics:
            name = (topic.get("name") or "").strip()
            if not name:
                if merged_topics:
                    merged_topics[-1]["content_jsonb"].extend(topic.get("content_jsonb", []))
                    logger.debug("Merged orphan topic content into previous topic (slug=%s)", merged_topics[-1].get("slug"))
                else:
                    # Nothing to merge into; skip entirely
                    logger.warning("Dropping orphan topic with empty name and no previous topic to attach to.")
                continue
            merged_topics.append(topic)
        topics = merged_topics

        # Apply bilingual processing if Thai
        if lang == 'th':
            for topic in topics:
                # First, split bilingual headings and paragraph titles similarly to parser.py
                nodes_bi = bilingualize_headers_th(topic["content_jsonb"], default_level=3)
                processed_nodes = []
                for node in nodes_bi:
                    n = copy.deepcopy(node)
                    txt = n.get('text')
                    if isinstance(txt, dict):
                        en_text = (txt.get('en') or "").strip() or None
                        th_text = (txt.get('th') or "").strip() or None
                        text_dict = {}
                        if en_text:
                            text_dict['en'] = en_text
                        if th_text:
                            text_dict['th'] = th_text
                        if text_dict:
                            n['text'] = text_dict
                        else:
                            n.pop('text', None)

                        combined = " ".join(filter(None, [en_text, th_text])).strip()
                        if combined:
                            template = (n.get('inlines') or [{}])[0]
                            n['inlines'] = [{
                                'text': combined,
                                'bold': template.get('bold', False),
                                'italic': template.get('italic', False),
                                'underline': template.get('underline', False)
                            }]
                    processed_nodes.append(n)

                en_name, th_name = split_en_th(topic.get('name', ''))
                display_name = " ".join(filter(None, [en_name, th_name])).strip()
                if display_name:
                    topic['name'] = display_name

                topic['content_jsonb'] = processed_nodes
                topic['content_jsonb_th'] = copy.deepcopy(processed_nodes)

        return topics


def main():
    parser = argparse.ArgumentParser(description='Convert Topic Library Google Docs to JSON')
    parser.add_argument('document_id', help='Google Docs document ID')
    parser.add_argument('--output', help='File to write processed JSON output (default: stdout)')
    parser.add_argument('--raw-output', help='File to write raw JSON output (optional)')
    parser.add_argument('--lang', choices=['en', 'th'], default='en',
                        help='Language of the document (default: en)')
    args = parser.parse_args()

    try:
        topic_parser = TopicParser()

        if args.raw_output:
            raw_doc = fetch_doc(args.document_id)
            with open(args.raw_output, 'w', encoding='utf-8') as f:
                json.dump(raw_doc, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote raw document JSON to {args.raw_output}")

        # Pass lang parameter
        result = topic_parser.parse_topic_document(args.document_id, args.lang)

        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"Wrote processed output to {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

        logger.info(f"Topic document conversion successful - parsed {len(result)} topics")

    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()

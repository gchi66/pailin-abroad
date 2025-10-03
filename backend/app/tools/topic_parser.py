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
import dataclasses
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Union

from .docs_fetch import fetch_doc
from .docwalker import paragraph_nodes, Node

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ───────────────────────────── Bilingual helpers (from parser.py)

TH = re.compile(r'[\u0E00-\u0E7F]')
EN = re.compile(r'[A-Za-z]')


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


def bilingualize_headers_th(nodes, default_level=3):
    """Convert appropriate paragraphs and headings to bilingual format."""
    FOCUS_EN = "LESSON FOCUS"
    FOCUS_TH = "จุดเน้นบทเรียน"
    out = []

    for n in nodes:
        # Handle LESSON FOCUS specifically
        if n.get("kind") == "paragraph":
            para_text = node_plain_text(n).strip()
            if para_text.upper() == FOCUS_EN:
                out.append({
                    "kind": "heading",
                    "level": 3,
                    "text": {"en": FOCUS_EN, "th": FOCUS_TH},
                })
                continue

        # For existing headings, apply bilingual split
        if n.get("kind") in {"heading", "header"}:
            # Check if this is a LESSON FOCUS heading that needs Thai translation
            if isinstance(n.get("text"), dict):
                text_en = (n["text"].get("en") or "").strip().upper()
                if text_en == FOCUS_EN and not n["text"].get("th"):
                    n = {**n, "text": {**n["text"], "th": FOCUS_TH}}
                    out.append(n)
                    continue

            # Apply bilingual split to ALL headings
            s = node_plain_text(n)
            en, th = split_en_th(s)
            if en or th:
                new_heading = {**n}
                new_heading.update({
                    "kind": "heading",
                    "level": n.get("level", default_level),
                    "text": {"en": en, "th": th}
                })
                out.append(new_heading)
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
                    out.append({
                        "kind": "heading",
                        "level": default_level,
                        "text": {"en": en, "th": th}
                    })
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


def _table_block(elem: dict, tbl_id: int) -> dict:
    """Convert a Google-Docs table element to a minimal table node."""
    rows = []
    for row in elem["table"]["tableRows"]:
        row_cells = []
        for cell in row["tableCells"]:
            cell_lines = []
            for para in cell.get("content", []):
                if "paragraph" in para:
                    text = "".join(
                        r.get("textRun", {}).get("content", "")
                        for r in para["paragraph"]["elements"]
                    )
                    cell_lines.append(text.strip())
            row_cells.append("\n".join(cell_lines))
        rows.append(row_cells)

    return {
        "kind": "table",
        "type": "table",
        "id": f"table-{tbl_id}",
        "rows": len(rows),
        "cols": len(rows[0]) if rows else 0,
        "cells": rows,
    }


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

        for elem in doc_json.get("body", {}).get("content", []):
            if "paragraph" in elem:
                para_nodes = list(paragraph_nodes({
                    "body": {"content": [elem]},
                    "lists": doc_json.get("lists", {}),
                }))

                for node in para_nodes:
                    node_dict = dataclasses.asdict(node)

                    if "inlines" in node_dict:
                        for inline in node_dict["inlines"]:
                            inline.pop("link", None)

                    all_nodes.append(node_dict)

            elif "table" in elem:
                table_counter += 1
                table_node = _table_block(elem, table_counter)
                all_nodes.append(table_node)

        # Split into topics based on level 3 headings
        topics = []
        current_topic = None
        current_nodes = []

        for node in all_nodes:
            if node.get("kind") == "heading" and node.get("level") == 3:
                if current_topic:
                    topics.append({
                        "name": current_topic,
                        "slug": _slugify(current_topic),
                        "content_jsonb": current_nodes,
                        "tags": []
                    })
                current_topic = get_heading_text(node)
                current_nodes = []
            else:
                current_nodes.append(node)

        # Don't forget last topic
        if current_topic:
            topics.append({
                "name": current_topic,
                "slug": _slugify(current_topic),
                "content_jsonb": current_nodes,
                "tags": []
            })

        # Apply bilingual processing if Thai
        if lang == 'th':
            for topic in topics:
                topic["content_jsonb"] = bilingualize_headers_th(topic["content_jsonb"])

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

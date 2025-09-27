#USAGE: python -m app.tools.fetch_raw_json --doc 1USn1mSY52hCZ_f1r5fhwdvGLV8JdzVqqFmXxDAs5B0U --out data/lesson_11_raw.json


# fetch_raw_json.py
from __future__ import annotations

import argparse
import json
import re
from typing import Any, Dict, List, Optional, Tuple

# 🔑 use your existing fetch_doc
from app.tools.docs_fetch import fetch_doc

SECTION_TITLE_DEFAULT = "PHRASES & VERBS"
STRICT_BULLETS = {"•", "●", "▪"}
NUMBERED_GLYPHS = {"DECIMAL", "UPPER_ALPHA", "LOWER_ALPHA", "UPPER_ROMAN", "LOWER_ROMAN"}

MANUAL_NUMBERED_RX = re.compile(r"^(\d+\.|\d+\)|[A-Za-z]\.|[A-Za-z]\)|[ivxIVX]+\.)\s+")
MANUAL_BULLET_RX = re.compile(rf"^\s*(?:{'|'.join(map(re.escape, STRICT_BULLETS))})\s+")


# ----------------- helpers -----------------
def _plain_text(paragraph: dict) -> str:
    return "".join(
        el.get("textRun", {}).get("content", "")
        for el in paragraph.get("elements", []) or []
        if el.get("textRun")
    ).rstrip("\n")


def _heading_level(paragraph: dict) -> Optional[int]:
    style = (paragraph.get("paragraphStyle") or {}).get("namedStyleType", "")
    if isinstance(style, str) and style.startswith("HEADING_"):
        tail = style.rsplit("_", 1)[-1]
        if tail.isdigit():
            return int(tail)
        return 3
    return None


def _resolve_list_glyph(doc_json: dict, bullet_info: dict) -> Tuple[Optional[str], Optional[str]]:
    try:
        list_id = bullet_info.get("listId")
        level = bullet_info.get("nestingLevel", 0)
        lists = doc_json.get("lists", {}) or {}
        ldef = lists.get(list_id) or {}
        nesting = (ldef.get("listProperties") or {}).get("nestingLevels") or []
        props = nesting[level] if level < len(nesting) else {}
        return props.get("glyphType"), props.get("glyphSymbol")
    except Exception:
        return None, None


def _docwalker_kind_guess(paragraph: dict, doc_json: dict) -> str:
    lvl = _heading_level(paragraph)
    if lvl is not None:
        return "heading"

    text = _plain_text(paragraph).strip()

    bullet = paragraph.get("bullet")
    if bullet:
        glyph_type, glyph_symbol = _resolve_list_glyph(doc_json, bullet)
        if glyph_symbol and glyph_symbol in STRICT_BULLETS:
            return "list_item"
        if glyph_type in NUMBERED_GLYPHS:
            return "numbered_item"
        return "list_item"

    if MANUAL_NUMBERED_RX.match(text):
        return "numbered_item"
    if MANUAL_BULLET_RX.match(text):
        return "list_item"
    return "paragraph"


def _index_paragraphs(doc_json: dict):
    out = []
    for idx, el in enumerate(doc_json.get("body", {}).get("content", []) or []):
        p = el.get("paragraph")
        if not p:
            continue
        text = _plain_text(p).strip()
        lvl = _heading_level(p)
        out.append((idx, p, text, lvl is not None, lvl))
    return out


# ----------------- main slicer -----------------
def slice_all_phrases_verbs(doc_json: dict, section_title=SECTION_TITLE_DEFAULT) -> List[Dict[str, Any]]:
    """
    Return a list of {section_index, paragraphs[]} for every PHRASES & VERBS
    section found in the doc.
    """
    paras = _index_paragraphs(doc_json)
    body = doc_json.get("body", {}).get("content", []) or []
    results = []

    # find all PHRASES & VERBS headings
    starts = [(i, lvl) for (i, p, text, is_h, lvl) in paras
              if is_h and text.upper().startswith(section_title.upper())]

    for start_idx, lvl_start in starts:
        # find end boundary
        end_idx = paras[-1][0] + 1 if paras else 0
        for (i, p, text, is_h, lvl) in paras:
            if i <= start_idx:
                continue
            if is_h and (lvl is not None) and (lvl <= (lvl_start or 3)):
                end_idx = i
                break

        # collect paragraphs in this section
        slice_data = []
        for i in range(start_idx + 1, end_idx):
            p = body[i].get("paragraph")
            if not p:
                continue
            glyph_type, glyph_symbol = (None, None)
            if p.get("bullet"):
                glyph_type, glyph_symbol = _resolve_list_glyph(doc_json, p["bullet"])
            slice_data.append({
                "index": i,
                "text": _plain_text(p),
                "namedStyleType": (p.get("paragraphStyle") or {}).get("namedStyleType"),
                "bullet": p.get("bullet"),
                "resolvedListGlyph": {"glyphType": glyph_type, "glyphSymbol": glyph_symbol},
                "docwalker_kind_guess": _docwalker_kind_guess(p, doc_json),
            })
        results.append({
            "section_index": start_idx,
            "paragraphs": slice_data,
        })
    return results


# ----------------- CLI -----------------
def main():
    ap = argparse.ArgumentParser(description="Dump all PHRASES & VERBS sections from a Google Doc")
    ap.add_argument("--doc", required=True, help="Google Docs documentId")
    ap.add_argument("--out", default="full_doc.json", help="Write full doc JSON here")
    ap.add_argument("--slice-out", default="phrases_verbs_all.json", help="Write PHRASES & VERBS slice here")
    ap.add_argument("--section-title", default=SECTION_TITLE_DEFAULT, help="Section heading to slice")
    ap.add_argument("--no-full", action="store_true", help="Skip writing the full document JSON")
    args = ap.parse_args()

    # fetch full doc JSON using your existing helper
    doc_json = fetch_doc(args.doc)

    if not args.no_full:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(doc_json, f, ensure_ascii=False, indent=2)
        print(f"[fetch_raw_json] wrote full doc JSON → {args.out}")

    all_sections = slice_all_phrases_verbs(doc_json, section_title=args.section_title)
    with open(args.slice_out, "w", encoding="utf-8") as f:
        json.dump(all_sections, f, ensure_ascii=False, indent=2)
    print(f"[fetch_raw_json] wrote {len(all_sections)} PHRASES & VERBS sections → {args.slice_out}")


if __name__ == "__main__":
    main()

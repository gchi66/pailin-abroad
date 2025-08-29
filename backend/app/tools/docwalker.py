from __future__ import annotations
from dataclasses import dataclass, field
import logging
import re

from .textutils import is_subheader   # helper already in your repo

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#   Data structures
# ────────────────────────────────────────────────────────────
@dataclass
class Inline:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass
class Node:
    kind: str                     # heading | paragraph | list_item | numbered_item | misc_item
    level: int | None = None      # heading level (1-6) or None
    inlines: list[Inline] = field(default_factory=list)
    indent: int = 0               # nesting level


# ────────────────────────────────────────────────────────────
#   Internal helpers
# ────────────────────────────────────────────────────────────
_numbered_glyphs = {
    "DECIMAL",       # 1-, 2-, …
    "UPPER_ALPHA",   # A-, B-, …
    "LOWER_ALPHA",   # a-, b-, …
    "UPPER_ROMAN",   # I-, II-, …
    "LOWER_ROMAN",   # i-, ii-, …
}

# Only Unicode bullet “•” counts
_bullet_symbol = {"•", "●", "◦", "○", "∙", "·"}

_manual_numbered_rx = re.compile(
    r"^(\d+\.|\d+\)|[A-Za-z]\.|[A-Za-z]\)|[ivxIVX]+\.)\s+"
)
_manual_bullet_rx = re.compile(rf"^({'|'.join(map(re.escape, _bullet_symbol))})\s+")


def _plain_text(elems: list[dict]) -> str:
    """Concatenate textRun chunks in a Google-Docs paragraph element."""
    return "".join(
        r.get("textRun", {}).get("content", "")
        for r in elems if r.get("textRun")
    ).rstrip("\n")


def _is_native_bullet(doc_json: dict, bullet_info: dict) -> bool:
    """
    Decide whether a native Google-Docs list item is a bullet
    (True) or a numbered/lettered item (False).
    """
    list_id = bullet_info.get("listId")
    level   = bullet_info.get("nestingLevel", 0)
    list_def = doc_json.get("lists", {}).get(list_id)
    if not list_def:
        return True
    try:
        nest_def   = list_def["listProperties"]["nestingLevels"][level]
        glyph_type = nest_def.get("glyphType", "")
        glyph_sym  = nest_def.get("glyphSymbol", "")
    except Exception:
        return True
    if glyph_sym and glyph_sym in _bullet_symbol:
        return True
    if glyph_type in _numbered_glyphs:
        return False
    return True


def _manual_list_class(text: str) -> str | None:
    """
    For indented plain paragraphs (manual lists) decide the class:
        • "bullet"   → exactly our bullet symbol
        • "numbered" → looks like 1., a), I. …
        • None       → not a list
    """
    if _manual_bullet_rx.match(text):
        return "bullet"
    if _manual_numbered_rx.match(text):
        return "numbered"
    return None


# ────────────────────────────────────────────────────────────
#   Public generator
# ────────────────────────────────────────────────────────────
def paragraph_nodes(doc_json: dict):
    """
    Yield a stream of Node objects, one per paragraph.

    Headings keep their Google level (3 by default for SHOUTY
    sub-headers), bullets become list_item, numbered become
    numbered_item, everything else indented → misc_item.
    """
    for elem in doc_json.get("body", {}).get("content", []):
        p = elem.get("paragraph")
        if not p:
            continue

        # ─── collect spans ──────────────────────────────────────────
        spans: list[Inline] = []
        for run in p.get("elements", []):
            tr = run.get("textRun")
            if not tr:
                continue
            txt = tr["content"].rstrip("\n")
            st  = tr.get("textStyle", {})
            spans.append(
                Inline(
                    text       = txt,
                    bold       = bool(st.get("bold")),
                    italic     = bool(st.get("italic")),
                    underline  = bool(st.get("underline")),
                )
            )
        plain = "".join(s.text for s in spans).strip()

        # ─── indent / nesting ─────────────────────────────────────
        bullet_info = p.get("bullet")
        indent = bullet_info.get("nestingLevel", 0) if bullet_info else 0
        if indent == 0:
            pts = p.get("paragraphStyle", {}).get("indentStart", {}).get("magnitude", 0)
            indent = round(pts / 18)

        # ─── classify ─────────────────────────────────────────────
        style_name = p.get("paragraphStyle", {}).get("namedStyleType", "")

        # HEADINGS -------------------------------------------------
        if (style_name.startswith("HEADING_") and style_name not in {"HEADING_1","HEADING_2"}) \
           or is_subheader(plain, style_name):
            lvl = 3
            if style_name.startswith("HEADING_") and style_name[-1].isdigit():
                lvl = int(style_name[-1])
            yield Node(kind="heading", level=lvl, inlines=spans, indent=indent)
            continue

        # NATIVE GOOGLE LIST -------------------------------------
        if bullet_info:
            if _is_native_bullet(doc_json, bullet_info):
                yield Node(kind="list_item", inlines=spans, indent=indent)
            else:
                yield Node(kind="numbered_item", inlines=spans, indent=indent)
            continue

        # MANUAL LISTS (indented) -------------------------------
        if indent > 0:
            cls = _manual_list_class(plain)
            if cls == "bullet":
                yield Node(kind="list_item", inlines=spans, indent=indent)
            elif cls == "numbered":
                yield Node(kind="numbered_item", inlines=spans, indent=indent)
            else:
                yield Node(kind="misc_item", inlines=spans, indent=indent)
            continue

        # PLAIN PARAGRAPH ----------------------------------------
        yield Node(kind="paragraph", inlines=spans, indent=indent)

def debug_google_lists(doc_json: dict):
    """Debug what Google Docs thinks are lists"""
    print("\n=== GOOGLE DOCS LIST DEBUG ===")

    # Check what lists are defined
    lists = doc_json.get("lists", {})
    print(f"Found {len(lists)} list definitions:")
    for list_id, list_def in lists.items():
        print(f"  List {list_id}:")
        nesting_levels = list_def.get("listProperties", {}).get("nestingLevels", [])
        for i, level in enumerate(nesting_levels):
            glyph_type = level.get("glyphType", "")
            glyph_symbol = level.get("glyphSymbol", "")
            print(f"    Level {i}: glyphType='{glyph_type}', glyphSymbol='{glyph_symbol}'")

    # Check paragraphs with bullet info
    bullet_count = 0
    for elem in doc_json.get("body", {}).get("content", []):
        p = elem.get("paragraph")
        if not p:
            continue

        bullet_info = p.get("bullet")
        if bullet_info:
            bullet_count += 1
            text = _plain_text(p.get("elements", []))
            list_id = bullet_info.get("listId")
            nesting = bullet_info.get("nestingLevel", 0)
            print(f"  Bullet item: '{text[:50]}...' | listId={list_id} | nesting={nesting}")

            # Check what our function thinks about this
            is_bullet = _is_native_bullet(doc_json, bullet_info)
            print(f"    -> _is_native_bullet says: {is_bullet}")

    print(f"Total paragraphs with bullet info: {bullet_count}")
    print("=== END LIST DEBUG ===\n")

def debug_paragraph_classification(doc_json: dict, section_name: str = "PHRASES & VERBS"):
    """Debug how paragraphs get classified in a specific section"""
    print(f"\n=== PARAGRAPH CLASSIFICATION DEBUG ({section_name}) ===")

    in_target_section = False
    for elem in doc_json.get("body", {}).get("content", []):
        p = elem.get("paragraph")
        if not p:
            continue

        text = _plain_text(p.get("elements", [])).strip()
        if not text:
            continue

        # Check if we're entering/leaving the target section
        if section_name.upper() in text.upper():
            in_target_section = True
            print(f">>> Entering section: {text}")
            continue
        elif text.upper().startswith(("FOCUS", "BACKSTORY", "CONVERSATION", "COMPREHENSION", "PRACTICE", "UNDERSTAND", "CULTURE NOTE", "COMMON MISTAKES", "EXTRA TIPS", "PINNED COMMENT", "TAGS", "LESSON", "CHECKPOINT")):
            if in_target_section:
                print(f">>> Exiting section at: {text}")
                break
            continue

        if not in_target_section:
            continue

        # Analyze this paragraph
        style_name = p.get("paragraphStyle", {}).get("namedStyleType", "")
        bullet_info = p.get("bullet")
        indent = bullet_info.get("nestingLevel", 0) if bullet_info else 0

        if indent == 0:
            pts = p.get("paragraphStyle", {}).get("indentStart", {}).get("magnitude", 0)
            indent = round(pts / 18)

        print(f"  Text: '{text[:60]}...'")
        print(f"    Style: '{style_name}'")
        print(f"    Has bullet info: {bool(bullet_info)}")
        print(f"    Indent: {indent}")

        if bullet_info:
            list_id = bullet_info.get("listId")
            nesting = bullet_info.get("nestingLevel", 0)
            is_bullet = _is_native_bullet(doc_json, bullet_info)
            print(f"    Bullet details: listId={list_id}, nesting={nesting}, is_bullet={is_bullet}")

        # What would the docwalker classify this as?
        if style_name.startswith("HEADING_") or is_subheader(text, style_name):
            classification = "heading"
        elif bullet_info:
            if _is_native_bullet(doc_json, bullet_info):
                classification = "list_item"
            else:
                classification = "numbered_item"
        elif indent > 0:
            cls = _manual_list_class(text)
            if cls == "bullet":
                classification = "list_item"
            elif cls == "numbered":
                classification = "numbered_item"
            else:
                classification = "misc_item"
        else:
            classification = "paragraph"

        print(f"    -> Classification: {classification}")
        print()

    print("=== END CLASSIFICATION DEBUG ===\n")

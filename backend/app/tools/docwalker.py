from dataclasses import dataclass
from .textutils import is_subheader
import logging

logger = logging.getLogger(__name__)

@dataclass
class Inline:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False

@dataclass
class Node:
    kind: str                   # 'heading' | 'paragraph' | 'list_item' | 'numbered_item'
    level: int | None = None    # for headings
    inlines: list[Inline] | None = None
    indent: int = 0             # bullet nesting

def is_bullet_list(doc_json, bullet_info):
    """
    Check if a bullet is actually a bullet point (not a numbered list).
    Returns True for bullet points, False for numbered lists.
    """
    if not bullet_info:
        return False

    list_id = bullet_info.get("listId")
    nesting_level = bullet_info.get("nestingLevel", 0)

    if not list_id:
        logger.debug("No listId found in bullet_info")
        return False

    # Check the list properties in the document
    lists = doc_json.get("lists", {})
    if list_id not in lists:
        logger.debug(f"List ID {list_id} not found in document lists. Available lists: {list(lists.keys())}")
        # If we can't find the list definition, assume it's a bullet (common case)
        return True

    list_properties = lists[list_id]
    nesting_properties = list_properties.get("listProperties", {}).get("nestingLevels", [])

    logger.debug(f"List {list_id} has {len(nesting_properties)} nesting levels, requesting level {nesting_level}")

    if nesting_level >= len(nesting_properties):
        logger.debug(f"Nesting level {nesting_level} exceeds available levels ({len(nesting_properties)}), defaulting to bullet")
        # If the nesting level isn't defined, it's often a simple bullet list
        return True

    current_level = nesting_properties[nesting_level]
    glyph_type = current_level.get("glyphType", "")
    glyph_symbol = current_level.get("glyphSymbol", "")
    glyph_format = current_level.get("glyphFormat", "")

    # Log the full level info for debugging
    logger.debug(f"List {list_id}, level {nesting_level}: {current_level}")
    logger.debug(f"  glyphType='{glyph_type}', glyphSymbol='{glyph_symbol}', glyphFormat='{glyph_format}'")

    # Check if it's explicitly a numbered list
    numbered_types = {
        "DECIMAL",           # 1, 2, 3...
        "UPPER_ALPHA",       # A, B, C...
        "LOWER_ALPHA",       # a, b, c...
        "UPPER_ROMAN",       # I, II, III...
        "LOWER_ROMAN"        # i, ii, iii...
    }

    # If we have a glyph symbol, check if it looks like a bullet
    if glyph_symbol:
        bullet_symbols = {"•", "◦", "▪", "▫", "‣", "⁃", "-", "*"}
        if glyph_symbol in bullet_symbols:
            logger.debug(f"Detected bullet based on symbol: '{glyph_symbol}'")
            return True

    # Check glyph type - if it's a numbered type, it's definitely numbered
    if glyph_type in numbered_types:
        logger.debug(f"Detected numbered list based on glyph type: '{glyph_type}'")
        return False

    # If glyph type is empty/unspecified and no symbol, it's usually a bullet
    if not glyph_type or glyph_type in {"GLYPH_TYPE_UNSPECIFIED", "NONE"}:
        logger.debug(f"Empty or unspecified glyph type, assuming bullet list")
        return True

    # For any other glyph type we don't recognize, log it and default to bullet
    logger.debug(f"Unknown glyph type '{glyph_type}', defaulting to bullet")
    return True

def paragraph_nodes(doc_json):
    """
    Yield Node objects instead of markdown strings.
    """
    for elem in doc_json["body"]["content"]:
        p = elem.get("paragraph")
        if not p:
            continue

        # -------- indent / bullet
        bullet_info = p.get("bullet")
        indent = bullet_info.get("nestingLevel", 0) if bullet_info else 0
        if indent == 0:
            pts = p.get("paragraphStyle", {}).get("indentStart", {}).get("magnitude", 0)
            indent = round(pts / 18)

        # -------- inline spans
        spans = []
        for run in p["elements"]:
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

        style = p.get("paragraphStyle", {}).get("namedStyleType", "")
        plain_text = "".join(s.text for s in spans).strip()

        # ── decide kind ────────────────────────────────────────────────
        if (style.startswith("HEADING_") and style not in {"HEADING_1", "HEADING_2"}) \
        or is_subheader(plain_text, style):
            # default "manual" headers to level 3
            lvl = int(style[-1]) if style.startswith("HEADING_") else 3
            yield Node(kind="heading", level=lvl, inlines=spans, indent=indent)
        elif bullet_info:
            # This handles Google Docs native bullet/numbered lists
            list_id = bullet_info.get("listId")
            nesting_level = bullet_info.get("nestingLevel", 0)

            # Get additional context for debugging
            lists = doc_json.get("lists", {})
            if list_id in lists:
                list_props = lists[list_id].get("listProperties", {})
                nesting_levels = list_props.get("nestingLevels", [])
                if nesting_level < len(nesting_levels):
                    current_level = nesting_levels[nesting_level]
                    logger.debug(f"Processing native list item: '{plain_text[:50]}...' "
                               f"listId={list_id}, level={nesting_level}, "
                               f"glyphType={current_level.get('glyphType', 'None')}, "
                               f"glyphSymbol={current_level.get('glyphSymbol', 'None')}")

            # Distinguish between bullet points and numbered lists
            if is_bullet_list(doc_json, bullet_info):
                logger.debug(f"Classified as native bullet: '{plain_text[:30]}...'")
                yield Node(kind="list_item", inlines=spans, indent=indent)
            else:
                logger.debug(f"Classified as native numbered: '{plain_text[:30]}...'")
                yield Node(kind="numbered_item", inlines=spans, indent=indent)
        elif indent > 0 and is_manual_list_item(plain_text):
            # This handles manually typed numbered/bulleted lists (indented paragraphs)
            if is_numbered_list_by_content(plain_text):
                logger.debug(f"Classified as manual numbered item: '{plain_text[:30]}...' (indent={indent})")
                yield Node(kind="numbered_item", inlines=spans, indent=indent)
            else:
                logger.debug(f"Classified as manual bullet list: '{plain_text[:30]}...' (indent={indent})")
                yield Node(kind="list_item", inlines=spans, indent=indent)
        else:
            yield Node(kind="paragraph", inlines=spans, indent=indent)


def is_manual_list_item(plain_text):
    """
    Check if this looks like a manually typed list item (numbered or bulleted).
    """
    text = plain_text.strip()
    if not text:
        return False

    import re

    # Patterns for numbered lists
    numbered_patterns = [
        r'^\d+\.',           # 1. 2. 3.
        r'^\d+\)',           # 1) 2) 3)
        r'^[a-z]\.',         # a. b. c.
        r'^[A-Z]\.',         # A. B. C.
        r'^[ivx]+\.',        # i. ii. iii.
        r'^[IVX]+\.',        # I. II. III.
    ]

    # Patterns for bullet lists
    bullet_patterns = [
        r'^[•◦▪▫‣⁃\-\*]\s',  # Various bullet symbols followed by space
        r'^[•◦▪▫‣⁃\-\*]',     # Just the bullet symbol
    ]

    # Check numbered patterns
    for pattern in numbered_patterns:
        if re.match(pattern, text):
            return True

    # Check bullet patterns
    for pattern in bullet_patterns:
        if re.match(pattern, text):
            return True

    return False


def is_numbered_list_by_content(plain_text):
    """
    Analyze the text content to determine if it's a numbered list item.
    Returns True for numbered lists, False for bullet lists.
    """
    text = plain_text.strip()
    if not text:
        return False

    import re

    # Check if text starts with common numbered patterns
    numbered_patterns = [
        r'^\d+\.',           # 1. 2. 3.
        r'^\d+\)',           # 1) 2) 3)
        r'^[a-z]\.',         # a. b. c.
        r'^[A-Z]\.',         # A. B. C.
        r'^[ivx]+\.',        # i. ii. iii. (roman numerals)
        r'^[IVX]+\.',        # I. II. III. (roman numerals)
    ]

    for pattern in numbered_patterns:
        if re.match(pattern, text):
            return True  # It's a numbered list

    return False  # It's a bullet list

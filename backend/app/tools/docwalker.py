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
    link: str | None = None
    highlight: str | None = None  # Add this field
    color: str | None = None


@dataclass
class Node:
    kind: str                     # heading | paragraph | list_item | numbered_item | misc_item
    level: int | None = None      # heading level (1-6) or None
    inlines: list[Inline] = field(default_factory=list)
    # legacy indent used for detection/classification (normalized with 36pt subtraction)
    indent: int = 0
    detection_indent: int = 0
    # display/measurement fields (preserve raw pt values and half-step levels)
    indent_level: int = 0
    indent_start_pts: float = 0.0
    indent_first_line_pts: float = 0.0
    indent_first_line_level: int = 0
    style: str = ""               # named style (e.g. HEADING_3, NORMAL_TEXT)
    is_indented: bool = False     # flag true for manually-indented paragraphs


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

# Only Unicode bullet "•" counts
_bullet_symbol = {"•", "◦", "▪", "●", "○"}

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


def _clean_vertical_tabs(text: str) -> str:
    """
    Clean up vertical tab characters (\u000b) from text.
    Convert to newlines to preserve bilingual structure.
    """
    return text.replace("\u000b", "\n")


def _is_native_bullet(doc_json: dict, bullet_info: dict, paragraph: dict) -> bool:
    """
    Decide whether a native Google-Docs list item is a bullet
    (True) or a numbered/lettered item (False).

    First check resolvedListGlyph on the paragraph, then fall back to lists definition.
    """
    # Check resolvedListGlyph first (most reliable)
    resolved_glyph = paragraph.get("resolvedListGlyph", {})
    if resolved_glyph:
        glyph_type = resolved_glyph.get("glyphType", "")
        glyph_sym = resolved_glyph.get("glyphSymbol")

        # If we have a numbered glyph type, it's numbered
        if glyph_type in _numbered_glyphs:
            return False

        # If we have a clear bullet symbol, it's a bullet
        if glyph_sym and glyph_sym in _bullet_symbol:
            return True

    # Fallback to original lists-based approach
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




def _dominant_indent_threshold(doc_json: dict) -> int:
    """
    Return the most common indentFirstLine magnitude (≥36 PT) among
    non-bullet paragraphs that contain text. Falls back to 0 if no
    qualifying paragraphs exist.
    """
    from collections import Counter

    indent_values = []
    for elem in doc_json.get("body", {}).get("content", []):
        paragraph = elem.get("paragraph")
        if not paragraph or paragraph.get("bullet"):
            continue

        text = _plain_text(paragraph.get("elements", [])).strip()
        if not text:
            continue

        first_line = (
            paragraph.get("paragraphStyle", {})
            .get("indentFirstLine", {})
            .get("magnitude", 0)
        )
        if first_line >= 36:
            indent_values.append(first_line)

    if not indent_values:
        return 0

    return Counter(indent_values).most_common(1)[0][0]


# ────────────────────────────────────────────────────────────
#   Public generator
# ────────────────────────────────────────────────────────────
def paragraph_nodes(doc_json: dict, *, include_text_color: bool = False):
    """
    Yield a stream of Node objects, one per paragraph.

    Headings keep their Google level (3 by default for SHOUTY
    sub-headers), bullets become list_item, numbered become
    numbered_item, everything else indented → misc_item.
    """
    indent_threshold = _dominant_indent_threshold(doc_json)

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
            # Clean vertical tabs here at the source
            txt = _clean_vertical_tabs(txt)
            st  = tr.get("textStyle", {})

            # Sentinel link (or any link)
            link = None
            if "link" in st and st["link"].get("url"):
                link = st["link"]["url"]

            # Extract highlight/background color
            highlight = None
            if 'backgroundColor' in st:
                bg_color = st['backgroundColor']
                if 'color' in bg_color and 'rgbColor' in bg_color['color']:
                    rgb = bg_color['color']['rgbColor']
                    # Convert RGB to hex
                    r = int(rgb.get('red', 0) * 255)
                    g = int(rgb.get('green', 0) * 255)
                    b = int(rgb.get('blue', 0) * 255)
                    highlight = f"#{r:02x}{g:02x}{b:02x}"

            color = None
            if include_text_color and 'foregroundColor' in st:
                fg_color = st['foregroundColor']
                if 'color' in fg_color and 'rgbColor' in fg_color['color']:
                    rgb = fg_color['color']['rgbColor']
                    r = int(rgb.get('red', 0) * 255)
                    g = int(rgb.get('green', 0) * 255)
                    b = int(rgb.get('blue', 0) * 255)
                    color = f"#{r:02x}{g:02x}{b:02x}"

            spans.append(
                Inline(
                    text       = txt,
                    bold       = bool(st.get("bold")),
                    italic     = bool(st.get("italic")),
                    underline  = bool(st.get("underline")),
                    link       = link,
                    highlight  = highlight,  # Add this field
                    color      = color,
                )
            )
        plain = "".join(s.text for s in spans).strip()
        has_text = bool(plain)

        # ─── indent / nesting ─────────────────────────────────────
        bullet_info = p.get("bullet")
        para_style = p.get("paragraphStyle", {})

        # Get raw indent values. For list items, fall back to list-level indents
        # if the paragraph style omits them (Docs sometimes stores these only on the list).
        base_indent_dict = para_style.get("indentStart")
        first_line_indent_dict = para_style.get("indentFirstLine")

        base_indent_pts = (
            base_indent_dict.get("magnitude") if isinstance(base_indent_dict, dict) and "magnitude" in base_indent_dict else None
        )
        first_line_indent_pts = (
            first_line_indent_dict.get("magnitude")
            if isinstance(first_line_indent_dict, dict) and "magnitude" in first_line_indent_dict
            else None
        )

        if bullet_info:
            list_id = bullet_info.get("listId")
            nesting_level = bullet_info.get("nestingLevel", 0)
            list_def = doc_json.get("lists", {}).get(list_id, {})
            nesting_levels = list_def.get("listProperties", {}).get("nestingLevels", [])
            list_level_def = nesting_levels[nesting_level] if nesting_level < len(nesting_levels) else {}

            if base_indent_pts is None:
                base_indent_pts = list_level_def.get("indentStart", {}).get("magnitude")
            if first_line_indent_pts is None:
                first_line_indent_pts = list_level_def.get("indentFirstLine", {}).get("magnitude")

        base_indent_pts = base_indent_pts or 0
        first_line_indent_pts = first_line_indent_pts or 0

        # Normalize: subtract the accidental 36 PT base from levels 3-12
        if base_indent_pts >= 36:
            normalized_base_pts = base_indent_pts - 36
        else:
            normalized_base_pts = base_indent_pts

        # Display levels: 36pt per level (one tab / bullet = level 1). Keep raw first-line for reference.
        indent_level = round(base_indent_pts / 36) if base_indent_pts else 0
        indent_first_line_level = round(first_line_indent_pts / 18) if first_line_indent_pts else 0

        # Calculate base indent (for non-bullets or additional nesting)
        base_indent = round(max(0, normalized_base_pts) / 18)

        # Handle bullets separately
        if bullet_info:
            # Check nestingLevel first
            bullet_nesting = bullet_info.get("nestingLevel", 0)

            # If no explicit nesting but has indentFirstLine, use that
            if bullet_nesting == 0 and first_line_indent_pts > 0:
                # Bullets should be indented by indentFirstLine
                indent = round(first_line_indent_pts / 18)
            else:
                # Use nesting level, or add to base if both exist
                indent = max(bullet_nesting, base_indent)
        else:
            # Non-bullets just use normalized base
            indent = base_indent

        detection_indent = indent  # preserve legacy indent used for classification

        # ─── classify ─────────────────────────────────────────────
        style_name = p.get("paragraphStyle", {}).get("namedStyleType", "")

        # HEADINGS -------------------------------------------------
        # Never treat "I (ฉัน)" as a header, even if styled as one.
        is_forced_non_header = bool(re.match(r"^I\s*\(\s*ฉัน\s*\)\s*$", plain.strip()))
        if not is_forced_non_header and (
           (style_name.startswith("HEADING_") and style_name not in {"HEADING_1","HEADING_2"})
           or is_subheader(plain, style_name)
        ):
            lvl = 3
            if style_name.startswith("HEADING_") and style_name[-1].isdigit():
                lvl = int(style_name[-1])
            yield Node(
                kind="heading",
                level=lvl,
                inlines=spans,
                indent=detection_indent,
                detection_indent=detection_indent,
                indent_level=indent_level,
                indent_start_pts=base_indent_pts,
                indent_first_line_pts=first_line_indent_pts,
                indent_first_line_level=indent_first_line_level,
                style=style_name,
            )
            continue

        # NATIVE GOOGLE LIST -------------------------------------
        if bullet_info:
            if _is_native_bullet(doc_json, bullet_info, p):
                yield Node(
                    kind="list_item",
                    inlines=spans,
                    indent=detection_indent,
                    detection_indent=detection_indent,
                    indent_level=indent_level,
                    indent_start_pts=base_indent_pts,
                    indent_first_line_pts=first_line_indent_pts,
                    indent_first_line_level=indent_first_line_level,
                    style=style_name,
                )
            else:
                yield Node(
                    kind="numbered_item",
                    inlines=spans,
                    indent=detection_indent,
                    detection_indent=detection_indent,
                    indent_level=indent_level,
                    indent_start_pts=base_indent_pts,
                    indent_first_line_pts=first_line_indent_pts,
                    indent_first_line_level=indent_first_line_level,
                    style=style_name,
                )
            continue

        # MANUAL LISTS (indented) -------------------------------
        if detection_indent > 0:
            cls = _manual_list_class(plain)
            if cls == "bullet":
                yield Node(
                    kind="list_item",
                    inlines=spans,
                    indent=detection_indent,
                    detection_indent=detection_indent,
                    indent_level=indent_level,
                    indent_start_pts=base_indent_pts,
                    indent_first_line_pts=first_line_indent_pts,
                    indent_first_line_level=indent_first_line_level,
                    style=style_name,
                )
            elif cls == "numbered":
                yield Node(
                    kind="numbered_item",
                    inlines=spans,
                    indent=detection_indent,
                    detection_indent=detection_indent,
                    indent_level=indent_level,
                    indent_start_pts=base_indent_pts,
                    indent_first_line_pts=first_line_indent_pts,
                    indent_first_line_level=indent_first_line_level,
                    style=style_name,
                )
            else:
                yield Node(
                    kind="misc_item",
                    inlines=spans,
                    indent=detection_indent,
                    detection_indent=detection_indent,
                    indent_level=indent_level,
                    indent_start_pts=base_indent_pts,
                    indent_first_line_pts=first_line_indent_pts,
                    indent_first_line_level=indent_first_line_level,
                    style=style_name,
                )
            continue

        # PLAIN PARAGRAPH ----------------------------------------
        is_indented = (
            not bullet_info
            and has_text
            and indent_threshold > 0
            and first_line_indent_pts >= indent_threshold
        )
        yield Node(
            kind="paragraph",
            inlines=spans,
            indent=detection_indent,
            detection_indent=detection_indent,
            indent_level=indent_level,
            indent_start_pts=base_indent_pts,
            indent_first_line_pts=first_line_indent_pts,
            indent_first_line_level=indent_first_line_level,
            style=style_name,
            is_indented=is_indented,
        )

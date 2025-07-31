from dataclasses import dataclass
from .textutils import is_subheader

@dataclass
class Inline:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False

@dataclass
class Node:
    kind: str                   # 'heading' | 'paragraph' | 'list_item' | 'numbered_list_item'
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
        return False

    # Check the list properties in the document
    lists = doc_json.get("lists", {})
    if list_id not in lists:
        return False

    list_properties = lists[list_id]
    nesting_properties = list_properties.get("listProperties", {}).get("nestingLevels", [])

    if nesting_level >= len(nesting_properties):
        return False

    current_level = nesting_properties[nesting_level]
    glyph_type = current_level.get("glyphType", "")

    # Check if it's a bullet (not numbered)
    # Common bullet glyph types: "GLYPH_TYPE_UNSPECIFIED", "DECIMAL", "UPPER_ALPHA", etc.
    # Bullet points typically don't have DECIMAL, UPPER_ALPHA, LOWER_ALPHA, etc.
    numbered_types = {"DECIMAL", "UPPER_ALPHA", "LOWER_ALPHA", "UPPER_ROMAN", "LOWER_ROMAN"}

    return glyph_type not in numbered_types

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
            # Distinguish between bullet points and numbered lists
            if is_bullet_list(doc_json, bullet_info):
                yield Node(kind="list_item", inlines=spans, indent=indent)
            else:
                yield Node(kind="numbered_list_item", inlines=spans, indent=indent)
        else:
            yield Node(kind="paragraph", inlines=spans, indent=indent)

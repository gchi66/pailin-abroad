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
    kind: str                   # 'heading' | 'paragraph' | 'list_item'
    level: int | None = None    # for headings
    inlines: list[Inline] | None = None
    indent: int = 0             # bullet nesting

def paragraph_nodes(doc_json):
    """
    Yield Node objects instead of markdown strings.
    """
    for elem in doc_json["body"]["content"]:
        p = elem.get("paragraph")
        if not p:
            continue

        # -------- indent / bullet
        indent = p.get("bullet", {}).get("nestingLevel", 0)
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
            # default “manual” headers to level 3
            lvl = int(style[-1]) if style.startswith("HEADING_") else 3
            yield Node(kind="heading", level=lvl, inlines=spans, indent=indent)
        elif p.get("bullet"):
            yield Node(kind="list_item", inlines=spans, indent=indent)
        else:
            yield Node(kind="paragraph", inlines=spans, indent=indent)

def paragraphs(doc_json):
    """Yield dicts with indent and markdown-formatted text for each paragraph."""
    for elem in doc_json["body"]["content"]:
        p = elem.get("paragraph")
        if not p:  # skip tables/images for now
            continue

        # ----- indent -----
        indent = p.get("bullet", {}).get("nestingLevel", 0)
        if indent == 0:
            pts = p.get("paragraphStyle", {}).get("indentStart", {}).get("magnitude", 0)
            indent = round(pts / 18)

        # ----- text with markdown -----
        parts = []
        for run in p["elements"]:
            tr = run.get("textRun")
            if not tr:
                continue
            txt = tr["content"].rstrip("\n")
            st  = tr.get("textStyle", {})
            if st.get("bold"):
                txt = f"**{txt}**"
            if st.get("italic"):
                txt = f"*{txt}*"
            if st.get("underline"):
                txt = f"__{txt}__"
            parts.append(txt)

        yield {
            "indent": indent,
            "text":   "".join(parts).strip()
        }

import re

UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-!?$%#]{2,60}$")

def is_subheader(text: str, style: str) -> bool:
    """
    True for HEADING_3…6 *or* for a paragraph that is entirely ALL-CAPS
    (2-60 chars, digits & basic punctuation allowed), even if the style is NORMAL_TEXT.
    """
    normalized_text = text.replace("\u200b", "").strip()
    if style.startswith("HEADING_") and style not in {"HEADING_1", "HEADING_2"}:
        return True
    if bool(UPPER_SUB_RE.match(normalized_text)):
        return True
    return False

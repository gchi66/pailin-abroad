import re

TH_RX = re.compile(r'[\u0E00-\u0E7F]')  # Thai block
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'‘’\-!?$%#\[\]:]{2,80}$")
HEADER_WITH_COLON_RE = re.compile(r"^[A-Z][A-Z0-9 ,.&'‘’\-!?$%#]+: [0-9]{1,2}:[0-9]{2} ?- ?[0-9]{1,2}:[0-9]{2}$")
HEADER_TRAILING_VARIANT_RE = re.compile(r"\[\s*\d+\s*\]\s*$")  # e.g. [1], [ 2 ]

def is_subheader(text: str, style: str) -> bool:
    """
    True for HEADING_3…6 *or* ALL-CAPS (ignoring Thai chars) *or* lines ending with [n],
    also true for 'TELLING THE TIME: 12:01 - 12:09'.
    """
    normalized_text = text.replace("\u200b", "").strip()
    # treat as header if styled (H3+)
    if style.startswith("HEADING_") and style not in {"HEADING_1", "HEADING_2"}:
        return True
    # allow headers with explicit [n] variant anywhere at end
    if HEADER_TRAILING_VARIANT_RE.search(normalized_text):
        return True
    # ALL-CAPS test should ignore Thai letters
    ascii_only = TH_RX.sub("", normalized_text).strip()
    if bool(UPPER_SUB_RE.match(ascii_only)):
        return True
    if bool(HEADER_WITH_COLON_RE.match(ascii_only)):
        return True
    return False

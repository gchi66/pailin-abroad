import re

TH_RX = re.compile(r'[\u0E00-\u0E7F]')  # Thai block
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&/()++'‘’\-!?$%#\[\]:…→]{2,80}$")
HEADER_WITH_COLON_RE = re.compile(r"^[A-Z][A-Z0-9 ,.&'‘’\-!?$%#]+: [0-9]{1,2}:[0-9]{2} ?- ?[0-9]{1,2}:[0-9]{2}$")
HEADER_TRAILING_VARIANT_RE = re.compile(r"\[\s*\d+\s*\]\s*$")  # e.g. [1], [ 2 ]
NON_HEADER_TOKENS_RE = re.compile(r"^I\s*\(\s*ฉัน\s*\)\s*$")

def is_subheader(text: str, style: str) -> bool:
    """
    True for HEADING_3…6 *or* ALL-CAPS (ignoring Thai chars) *or* lines ending with [n],
    also true for 'TELLING THE TIME: 12:01 - 12:09'.

    Added guard (ALL-CAPS path only): the first Latin alphabetic letter in the *original*
    text must be an uppercase English letter (A–Z).
    """
    normalized_text = text.replace("\u200b", "").strip()

    if NON_HEADER_TOKENS_RE.match(normalized_text):
        return False

    # treat as header if styled (H3+)
    if style.startswith("HEADING_") and style not in {"HEADING_1", "HEADING_2"}:
        return True

    # allow headers with explicit [n] variant anywhere at end
    if HEADER_TRAILING_VARIANT_RE.search(normalized_text):
        return True

    # --- ALL-CAPS heuristic (Thai-stripped) with new "first letter must be uppercase Latin" guard ---
    # Find the first Latin alphabetic letter in the original text (skip spaces, Thai, digits, punctuation)
    first_latin_letter = None
    for ch in normalized_text:
        if ch.isspace() or ch == "\u200b":
            continue
        # skip Thai letters
        if '\u0E00' <= ch <= '\u0E7F':
            continue
        # take the first Latin alphabetic letter we encounter (ignore digits/punct)
        if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'):
            first_latin_letter = ch
            break
        # otherwise keep scanning

    # ALL-CAPS test should ignore Thai letters, but the English must lead the
    # line. A Thai bullet/body sentence can contain an uppercase acronym such
    # as LGBTQ+ without becoming a subheader. Ignore punctuation when deciding
    # which script actually comes first (for example, "-สนับสนุน... LGBTQ+").
    ascii_only = TH_RX.sub("", normalized_text).strip()
    has_thai = bool(TH_RX.search(normalized_text))
    first_thai_index = next(
        (index for index, char in enumerate(normalized_text) if '\u0E00' <= char <= '\u0E7F'),
        None,
    )
    first_latin_index = next(
        (index for index, char in enumerate(normalized_text) if char.isascii() and char.isalpha()),
        None,
    )
    if (
        has_thai
        and first_thai_index is not None
        and (first_latin_index is None or first_thai_index < first_latin_index)
    ):
        return False
    if (
        ascii_only
        and re.search(r'[A-Z]', ascii_only)
        and UPPER_SUB_RE.match(ascii_only)  # reasonably "header-like"
        and re.search(r'[A-Z]{2,}', ascii_only)  # at least one 2+ letter English word
    ):
        if first_latin_letter is not None and 'A' <= first_latin_letter <= 'Z':
            return True

    # time-range header like "TELLING THE TIME: 12:01 - 12:09"
    if HEADER_WITH_COLON_RE.match(ascii_only):
        return True

    return False

import re

TH_RX = re.compile(r'[\u0E00-\u0E7F]')  # Thai block
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&/()++'‘’\-!?$%#\[\]:…]{2,80}$")
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

    # ALL-CAPS test should ignore Thai letters
    ascii_only = TH_RX.sub("", normalized_text).strip()
    has_thai = bool(TH_RX.search(normalized_text))
    if has_thai:
        # Avoid treating single-letter English + Thai as a subheader (e.g., "I (ฉัน)").
        upper_letters = re.findall(r"[A-Z]", ascii_only)
        if len(upper_letters) < 2:
            return False
    # Check if text starts with Thai (after trimming whitespace)
    if normalized_text and '\u0E00' <= normalized_text[0] <= '\u0E7F':
        # Text starts with Thai, skip ALL-CAPS English header detection
        pass  # Don't return True here
    else:
        # Text doesn't start with Thai, proceed with your current logic
        if (
            ascii_only
            and re.search(r'[A-Z]', ascii_only)
            and UPPER_SUB_RE.match(ascii_only)  # reasonably "header-like"
            and re.search(r'[A-Z]{2,}', ascii_only)  # at least one 2+ letter English word
        ):
            # NEW GUARD: only accept this ALL-CAPS path if first Latin letter is uppercase A–Z
            if first_latin_letter is not None and 'A' <= first_latin_letter <= 'Z':
                return True
            # else: fall through (don’t classify as header)

    # time-range header like "TELLING THE TIME: 12:01 - 12:09"
    if HEADER_WITH_COLON_RE.match(ascii_only):
        return True

    return False

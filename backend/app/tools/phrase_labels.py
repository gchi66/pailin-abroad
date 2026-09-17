"""Keep explanatory notes out of Thai phrase labels."""

import re


_TRAILING_USAGE_NOTE = re.compile(r"^(.+?)\s+\(?ใช้เมื่อ[^)]*\)?$")


def normalize_thai_phrase_label(value: str | None) -> str:
    label = (value or "").strip()
    match = _TRAILING_USAGE_NOTE.fullmatch(label)
    return match.group(1).strip() if match else label

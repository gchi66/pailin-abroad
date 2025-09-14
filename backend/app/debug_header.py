#!/usr/bin/env python3

import re

TH_RX = re.compile(r'[\u0E00-\u0E7F]')  # Thai block
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'''\-!?$%#\[\]:]{2,80}$")

def debug_header_detection(text):
    print(f"Original text: {repr(text)}")

    normalized_text = text.replace("\u200b", "").strip()
    print(f"Normalized: {repr(normalized_text)}")

    ascii_only = TH_RX.sub("", normalized_text).strip()
    print(f"ASCII only: {repr(ascii_only)}")

    has_uppercase = re.search(r'[A-Z]', ascii_only)
    print(f"Has uppercase: {bool(has_uppercase)}")

    matches_upper_sub = bool(UPPER_SUB_RE.match(ascii_only))
    print(f"Matches UPPER_SUB_RE: {matches_upper_sub}")

    consecutive_letters = re.search(r'[A-Z]{2,}', ascii_only)
    print(f"Has 2+ consecutive letters: {bool(consecutive_letters)}")
    if consecutive_letters:
        print(f"First match: {consecutive_letters.group()} at position {consecutive_letters.start()}")

    # Check all matches
    all_matches = list(re.finditer(r'[A-Z]{2,}', ascii_only))
    print(f"All consecutive letter matches: {[(m.group(), m.start()) for m in all_matches]}")

# Test the problematic text
problematic_text = "แฟรงค์บอกกับสาวๆว่าให้กลับมาตอน 12:00 จากเวลาที่แฟรงค์พูด เขาหมายถึง 12AM หรือ 12PM กันล่ะ?"

debug_header_detection(problematic_text)

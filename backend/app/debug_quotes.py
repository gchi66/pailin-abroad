#!/usr/bin/env python3

import re

UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&'''\-!?$%#\[\]:]{2,80}$")

test_text = "USES OF 'IS'  'is'"
print(f"Text: {repr(test_text)}")
print(f"Matches UPPER_SUB_RE: {bool(UPPER_SUB_RE.match(test_text))}")

# Let's check what characters are in the text
for i, char in enumerate(test_text):
    print(f"Position {i}: {repr(char)} (ord: {ord(char)})")
import json, re
from pathlib import Path

raw = json.loads(Path('/home/gchichester/code/pailin-abroad/backend/data/level_2_th_raw.json').read_text())

# find the Thai line paragraph for QP3 item 1
thai_line = None
style_line = None
for elem in raw.get('body', {}).get('content', []):
    para = elem.get('paragraph')
    if not para:
        continue
    text = ''.join(r.get('textRun', {}).get('content', '') for r in para.get('elements', []))
    text = text.replace('\u000b', '\n').strip()
    if text == 'มันแออัดในคอนเสิร์ตไหม?':
        thai_line = text
        style_line = para.get('paragraphStyle', {}).get('namedStyleType', '')
        break

print('thai_line:', thai_line)
print('style:', style_line)

TH_RX = re.compile(r'[\u0E00-\u0E7F]')
UPPER_SUB_RE = re.compile(r"^[A-Z0-9 ,.&/()++'‘’\-!?$%#\[\]:…]{2,80}$")
HEADER_WITH_COLON_RE = re.compile(r"^[A-Z][A-Z0-9 ,.&'‘’\-!?$%#]+: [0-9]{1,2}:[0-9]{2} ?- ?[0-9]{1,2}:[0-9]{2}$")
HEADER_TRAILING_VARIANT_RE = re.compile(r"\[\s*\d+\s*\]\s*$")
NON_HEADER_TOKENS_RE = re.compile(r"^I\s*\(\s*ฉัน\s*\)\s*$")

def is_subheader(text, style):
    normalized_text = text.replace("\u200b", "").strip()
    if NON_HEADER_TOKENS_RE.match(normalized_text):
        return False
    if style.startswith("HEADING_") and style not in {"HEADING_1","HEADING_2"}:
        print('subheader: style heading')
        return True
    if HEADER_TRAILING_VARIANT_RE.search(normalized_text):
        print('subheader: trailing variant')
        return True
    first_latin_letter = None
    for ch in normalized_text:
        if ch.isspace() or ch == "\u200b":
            continue
        if '\u0E00' <= ch <= '\u0E7F':
            continue
        if ('A' <= ch <= 'Z') or ('a' <= ch <= 'z'):
            first_latin_letter = ch
            break
    ascii_only = TH_RX.sub("", normalized_text).strip()
    has_thai = bool(TH_RX.search(normalized_text))
    if has_thai:
        upper_letters = re.findall(r"[A-Z]", ascii_only)
        print('ascii_only:', ascii_only, 'upper_letters', upper_letters)
        if len(upper_letters) < 2:
            print('subheader: has_thai but <2 upper letters -> False')
            return False
    if normalized_text and '\u0E00' <= normalized_text[0] <= '\u0E7F':
        pass
    else:
        if (
            ascii_only and re.search(r'[A-Z]', ascii_only)
            and UPPER_SUB_RE.match(ascii_only)
            and re.search(r'[A-Z]{2,}', ascii_only)
        ):
            if first_latin_letter is not None and 'A' <= first_latin_letter <= 'Z':
                print('subheader: all-caps heuristic')
                return True
    if HEADER_WITH_COLON_RE.match(ascii_only):
        print('subheader: header with colon')
        return True
    return False

print('is_subheader?', is_subheader(thai_line, style_line))

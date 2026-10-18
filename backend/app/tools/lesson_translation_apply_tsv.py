"""Apply Codex-authored TSV translations to a lesson translation manifest.

Each non-empty TSV line is ``UNIT_INDEX.PART_INDEX<TAB>THAI_TEXT``. Exact
duplicate source strings reuse an authored translation automatically, which
keeps repeated desktop/mobile lesson blocks consistent.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any


REQUIRED_ACTIONS = {"translate", "localize", "bilingual"}


def _read_tsv(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            key, translated = raw_line.split("\t", 1)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: expected key<TAB>translation") from exc
        if key in rows:
            raise ValueError(f"{path}:{line_number}: duplicate key {key}")
        rows[key] = translated.strip()
    return rows


def _read_blue_spans(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    rows: dict[str, list[str]] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            key, phrases = raw_line.split("\t", 1)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: expected key<TAB>phrase[|||phrase]") from exc
        rows[key] = [phrase for phrase in phrases.split("|||") if phrase]
    return rows


def apply_tsv(
    source: dict[str, Any], rows: dict[str, str], blue_spans: dict[str, list[str]] | None = None
) -> tuple[dict[str, Any], list[str]]:
    completed = copy.deepcopy(source)
    by_source: dict[str, str] = {}

    for key, translated in rows.items():
        unit_index_text, part_index_text = key.split(".", 1)
        part = completed["units"][int(unit_index_text)]["translation_parts"][int(part_index_text)]
        if part.get("recommended_action") not in REQUIRED_ACTIONS:
            raise ValueError(f"{key} does not require translation")
        # Exact key translations win. The first authored translation is only a
        # fallback for repeated desktop/mobile content whose key is omitted.
        by_source.setdefault(part["source_text"], translated)

    unused = set(rows)
    unused_blue = set(blue_spans or {})
    missing: list[str] = []
    for unit_index, unit in enumerate(completed["units"]):
        required = False
        complete = True
        for part_index, part in enumerate(unit.get("translation_parts", [])):
            if part.get("recommended_action") not in REQUIRED_ACTIONS:
                continue
            required = True
            key = f"{unit_index}.{part_index}"
            translated = rows.get(key) or by_source.get(part.get("source_text", ""))
            if not translated:
                missing.append(key)
                complete = False
                continue
            part["translated_text"] = translated
            phrases = (blue_spans or {}).get(key)
            if phrases:
                cursor = 0
                spans = []
                for phrase in phrases:
                    start = translated.find(phrase, cursor)
                    if start < 0:
                        raise ValueError(f"{key}: blue phrase not found in translation: {phrase!r}")
                    end = start + len(phrase)
                    spans.append(
                        {
                            "start": start,
                            "end": end,
                            "text": phrase,
                            "style": {
                                "foregroundColor": {"color": {"rgbColor": {"blue": 1}}},
                                "weightedFontFamily": {"fontFamily": "Work Sans", "weight": 400},
                            },
                        }
                    )
                    cursor = end
                part["translated_style_spans"] = spans
                unused_blue.discard(key)
            unused.discard(key)
        if required:
            unit["translation"]["status"] = "complete" if complete else "pending"

    if unused:
        raise ValueError(f"TSV contains unknown or unused keys: {sorted(unused)[:10]}")
    if unused_blue:
        raise ValueError(f"Blue-span TSV contains unknown or unused keys: {sorted(unused_blue)[:10]}")
    return completed, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Codex-authored TSV lesson translations.")
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--translations", required=True, type=Path)
    parser.add_argument("--blue-spans", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    source = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    completed, missing = apply_tsv(
        source, _read_tsv(args.translations), _read_blue_spans(args.blue_spans)
    )
    args.out.write_text(json.dumps(completed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}; {len(missing)} required parts remain untranslated.")


if __name__ == "__main__":
    main()

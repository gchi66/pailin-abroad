"""exercise_parser.py – Google Docs → Exercise Bank JSON
──────────────────────────────────────────────────────────

Parses structured exercise-bank Google Docs into a bilingual JSON format.
Run once for English content and once for Thai content:

    python -m app.tools.exercise_parser <doc_id> --lang en --output exercise_bank.json
    python -m app.tools.exercise_parser <doc_id> --lang th --output exercise_bank_th.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

try:  # pragma: no cover - allow running outside package context
    from .docs_fetch import fetch_doc
    from .docwalker import paragraph_nodes
    from . import docwalker as docwalker_module
    from .excercise_textutils import is_subheader as exercise_is_subheader
except ImportError:  # pragma: no cover
    from backend.app.tools.docs_fetch import fetch_doc  # type: ignore
    from backend.app.tools.docwalker import paragraph_nodes  # type: ignore
    from backend.app.tools import docwalker as docwalker_module  # type: ignore
    from backend.app.tools.excercise_textutils import is_subheader as exercise_is_subheader  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
OPTION_RE = re.compile(r"^[A-Z]\.\s")


def _clean_text(value: str) -> str:
    if not value:
        return ""
    replacements = {
        "“": '"',
        "”": '"',
        "„": '"',
        "«": '"',
        "»": '"',
        "‘": "'",
        "’": "'",
        "´": "'",
        "—": "-",
        "–": "-",
        "\u00a0": " ",
    }
    out = value
    for src, dst in replacements.items():
        out = out.replace(src, dst)
    return out.strip()


def _split_lines(text: str) -> List[str]:
    if not text:
        return []
    return [_clean_text(part) for part in re.split(r"[\r\n]+", text) if _clean_text(part)]


def _split_en_th(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    match = THAI_RE.search(text)
    if not match:
        return text.strip(), ""
    idx = match.start()
    en = text[:idx].strip()
    th = text[idx:].strip()
    return en, th


def _append_text(current: str, addition: str) -> str:
    current = current or ""
    addition = addition.strip()
    if not addition:
        return current
    if not current:
        return addition
    return f"{current}\n{addition}"


class ExerciseParser:
    def __init__(self) -> None:
        pass

    def parse_exercise_document(self, document_id: str, lang: str = "en") -> List[Dict[str, Any]]:
        lang = (lang or "en").lower()
        if lang not in {"en", "th"}:
            raise ValueError("lang must be 'en' or 'th'")

        logger.info("Parsing exercise document %s (lang=%s)", document_id, lang)

        doc_json = fetch_doc(document_id)
        if not doc_json:
            logger.error("Failed to fetch document %s", document_id)
            return []

        original_is_subheader = getattr(docwalker_module, "is_subheader", None)
        docwalker_module.is_subheader = exercise_is_subheader

        try:
            entries: List[Dict[str, str]] = []
            for elem in doc_json.get("body", {}).get("content", []):
                if "paragraph" not in elem:
                    continue

                para_nodes = list(
                    paragraph_nodes(
                        {
                            "body": {"content": [elem]},
                            "lists": doc_json.get("lists", {}),
                        }
                    )
                )
                for node in para_nodes:
                    node_dict = dataclasses.asdict(node)
                    for inline in node_dict.get("inlines", []):
                        inline.pop("link", None)

                    text = "".join(inline.get("text", "") for inline in node_dict.get("inlines", []))
                    if not text:
                        continue

                    is_heading = node_dict.get("kind") == "heading"
                    style_name = node_dict.get("style") or ""

                    pieces = _split_lines(text)
                    for index, piece in enumerate(pieces):
                        entry_type = "heading" if is_heading and index == 0 else "line"
                        upper_piece = piece.upper()
                        if entry_type == "heading":
                            if not exercise_is_subheader(piece, style_name):
                                entry_type = "line"
                        if entry_type == "heading" and re.match(
                            r"^(SECTION|CATEGORY|DESCRIPTION|TYPE|TITLE|PROMPT|PARAGRAPH|ITEM|QUESTION|TEXT|STEM|ANSWER|OPTIONS|KEYWORDS|TRANSLATION)",
                            upper_piece,
                        ):
                            entry_type = "line"
                        entries.append({"type": entry_type, "text": piece})

            sections: List[Dict[str, Any]] = []
            current_section: Optional[Dict[str, Any]] = None
            current_exercise: Optional[Dict[str, Any]] = None
            current_item: Optional[Dict[str, Any]] = None
            sort_order = 0
            pending_context: Optional[str] = None  # e.g., 'section_description', 'exercise_title', 'item_text'

            def flush_item() -> None:
                nonlocal current_item, current_exercise, pending_context
                if current_item is None or current_exercise is None:
                    current_item = None
                    pending_context = None
                    return

                kind = current_item["kind"]
                number = current_item["number"]
                text = _clean_text(current_item.get("text", ""))
                answers = current_item.get("answers", [])

                if kind == "fill_blank":
                    payload = {
                        "number": number,
                        "text": text,
                        "answer": ", ".join(answers),
                    }
                elif kind == "sentence_transform":
                    payload = {
                        "number": number,
                        "text": text,
                        "correct": current_item.get("correct") or "",
                        "answer": ", ".join(answers),
                    }
                elif kind == "multiple_choice":
                    payload = {
                        "number": number,
                        "text": text,
                        "options": current_item.get("options", []),
                        "answer": current_item.get("answer") or "",
                    }
                else:  # open-ended
                    payload = {
                        "number": number,
                        "text": text,
                        "keywords": ", ".join(current_item.get("keywords", [])),
                    }

                target_list = current_exercise["items_th"] if lang == "th" else current_exercise["items"]
                target_list.append(payload)
                current_item = None
                pending_context = None

            def finalise_exercise(exercise: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "kind": exercise["kind"],
                    "title": {
                        "en": exercise["title_en"],
                        "th": exercise["title_th"],
                    },
                    "prompt": {
                        "en": exercise["prompt_en"],
                        "th": exercise["prompt_th"],
                    },
                    "paragraph": {
                        "en": exercise["paragraph_en"],
                        "th": exercise["paragraph_th"],
                    },
                    "items": exercise["items"],
                    "items_th": exercise["items_th"],
                    "sort_order": exercise["sort_order"],
                    "is_featured": exercise["is_featured"],
                }

            def flush_exercise() -> None:
                nonlocal current_exercise, current_section, current_item, pending_context
                flush_item()
                if current_exercise is None or current_section is None:
                    current_exercise = None
                    return

                if current_exercise["items"] or current_exercise["items_th"]:
                    current_section["exercises"].append(finalise_exercise(current_exercise))
                current_exercise = None
                pending_context = None

            def flush_section() -> None:
                nonlocal current_section, sort_order, pending_context
                flush_exercise()
                if current_section is None:
                    return

                if current_section["exercises"]:
                    sections.append(current_section)
                current_section = None
                sort_order = 0
                pending_context = None

            for entry in entries:
                line = entry["text"]
                upper = line.upper()

                if upper.startswith("SECTION:"):
                    flush_section()
                    en_title, th_title = _split_en_th(line.split(":", 1)[1].strip())
                    current_section = {
                        "category": "",
                        "section": {
                            "title_en": en_title if lang == "en" else en_title,
                            "title_th": th_title if th_title else (line.split(":", 1)[1].strip() if lang == "th" else ""),
                            "description": "",
                        },
                        "exercises": [],
                    }
                    pending_context = None
                    continue

                if entry["type"] == "heading":
                    flush_section()
                    en_title, th_title = _split_en_th(line)
                    if lang == "th" and not th_title and THAI_RE.search(line):
                        th_title = line
                    if lang == "en" and not en_title:
                        en_title = line
                    current_section = {
                        "category": "",
                        "section": {
                            "title_en": en_title,
                            "title_th": th_title,
                            "description": "",
                        },
                        "exercises": [],
                    }
                    pending_context = None
                    continue

                if current_section is None:
                    logger.debug("Skipping line outside any section: %s", line)
                    continue

                if upper.startswith("DESCRIPTION:"):
                    current_section["section"]["description"] = _append_text(
                        current_section["section"]["description"],
                        line.split(":", 1)[1].strip(),
                    )
                    pending_context = "section_description"
                    continue

                if upper.startswith("CATEGORY:"):
                    current_section["category"] = line.split(":", 1)[1].strip()
                    pending_context = None
                    continue

                if upper.startswith("TYPE:"):
                    flush_exercise()
                    exercise_type = line.split(":", 1)[1].strip().lower()
                    sort_order += 1
                    current_exercise = {
                        "kind": exercise_type,
                        "title_en": "",
                        "title_th": "",
                        "prompt_en": "",
                        "prompt_th": "",
                        "paragraph_en": "",
                        "paragraph_th": "",
                        "items": [],
                        "items_th": [],
                        "sort_order": sort_order,
                        "is_featured": False,
                    }
                    current_section["exercises"]  # ensure list
                    pending_context = None
                    current_item = None
                    continue

                if current_exercise is None:
                    logger.debug("Ignoring line outside exercise block: %s", line)
                    continue

                if upper.startswith("TITLE:"):
                    value = line.split(":", 1)[1].strip()
                    en_title, th_title = _split_en_th(value)
                    if lang == "th":
                        current_exercise["title_en"] = en_title
                        current_exercise["title_th"] = th_title if th_title else value
                        pending_context = "exercise_title_th"
                    else:
                        current_exercise["title_en"] = en_title if en_title else value
                        current_exercise["title_th"] = th_title
                        pending_context = "exercise_title_en"
                    continue

                if upper.startswith("PROMPT:"):
                    value = line.split(":", 1)[1].strip()
                    if lang == "th":
                        current_exercise["prompt_th"] = value
                        pending_context = "exercise_prompt_th"
                    else:
                        current_exercise["prompt_en"] = value
                        pending_context = "exercise_prompt_en"
                    continue

                if upper.startswith("PARAGRAPH:"):
                    value = line.split(":", 1)[1].strip()
                    if lang == "th":
                        current_exercise["paragraph_th"] = value
                        pending_context = "exercise_paragraph_th"
                    else:
                        current_exercise["paragraph_en"] = value
                        pending_context = "exercise_paragraph_en"
                    continue

                if upper.startswith(("ITEM:", "QUESTION:")):
                    flush_item()
                    number = line.split(":", 1)[1].strip()
                    current_item = {
                        "kind": current_exercise["kind"],
                        "number": number,
                        "text": "",
                        "answers": [],
                        "options": [],
                        "answer": "",
                        "correct": "",
                        "keywords": [],
                    }
                    pending_context = None
                    continue

                if current_item is None:
                    logger.debug("Line without active item: %s", line)
                    continue

                if upper.startswith(("TEXT:", "STEM:")):
                    value = line.split(":", 1)[1].strip()
                    current_item["text"] = value
                    pending_context = "item_text"
                    continue

                if upper.startswith("TRANSLATION:"):
                    current_item["text"] = _append_text(current_item["text"], line.split(":", 1)[1].strip())
                    pending_context = "item_text"
                    continue

                if upper.startswith("ANSWER:"):
                    answer_val = line.split(":", 1)[1].strip()
                    if current_exercise["kind"] == "multiple_choice":
                        current_item["answer"] = answer_val
                    else:
                        current_item["answers"].extend([piece.strip() for piece in answer_val.split(",") if piece.strip()])
                    pending_context = None
                    continue

                if upper.startswith("CORRECT:"):
                    current_item["correct"] = line.split(":", 1)[1].strip().lower()
                    pending_context = None
                    continue

                if upper.startswith("KEYWORDS:"):
                    keywords = [piece.strip() for piece in line.split(":", 1)[1].split(",") if piece.strip()]
                    current_item["keywords"].extend(keywords)
                    pending_context = "item_keywords"
                    continue

                if upper.startswith("OPTIONS:"):
                    options_raw = line.split(":", 1)[1].strip()
                    options = [opt.strip() for opt in re.split(r"\s*\|\s*|\s{2,}", options_raw) if opt.strip()]
                    current_item["options"].extend(options)
                    pending_context = "item_options"
                    continue

                if OPTION_RE.match(line):
                    current_item["options"].append(line.strip())
                    pending_context = "item_options"
                    continue

                # Handle continuation / translation lines for last directive.
                if pending_context == "section_description":
                    current_section["section"]["description"] = _append_text(
                        current_section["section"]["description"],
                        line,
                    )
                    continue

                if pending_context == "exercise_title_th":
                    current_exercise["title_th"] = _append_text(current_exercise["title_th"], line)
                    continue
                if pending_context == "exercise_title_en":
                    current_exercise["title_en"] = _append_text(current_exercise["title_en"], line)
                    continue
                if pending_context == "exercise_prompt_th":
                    current_exercise["prompt_th"] = _append_text(current_exercise["prompt_th"], line)
                    continue
                if pending_context == "exercise_prompt_en":
                    current_exercise["prompt_en"] = _append_text(current_exercise["prompt_en"], line)
                    continue
                if pending_context == "exercise_paragraph_th":
                    current_exercise["paragraph_th"] = _append_text(current_exercise["paragraph_th"], line)
                    continue
                if pending_context == "exercise_paragraph_en":
                    current_exercise["paragraph_en"] = _append_text(current_exercise["paragraph_en"], line)
                    continue
                if pending_context == "item_text":
                    current_item["text"] = _append_text(current_item["text"], line)
                    continue
                if pending_context == "item_keywords":
                    current_item["keywords"].append(line.strip())
                    continue
                if pending_context == "item_options":
                    current_item["options"].append(line.strip())
                    continue

                # Fallback: append to item text
                current_item["text"] = _append_text(current_item["text"], line)
                pending_context = "item_text"

            flush_section()

            logger.info("Finished parsing %d sections.", len(sections))
            return sections
        finally:
            if original_is_subheader is not None:
                docwalker_module.is_subheader = original_is_subheader


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse exercise bank Google Docs into JSON.")
    parser.add_argument("document_id", help="Google Docs document ID")
    parser.add_argument("--output", help="File to write parsed JSON (default: stdout)")
    parser.add_argument("--raw-output", help="File to write raw Google Docs JSON (optional)")
    parser.add_argument("--lang", choices=["en", "th"], default="en", help="Document language (default: en)")
    args = parser.parse_args()

    try:
        exercise_parser = ExerciseParser()

        if args.raw_output:
            raw_doc = fetch_doc(args.document_id)
            with open(args.raw_output, "w", encoding="utf-8") as fh:
                json.dump(raw_doc, fh, ensure_ascii=False, indent=2)
            logger.info("Wrote raw document JSON to %s", args.raw_output)

        result = exercise_parser.parse_exercise_document(args.document_id, lang=args.lang)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, indent=2)
            logger.info("Wrote parsed exercises to %s", args.output)
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as exc:  # pragma: no cover
        logger.error("Exercise parsing failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

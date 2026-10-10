"""Populate a lesson translation manifest with structured English-to-Thai output.

This tool only writes a local manifest. It never calls the Google Docs API.
Progress is saved after every batch, so an interrupted run can be resumed by
passing the same path as ``--resume`` and ``--out``.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


REQUIRED_ACTIONS = {"translate", "localize", "bilingual"}
DEFAULT_MODEL = os.getenv("LESSON_TRANSLATION_MODEL", "gpt-4o")
PROMPT_VERSION = "lesson-thai-translation-v1"

SYSTEM_PROMPT = """You are translating English-learning lesson material for Thai learners.
Return only the structured translations requested by the response schema.

The source is authoritative. Do not correct, normalize, or silently repair any typo,
grammar error, repetition, punctuation, capitalization, spacing, or odd wording. Some
errors are intentional teaching material.

Translate naturally into contemporary Thai suitable for an educational app. Preserve
tone, humor, hesitation, speaker intent, and meaning. Do not add explanations that are
not in the source.

Each item has one action:
- bilingual: write only the Thai companion text. Do not copy the English source or any
  audio/image/parser token; the writer retains the English source separately.
- translate: write a Thai replacement.
- localize: write a Thai replacement while retaining every protected English span
  exactly as supplied.

For translate/localize items, reproduce every protected token exactly and once. These
may include audio markers, blanks, URLs, image keys, or parser directives. Never wrap
output in Markdown, XML, labels, or commentary. Preserve exercise labels, speaker
identity, and placeholders when they are meaningful. Use established Thai character
names where applicable: Pailin = ไพลิน, Chloe = โคลอี้, Tyler = ไทเลอร์.
"""


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def _part_key(unit_id: str, part_id: str) -> str:
    return f"{unit_id}::{part_id}"


def _translation_parts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for unit in manifest.get("units", []):
        for part in unit.get("translation_parts", []):
            if part.get("recommended_action") not in REQUIRED_ACTIONS:
                continue
            result.append(
                {
                    "key": _part_key(unit["unit_id"], part["part_id"]),
                    "unit_id": unit["unit_id"],
                    "part_id": part["part_id"],
                    "lesson_id": unit.get("lesson_id"),
                    "section": unit.get("section"),
                    "role": unit.get("role"),
                    "action": part.get("recommended_action"),
                    "source_text": part.get("source_text", ""),
                    "protected_tokens": [
                        token.get("text") for token in part.get("protected_tokens", [])
                    ],
                    "protected_english_spans": part.get(
                        "protected_english_spans", []
                    ),
                    "translated_text": part.get("translated_text"),
                }
            )
    return result


def _pending_batches(
    manifest: dict[str, Any], *, max_source_chars: int
) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    batch: list[dict[str, Any]] = []
    size = 0
    for part in _translation_parts(manifest):
        if isinstance(part.get("translated_text"), str) and part["translated_text"].strip():
            continue
        part_size = len(part["source_text"])
        if batch and size + part_size > max_source_chars:
            batches.append(batch)
            batch = []
            size = 0
        batch.append({key: value for key, value in part.items() if key != "translated_text"})
        size += part_size
    if batch:
        batches.append(batch)
    return batches


def _response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "lesson_translations",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "translations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "translated_text": {"type": "string"},
                            },
                            "required": ["key", "translated_text"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["translations"],
                "additionalProperties": False,
            },
        },
    }


def _translate_batch(
    batch: list[dict[str, Any]],
    *,
    client: OpenAI,
    model: str,
) -> dict[str, str]:
    payload = {
        "prompt_version": PROMPT_VERSION,
        "instruction": (
            "Translate every item. Return exactly one result for each key and no extra keys. "
            "Use neighboring items in this ordered batch as lesson context."
        ),
        "items": batch,
    }
    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format=_response_format(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    raw = completion.choices[0].message.content or ""
    response = json.loads(raw)
    rows = response.get("translations")
    if not isinstance(rows, list):
        raise ValueError("Translation response has no translations array")

    expected = {item["key"] for item in batch}
    translated: dict[str, str] = {}
    for row in rows:
        key = row.get("key")
        text = row.get("translated_text")
        if key in translated:
            raise ValueError(f"Translation response duplicated key {key!r}")
        if key not in expected:
            raise ValueError(f"Translation response returned unexpected key {key!r}")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Translation response returned empty text for {key!r}")
        translated[key] = text.strip()
    if set(translated) != expected:
        missing = sorted(expected - set(translated))
        raise ValueError(f"Translation response omitted keys: {missing!r}")
    return translated


def _apply_translations(manifest: dict[str, Any], translations: dict[str, str]) -> None:
    for unit in manifest.get("units", []):
        required = False
        complete = True
        for part in unit.get("translation_parts", []):
            if part.get("recommended_action") not in REQUIRED_ACTIONS:
                continue
            required = True
            key = _part_key(unit["unit_id"], part["part_id"])
            if key in translations:
                part["translated_text"] = translations[key]
            if not isinstance(part.get("translated_text"), str) or not part[
                "translated_text"
            ].strip():
                complete = False
        unit["translation"]["status"] = (
            "complete" if required and complete else "pending" if required else "not_required"
        )


def generate_translations(
    source_manifest: dict[str, Any],
    *,
    client: OpenAI,
    model: str,
    max_source_chars: int = 5000,
    retries: int = 3,
    progress_callback: Any | None = None,
) -> dict[str, Any]:
    manifest = copy.deepcopy(source_manifest)
    batches = _pending_batches(manifest, max_source_chars=max_source_chars)
    for index, batch in enumerate(batches, start=1):
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                translations = _translate_batch(batch, client=client, model=model)
                _apply_translations(manifest, translations)
                last_error = None
                break
            except Exception as exc:  # API and model-output failures are retryable.
                last_error = exc
                if attempt < retries:
                    time.sleep(min(2**attempt, 8))
        if last_error is not None:
            raise RuntimeError(
                f"Translation batch {index}/{len(batches)} failed after {retries} attempts"
            ) from last_error
        if progress_callback:
            progress_callback(manifest, index, len(batches), len(batch))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a completed Thai lesson manifest.")
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-source-chars", type=int, default=5000)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    load_dotenv()
    source = _read_json(args.source_manifest)
    working = _read_json(args.resume) if args.resume and args.resume.exists() else source

    # Confirm a resume file still represents the exact immutable source before
    # paying for more translations.
    if args.resume and args.resume.exists():
        from .lesson_translation_validator import validate_manifest

        resume_result = validate_manifest(working, source_manifest=source)
        immutable_errors = [
            issue
            for issue in resume_result["issues"]
            if issue["code"]
            not in {"missing-translation", "translation-status-mismatch"}
        ]
        if immutable_errors:
            raise ValueError(f"Resume manifest is incompatible: {immutable_errors[:3]!r}")

    pending = _pending_batches(working, max_source_chars=args.max_source_chars)
    pending_count = sum(len(batch) for batch in pending)
    print(
        f"Generating {pending_count} translation parts in {len(pending)} batch(es) "
        f"with {args.model}."
    )

    def save_progress(
        manifest: dict[str, Any], batch_index: int, batch_count: int, batch_size: int
    ) -> None:
        _write_json_atomic(args.out, manifest)
        print(f"Saved batch {batch_index}/{batch_count} ({batch_size} parts).", flush=True)

    completed = generate_translations(
        working,
        client=OpenAI(api_key=os.getenv("OPENAI_API_KEY")),
        model=args.model,
        max_source_chars=args.max_source_chars,
        retries=args.retries,
        progress_callback=save_progress,
    )
    _write_json_atomic(args.out, completed)
    print(f"Wrote completed translation manifest to {args.out}")


if __name__ == "__main__":
    main()

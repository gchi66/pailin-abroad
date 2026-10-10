"""Validate a completed Thai lesson translation manifest without writing Docs.

Only ``translation_parts[*].translated_text``, optional translated inline-style
spans, and the derived top-level ``translation.status`` may differ. All
source text, actions, Google Docs ranges, styles, tokens, and structure remain
immutable.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .lesson_translation_manifest import _protected_tokens


THAI_RE = re.compile(r"[\u0E00-\u0E7F]")
MARKDOWN_FENCE_RE = re.compile(r"```|~~~")
INTERNAL_MARKER_RE = re.compile(
    r"(?:<\/?(?:translate|translation|segment|style|unit)(?:\s[^>]*)?>|"
    r"\b(?:unit_id|recommended_action|translated_text)\b\s*[:=])",
    re.IGNORECASE,
)
REQUIRED_ACTIONS = {"translate", "localize", "bilingual"}
NO_TRANSLATION_ACTIONS = {"preserve", "remove"}


def _issue(
    issues: list[dict[str, Any]],
    *,
    severity: str,
    code: str,
    message: str,
    unit_id: str | None = None,
    part_id: str | None = None,
) -> None:
    issues.append(
        {
            "severity": severity,
            "code": code,
            "unit_id": unit_id,
            "part_id": part_id,
            "message": message,
        }
    )


def _immutable_manifest_header(manifest: dict[str, Any]) -> dict[str, Any]:
    immutable = copy.deepcopy(manifest)
    immutable.pop("units", None)
    return immutable


def _immutable_unit(unit: dict[str, Any]) -> dict[str, Any]:
    immutable = copy.deepcopy(unit)
    immutable.get("translation", {}).pop("status", None)
    for part in immutable.get("translation_parts", []):
        part.pop("translated_text", None)
        part.pop("translated_style_spans", None)
    return immutable


def _token_inventory(tokens: list[dict[str, Any]]) -> Counter[tuple[str, str]]:
    return Counter((token.get("kind", ""), token.get("text", "")) for token in tokens)


def _reconstruct_source(parts: list[dict[str, Any]]) -> str:
    return "".join(
        f"{part.get('source_text', '')}{part.get('separator_after', '')}" for part in parts
    )


def _translation_required(part: dict[str, Any]) -> bool:
    return part.get("recommended_action") in REQUIRED_ACTIONS


def _validate_part(
    part: dict[str, Any],
    *,
    unit_id: str,
    issues: list[dict[str, Any]],
) -> bool:
    part_id = part.get("part_id")
    action = part.get("recommended_action")
    translated = part.get("translated_text")
    source = part.get("source_text", "")
    preserve_source = bool(part.get("preserve_source_in_output"))
    valid = True

    if action not in REQUIRED_ACTIONS | NO_TRANSLATION_ACTIONS:
        _issue(
            issues,
            severity="error",
            code="invalid-part-action",
            unit_id=unit_id,
            part_id=part_id,
            message=f"Unsupported translation-part action {action!r}.",
        )
        return False

    if action in NO_TRANSLATION_ACTIONS:
        if translated not in {None, ""}:
            _issue(
                issues,
                severity="error",
                code="unexpected-translation",
                unit_id=unit_id,
                part_id=part_id,
                message=f"{action} parts must not contain translated text.",
            )
            return False
        return True

    if not isinstance(translated, str) or not translated.strip():
        _issue(
            issues,
            severity="error",
            code="missing-translation",
            unit_id=unit_id,
            part_id=part_id,
            message="Required Thai translation is empty.",
        )
        return False

    for span in part.get("translated_style_spans", []):
        start = span.get("start")
        end = span.get("end")
        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end <= start
            or end > len(translated)
            or (
                span.get("text") is not None
                and translated[start:end] != span.get("text")
            )
            or not isinstance(span.get("style"), dict)
            or not span.get("style")
        ):
            valid = False
            _issue(
                issues,
                severity="error",
                code="invalid-translated-style-span",
                unit_id=unit_id,
                part_id=part_id,
                message="Translated inline-style span has an invalid range, text, or style.",
            )

    if not THAI_RE.search(translated):
        valid = False
        _issue(
            issues,
            severity="error",
            code="thai-script-missing",
            unit_id=unit_id,
            part_id=part_id,
            message="Translation contains no Thai-script character.",
        )

    if MARKDOWN_FENCE_RE.search(translated) or INTERNAL_MARKER_RE.search(translated):
        valid = False
        _issue(
            issues,
            severity="error",
            code="control-artifact",
            unit_id=unit_id,
            part_id=part_id,
            message="Translation contains Markdown fencing or an internal manifest marker.",
        )

    source_tokens = part.get("protected_tokens", [])
    translated_tokens = _protected_tokens(translated)
    source_inventory = _token_inventory(source_tokens)
    translated_inventory = _token_inventory(translated_tokens)

    if preserve_source:
        # Tokens remain safely attached to the exact retained source. Repeating
        # them in Thai would duplicate audio, images, blanks, or directives.
        forbidden_kinds = {
            "audio",
            "image",
            "header_image",
            "blank",
            "url",
            "parser_directive",
        }
        repeated = [
            token
            for token in translated_tokens
            if token.get("kind") in forbidden_kinds
        ]
        if repeated:
            valid = False
            _issue(
                issues,
                severity="error",
                code="duplicated-protected-token",
                unit_id=unit_id,
                part_id=part_id,
                message=f"Thai companion repeats protected source tokens: {repeated!r}.",
            )
    elif translated_inventory != source_inventory:
        valid = False
        _issue(
            issues,
            severity="error",
            code="protected-token-mismatch",
            unit_id=unit_id,
            part_id=part_id,
            message=(
                "Localized replacement must preserve the exact protected-token inventory: "
                f"expected={dict(source_inventory)!r}, actual={dict(translated_inventory)!r}."
            ),
        )

    if not preserve_source:
        missing_english = [
            span
            for span in part.get("protected_english_spans", [])
            if span not in translated
        ]
        if missing_english:
            valid = False
            _issue(
                issues,
                severity="error",
                code="protected-english-missing",
                unit_id=unit_id,
                part_id=part_id,
                message=(
                    "Localized replacement dropped English teaching text that must remain "
                    f"exact: {missing_english!r}."
                ),
            )

    if preserve_source and len(source.strip()) >= 8 and source.strip() in translated:
        valid = False
        _issue(
            issues,
            severity="error",
            code="source-duplicated-in-translation",
            unit_id=unit_id,
            part_id=part_id,
            message="Thai companion repeats the complete English source; the writer retains it separately.",
        )

    return valid


def validate_manifest(
    manifest: dict[str, Any],
    *,
    source_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    if manifest.get("schema_version") != 1:
        _issue(
            issues,
            severity="error",
            code="unsupported-schema",
            message=f"Expected schema_version 1, got {manifest.get('schema_version')!r}.",
        )

    if source_manifest is not None:
        if _immutable_manifest_header(manifest) != _immutable_manifest_header(source_manifest):
            _issue(
                issues,
                severity="error",
                code="source-header-mutated",
                message="Immutable source metadata, inventory, selection, or removal plan changed.",
            )

    units = manifest.get("units")
    if not isinstance(units, list):
        _issue(
            issues,
            severity="error",
            code="units-missing",
            message="Manifest units must be an array.",
        )
        units = []

    source_units = source_manifest.get("units", []) if source_manifest else []
    if source_manifest is not None and len(units) != len(source_units):
        _issue(
            issues,
            severity="error",
            code="unit-count-mutated",
            message=f"Expected {len(source_units)} units, got {len(units)}.",
        )

    ids = [unit.get("unit_id") for unit in units]
    source_ids = [unit.get("unit_id") for unit in source_units]
    if source_manifest is not None and ids != source_ids:
        _issue(
            issues,
            severity="error",
            code="unit-order-mutated",
            message="Unit IDs or their source order differ from the source manifest.",
        )
    duplicates = sorted(unit_id for unit_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        _issue(
            issues,
            severity="error",
            code="duplicate-unit-id",
            message=f"Duplicate unit IDs: {duplicates!r}.",
        )

    source_by_id = {
        unit.get("unit_id"): unit for unit in source_units if unit.get("unit_id") is not None
    }
    completed_parts = 0
    required_parts = 0
    action_counts: Counter[str] = Counter()

    for unit in units:
        unit_id = unit.get("unit_id")
        action = unit.get("recommended_action")
        action_counts[action] += 1

        if source_manifest is not None:
            source_unit = source_by_id.get(unit_id)
            if source_unit is None:
                _issue(
                    issues,
                    severity="error",
                    code="unexpected-unit",
                    unit_id=unit_id,
                    message="Unit does not exist in the source manifest.",
                )
            elif _immutable_unit(unit) != _immutable_unit(source_unit):
                _issue(
                    issues,
                    severity="error",
                    code="source-unit-mutated",
                    unit_id=unit_id,
                    message="Source text, classification, structure, range, style, or token data changed.",
                )

        parts = unit.get("translation_parts")
        if not isinstance(parts, list) or not parts:
            _issue(
                issues,
                severity="error",
                code="translation-parts-missing",
                unit_id=unit_id,
                message="Unit has no translation parts.",
            )
            continue

        reconstructed = _reconstruct_source(parts)
        if reconstructed != unit.get("source_text"):
            _issue(
                issues,
                severity="error",
                code="part-source-mismatch",
                unit_id=unit_id,
                message="Translation parts do not reconstruct the authoritative source text exactly.",
            )

        part_actions = {part.get("recommended_action") for part in parts}
        if action == "mixed" and len(part_actions) < 2:
            _issue(
                issues,
                severity="error",
                code="mixed-action-invalid",
                unit_id=unit_id,
                message="Mixed unit must contain at least two distinct part actions.",
            )
        elif action != "mixed" and part_actions != {action}:
            _issue(
                issues,
                severity="error",
                code="unit-part-action-mismatch",
                unit_id=unit_id,
                message=f"Unit action {action!r} does not match part actions {part_actions!r}.",
            )

        unit_complete = True
        for part in parts:
            if _translation_required(part):
                required_parts += 1
            part_valid = _validate_part(part, unit_id=unit_id, issues=issues)
            if _translation_required(part) and part_valid:
                completed_parts += 1
            if not part_valid:
                unit_complete = False

        expected_status = (
            "not_required"
            if all(part.get("recommended_action") in NO_TRANSLATION_ACTIONS for part in parts)
            else ("complete" if unit_complete else "pending")
        )
        actual_status = unit.get("translation", {}).get("status")
        if actual_status != expected_status:
            _issue(
                issues,
                severity="error",
                code="translation-status-mismatch",
                unit_id=unit_id,
                message=f"Expected translation.status={expected_status!r}, got {actual_status!r}.",
            )

    if source_manifest is not None:
        completed_ids = set(ids)
        missing_ids = [unit_id for unit_id in source_by_id if unit_id not in completed_ids]
        if missing_ids:
            _issue(
                issues,
                severity="error",
                code="missing-units",
                message=f"Missing source unit IDs: {missing_ids!r}.",
            )

    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    return {
        "valid": error_count == 0,
        "source": manifest.get("source"),
        "selection": manifest.get("selection"),
        "summary": {
            "unit_count": len(units),
            "required_translation_part_count": required_parts,
            "completed_translation_part_count": completed_parts,
            "error_count": error_count,
            "warning_count": warning_count,
            "action_counts": dict(sorted(action_counts.items(), key=lambda item: str(item[0]))),
        },
        "issues": issues,
    }


def render_validation_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    source = result.get("source", {})
    lines = [
        "# Thai translation manifest validation report",
        "",
        f"- Result: **{'PASS' if result['valid'] else 'FAIL'}**",
        f"- Document: `{source.get('title')}`",
        f"- Document ID: `{source.get('document_id')}`",
        f"- Lesson selection: `{result.get('selection', {}).get('lesson') or 'all'}`",
        f"- Units: {summary['unit_count']}",
        (
            "- Required translation parts completed: "
            f"{summary['completed_translation_part_count']}/"
            f"{summary['required_translation_part_count']}"
        ),
        f"- Errors: {summary['error_count']}",
        f"- Warnings: {summary['warning_count']}",
        "",
        "## Issues",
        "",
    ]

    if not result["issues"]:
        lines.append("None.")
    else:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for issue in result["issues"]:
            grouped[issue["code"]].append(issue)
        max_examples_per_code = 20
        for code, issues in sorted(grouped.items()):
            lines.append(f"### `{code}` ({len(issues)})")
            lines.append("")
            for issue in issues[:max_examples_per_code]:
                location = " / ".join(
                    value
                    for value in (issue.get("unit_id"), issue.get("part_id"))
                    if value
                )
                prefix = f"`{location}`: " if location else ""
                lines.append(f"- {prefix}{issue['message']}")
            omitted = len(issues) - max_examples_per_code
            if omitted > 0:
                lines.append(f"- … {omitted} additional issue(s) are in the JSON report.")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a completed Thai lesson translation manifest."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--json-report", type=Path)
    args = parser.parse_args()

    manifest = _read_json(args.manifest)
    source_manifest = _read_json(args.source_manifest)
    result = validate_manifest(manifest, source_manifest=source_manifest)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_validation_report(result), encoding="utf-8")
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        f"Validation {'passed' if result['valid'] else 'failed'}: "
        f"{result['summary']['completed_translation_part_count']}/"
        f"{result['summary']['required_translation_part_count']} translation parts complete, "
        f"{result['summary']['error_count']} errors"
    )
    raise SystemExit(0 if result["valid"] else 2)


if __name__ == "__main__":
    main()

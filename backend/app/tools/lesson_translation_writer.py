"""Plan and optionally apply a validated Thai manifest to a Google Doc copy.

Dry-run is the default. A write requires ``--execute`` plus an exact destination
allowlist match. Requests are grouped and applied from later document indexes to
earlier ones, with a required revision ID to reject concurrent edits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .lesson_translation_manifest import _protected_tokens
from .lesson_translation_validator import render_validation_report, validate_manifest


REQUIRED_ACTIONS = {"translate", "localize", "bilingual"}
INLINE_BILINGUAL_ROLES = {
    "lesson_heading",
    "instructional_subheading",
    "phrase_heading",
    "practice_title",
    "phrase_term_audio",
}
WRITABLE_TEXT_STYLE_FIELDS = {
    "backgroundColor",
    "baselineOffset",
    "bold",
    "fontSize",
    "foregroundColor",
    "italic",
    "smallCaps",
    "strikethrough",
    "underline",
    "weightedFontFamily",
}
WRITABLE_INLINE_STYLE_FIELDS = WRITABLE_TEXT_STYLE_FIELDS | {"link"}
INVENTORY_TOKEN_KINDS = {"audio", "image", "header_image", "blank", "url"}
DOCS_WRITE_SCOPE = "https://www.googleapis.com/auth/documents"


@dataclass(frozen=True)
class EditGroup:
    start_index: int
    end_index: int
    kind: str
    unit_id: str | None
    part_id: str | None
    source_text: str
    translated_text: str | None
    requests: list[dict[str, Any]]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temporary.replace(path)


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _slice_utf16(text: str, start: int, end: int) -> str:
    encoded = text.encode("utf-16-le")
    return encoded[start * 2 : end * 2].decode("utf-16-le")


def _dominant_writable_style(unit: dict[str, Any]) -> dict[str, Any]:
    weighted: list[tuple[int, dict[str, Any]]] = []
    for segment in unit.get("style_segments", []):
        style = {
            key: value
            for key, value in segment.get("style", {}).items()
            if key in WRITABLE_TEXT_STYLE_FIELDS
        }
        if style:
            weighted.append((_utf16_len(segment.get("text", "")), style))
    return max(weighted, key=lambda item: item[0])[1] if weighted else {}


def _style_request(start: int, text: str, style: dict[str, Any]) -> dict[str, Any] | None:
    if not text or not style:
        return None
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": start + _utf16_len(text)},
            "textStyle": style,
            "fields": ",".join(sorted(style)),
        }
    }


def _translated_span_style_requests(
    start: int, translated: str, part: dict[str, Any]
) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for span in part.get("translated_style_spans", []):
        span_start = span.get("start")
        span_end = span.get("end")
        if (
            not isinstance(span_start, int)
            or not isinstance(span_end, int)
            or span_start < 0
            or span_end <= span_start
            or span_end > len(translated)
        ):
            raise ValueError("Translated style span has an invalid range")
        expected_text = span.get("text")
        if expected_text is not None and translated[span_start:span_end] != expected_text:
            raise ValueError("Translated style span text does not match its range")
        style = {
            key: value
            for key, value in span.get("style", {}).items()
            if key in WRITABLE_INLINE_STYLE_FIELDS
        }
        request = _style_request(
            start + _utf16_len(translated[:span_start]),
            translated[span_start:span_end],
            style,
        )
        if request:
            requests.append(request)
    return requests


def _part_start_index(unit: dict[str, Any], part: dict[str, Any]) -> int:
    base = unit.get("location", {}).get("start_index")
    if not isinstance(base, int):
        raise ValueError(f"Unit {unit.get('unit_id')} has no source start index")
    source = unit.get("source_text", "")
    offset = part.get("start")
    if not isinstance(offset, int) or offset < 0 or offset > len(source):
        raise ValueError(f"Unit {unit.get('unit_id')} has an invalid part offset")
    return base + _utf16_len(source[:offset])


def _bilingual_prefix(unit: dict[str, Any], part: dict[str, Any]) -> str:
    if unit.get("role") in INLINE_BILINGUAL_ROLES:
        return " "
    if unit.get("role") == "phrase_example" and unit.get("paragraph", {}).get("bullet"):
        return "\u000b"
    if part.get("separator_after") == "\u000b":
        return "\u000b"
    return "\n"


def _part_edit_group(unit: dict[str, Any], part: dict[str, Any]) -> EditGroup:
    action = part["recommended_action"]
    translated = part.get("translated_text")
    if action not in REQUIRED_ACTIONS or not isinstance(translated, str):
        raise ValueError(
            f"Unit {unit.get('unit_id')} part {part.get('part_id')} is not write-ready"
        )

    start = _part_start_index(unit, part)
    source = part.get("source_text", "")
    end = start + _utf16_len(source)
    style = _dominant_writable_style(unit)
    requests: list[dict[str, Any]] = []

    if action == "bilingual":
        prefix = _bilingual_prefix(unit, part)
        inserted = prefix + translated
        requests.append({"insertText": {"location": {"index": end}, "text": inserted}})
        style_request = _style_request(end + _utf16_len(prefix), translated, style)
        if style_request:
            requests.append(style_request)
        requests.extend(
            _translated_span_style_requests(
                end + _utf16_len(prefix), translated, part
            )
        )
        return EditGroup(
            start_index=end,
            end_index=end,
            kind="insert_bilingual",
            unit_id=unit.get("unit_id"),
            part_id=part.get("part_id"),
            source_text=source,
            translated_text=translated,
            requests=requests,
        )

    if end > start:
        requests.append(
            {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}
        )
    requests.append({"insertText": {"location": {"index": start}, "text": translated}})
    style_request = _style_request(start, translated, style)
    if style_request:
        requests.append(style_request)
    requests.extend(_translated_span_style_requests(start, translated, part))
    return EditGroup(
        start_index=start,
        end_index=end,
        kind="replace_source",
        unit_id=unit.get("unit_id"),
        part_id=part.get("part_id"),
        source_text=source,
        translated_text=translated,
        requests=requests,
    )


def _overlaps_removal(start: int, end: int, removals: list[dict[str, Any]]) -> bool:
    return any(
        start < removal["end_index"] and end > removal["start_index"]
        for removal in removals
    )


def build_write_plan(
    completed_manifest: dict[str, Any],
    *,
    source_manifest: dict[str, Any],
    destination_doc_id: str,
    allowed_doc_id: str,
) -> dict[str, Any]:
    if not destination_doc_id or destination_doc_id != allowed_doc_id:
        raise ValueError("Destination document ID must exactly match the explicit allowlist ID")
    manifest_doc_id = completed_manifest.get("source", {}).get("document_id")
    if destination_doc_id != manifest_doc_id:
        raise ValueError(
            "Destination document ID does not match the document used to build the manifest"
        )

    validation = validate_manifest(completed_manifest, source_manifest=source_manifest)
    if not validation["valid"]:
        raise ValueError(
            "Completed manifest failed validation: "
            f"{validation['summary']['error_count']} error(s)"
        )

    removals = completed_manifest.get("planned_removals", [])
    groups: list[EditGroup] = []
    for removal in removals:
        start = removal.get("start_index")
        end = removal.get("end_index")
        if not isinstance(start, int) or not isinstance(end, int) or start >= end:
            raise ValueError(f"Invalid planned removal: {removal!r}")
        groups.append(
            EditGroup(
                start_index=start,
                end_index=end,
                kind=(
                    "remove_prepare"
                    if removal.get("section") == "PREPARE"
                    else "remove_header_image"
                ),
                unit_id=None,
                part_id=None,
                source_text="",
                translated_text=None,
                requests=[
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": start, "endIndex": end}
                        }
                    }
                ],
            )
        )

    for unit in completed_manifest.get("units", []):
        for part in unit.get("translation_parts", []):
            if part.get("recommended_action") not in REQUIRED_ACTIONS:
                continue
            start = _part_start_index(unit, part)
            end = start + _utf16_len(part.get("source_text", ""))
            if _overlaps_removal(start, max(end, start + 1), removals):
                raise ValueError(
                    f"Required translation unexpectedly overlaps a planned removal: "
                    f"{unit.get('unit_id')} / {part.get('part_id')}"
                )
            groups.append(_part_edit_group(unit, part))

    groups.sort(key=lambda group: (group.start_index, group.end_index), reverse=True)
    requests = [request for group in groups for request in group.requests]
    serialized_source = json.dumps(
        source_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    serialized_completed = json.dumps(
        completed_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "schema_version": 1,
        "mode": "google_docs_write_plan",
        "destination_document_id": destination_doc_id,
        "selection": completed_manifest.get("selection"),
        "source_manifest_sha256": hashlib.sha256(serialized_source).hexdigest(),
        "completed_manifest_sha256": hashlib.sha256(serialized_completed).hexdigest(),
        "summary": {
            "edit_group_count": len(groups),
            "google_request_count": len(requests),
            "replacement_count": sum(group.kind == "replace_source" for group in groups),
            "bilingual_insertion_count": sum(
                group.kind == "insert_bilingual" for group in groups
            ),
            "prepare_removal_count": sum(group.kind == "remove_prepare" for group in groups),
            "header_image_removal_count": sum(
                group.kind == "remove_header_image" for group in groups
            ),
        },
        "validation": validation["summary"],
        "groups": [asdict(group) for group in groups],
        "requests": requests,
    }


def _iter_paragraphs(content: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for element in content:
        if paragraph := element.get("paragraph"):
            yield paragraph
        if table := element.get("table"):
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    yield from _iter_paragraphs(cell.get("content", []))
        if toc := element.get("tableOfContents"):
            yield from _iter_paragraphs(toc.get("content", []))


def _text_segments(document: dict[str, Any]) -> list[tuple[int, int, str]]:
    segments: list[tuple[int, int, str]] = []
    for paragraph in _iter_paragraphs(document.get("body", {}).get("content", [])):
        for element in paragraph.get("elements", []):
            run = element.get("textRun")
            start = element.get("startIndex")
            end = element.get("endIndex")
            if run is not None and isinstance(start, int) and isinstance(end, int):
                segments.append((start, end, run.get("content", "")))
    return sorted(segments)


def _document_text(document: dict[str, Any]) -> str:
    return "".join(text for _, _, text in _text_segments(document))


def _range_text(document: dict[str, Any], start: int, end: int) -> str:
    pieces: list[str] = []
    for segment_start, segment_end, text in _text_segments(document):
        overlap_start = max(start, segment_start)
        overlap_end = min(end, segment_end)
        if overlap_start < overlap_end:
            pieces.append(
                _slice_utf16(
                    text,
                    overlap_start - segment_start,
                    overlap_end - segment_start,
                )
            )
    return "".join(pieces)


def verify_live_source(
    document: dict[str, Any],
    *,
    completed_manifest: dict[str, Any],
    destination_doc_id: str,
) -> list[str]:
    errors: list[str] = []
    if document.get("documentId") != destination_doc_id:
        errors.append("Fetched Google Doc ID does not match the allowlisted destination.")
    if not document.get("revisionId"):
        errors.append("Fetched Google Doc has no revisionId; revision-safe writes are unavailable.")
    for unit in completed_manifest.get("units", []):
        location = unit.get("location", {})
        start = location.get("start_index")
        end = location.get("end_index")
        if not isinstance(start, int) or not isinstance(end, int):
            errors.append(f"{unit.get('unit_id')}: missing source range.")
            continue
        live = _range_text(document, start, end)
        if live != unit.get("source_text"):
            errors.append(
                f"{unit.get('unit_id')}: live source range differs from the manifest."
            )
    return errors


def _table_shapes(document: dict[str, Any]) -> list[list[int]]:
    shapes: list[list[int]] = []

    def visit(content: Iterable[dict[str, Any]]) -> None:
        for element in content:
            if table := element.get("table"):
                rows = table.get("tableRows", [])
                shapes.append([len(row.get("tableCells", [])) for row in rows])
                for row in rows:
                    for cell in row.get("tableCells", []):
                        visit(cell.get("content", []))

    visit(document.get("body", {}).get("content", []))
    return shapes


def _link_inventory(document: dict[str, Any]) -> Counter[str]:
    links: Counter[str] = Counter()
    for paragraph in _iter_paragraphs(document.get("body", {}).get("content", [])):
        for element in paragraph.get("elements", []):
            link = element.get("textRun", {}).get("textStyle", {}).get("link", {})
            target = link.get("url") or link.get("bookmarkId") or link.get("headingId")
            if target:
                links[target] += 1
    return links


def _token_inventory(text: str) -> Counter[tuple[str, str]]:
    return Counter(
        (token["kind"], token["text"])
        for token in _protected_tokens(text)
        if token["kind"] in INVENTORY_TOKEN_KINDS
    )


def verify_post_write(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    completed_manifest: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    after_text = _document_text(after)
    missing_thai: list[str] = []
    for unit in completed_manifest.get("units", []):
        for part in unit.get("translation_parts", []):
            translated = part.get("translated_text")
            if (
                part.get("recommended_action") in REQUIRED_ACTIONS
                and isinstance(translated, str)
                and translated not in after_text
            ):
                missing_thai.append(f"{unit.get('unit_id')}::{part.get('part_id')}")
    if missing_thai:
        issues.append(f"Missing translated text for {len(missing_thai)} part(s).")

    if _table_shapes(before) != _table_shapes(after):
        issues.append("Table geometry changed unexpectedly.")
    if _link_inventory(before) != _link_inventory(after):
        issues.append("Link-target inventory changed unexpectedly.")

    before_tokens = _token_inventory(_document_text(before))
    after_tokens = _token_inventory(after_text)
    removed_text = "".join(
        _range_text(before, removal["start_index"], removal["end_index"])
        for removal in completed_manifest.get("planned_removals", [])
    )
    expected_tokens = before_tokens - _token_inventory(removed_text)
    if after_tokens != expected_tokens:
        issues.append("Protected audio/image/blank/URL inventory differs from the plan.")

    return {
        "valid": not issues,
        "before_revision_id": before.get("revisionId"),
        "after_revision_id": after.get("revisionId"),
        "missing_translation_parts": missing_thai,
        "before_table_shapes": _table_shapes(before),
        "after_table_shapes": _table_shapes(after),
        "expected_protected_tokens": [
            {"kind": kind, "text": text, "count": count}
            for (kind, text), count in sorted(expected_tokens.items())
        ],
        "actual_protected_tokens": [
            {"kind": kind, "text": text, "count": count}
            for (kind, text), count in sorted(after_tokens.items())
        ],
        "issues": issues,
    }


def _google_docs_service(credentials_path: Path):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        credentials_path, scopes=[DOCS_WRITE_SCOPE]
    )
    return build("docs", "v1", credentials=credentials, cache_discovery=False)


def _fetch_document(service: Any, document_id: str) -> dict[str, Any]:
    return service.documents().get(documentId=document_id).execute()


def execute_write_plan(
    plan: dict[str, Any],
    *,
    completed_manifest: dict[str, Any],
    credentials_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    document_id = plan["destination_document_id"]
    service = _google_docs_service(credentials_path)
    before = _fetch_document(service, document_id)
    preflight_errors = verify_live_source(
        before,
        completed_manifest=completed_manifest,
        destination_doc_id=document_id,
    )
    if preflight_errors:
        raise ValueError(f"Live document preflight failed: {preflight_errors[:10]!r}")

    response = (
        service.documents()
        .batchUpdate(
            documentId=document_id,
            body={
                "requests": plan["requests"],
                "writeControl": {"requiredRevisionId": before["revisionId"]},
            },
        )
        .execute()
    )
    after = _fetch_document(service, document_id)
    post_write = verify_post_write(before, after, completed_manifest=completed_manifest)
    return response, after, post_write


def render_plan_report(plan: dict[str, Any], *, executed: bool = False) -> str:
    summary = plan["summary"]
    lesson = (plan.get("selection") or {}).get("lesson") or "lesson"
    lines = [
        f"# {lesson} Thai Google Docs write plan",
        "",
        f"- Mode: **{'EXECUTED' if executed else 'DRY RUN'}**",
        f"- Destination document ID: `{plan['destination_document_id']}`",
        f"- Edit groups: {summary['edit_group_count']}",
        f"- Google Docs requests: {summary['google_request_count']}",
        f"- Thai replacements: {summary['replacement_count']}",
        f"- Bilingual insertions: {summary['bilingual_insertion_count']}",
        f"- PREPARE removals: {summary['prepare_removal_count']}",
        f"- Header-image removals: {summary['header_image_removal_count']}",
        f"- Manifest validation errors: {plan['validation']['error_count']}",
        "",
        "Edits are ordered from later document indexes to earlier indexes. A live write uses "
        "the fetched revision ID as a required write precondition.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan or apply a validated Thai translation manifest to Google Docs."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--destination-doc-id", required=True)
    parser.add_argument("--allow-doc-id", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument(
        "--credentials",
        type=Path,
        default=Path(__file__).parents[2] / "keys" / "lesson_importer_key.json",
    )
    parser.add_argument("--operation-log", type=Path)
    parser.add_argument("--post-write-report", type=Path)
    args = parser.parse_args()

    completed = _read_json(args.manifest)
    source = _read_json(args.source_manifest)
    plan = build_write_plan(
        completed,
        source_manifest=source,
        destination_doc_id=args.destination_doc_id,
        allowed_doc_id=args.allow_doc_id,
    )
    _write_json(args.plan, plan)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_plan_report(plan, executed=args.execute), encoding="utf-8")

    if not args.execute:
        print(
            f"Dry run: {plan['summary']['edit_group_count']} edit groups, "
            f"{plan['summary']['google_request_count']} Google Docs requests."
        )
        return

    if not args.operation_log or not args.post_write_report:
        raise ValueError("--execute requires --operation-log and --post-write-report")
    response, after, post_write = execute_write_plan(
        plan,
        completed_manifest=completed,
        credentials_path=args.credentials,
    )
    operation_log = {
        "document_id": args.destination_doc_id,
        "plan_sha256": hashlib.sha256(
            json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "write_response": response,
        "after_revision_id": after.get("revisionId"),
        "edit_groups": [
            {
                key: group[key]
                for key in (
                    "start_index",
                    "end_index",
                    "kind",
                    "unit_id",
                    "part_id",
                )
            }
            for group in plan["groups"]
        ],
        "post_write_validation": post_write,
    }
    _write_json(args.operation_log, operation_log)
    _write_json(args.post_write_report, post_write)
    if not post_write["valid"]:
        raise SystemExit("Write completed, but post-write validation failed; inspect reports.")
    print(
        f"Write complete and verified at revision {after.get('revisionId')}: "
        f"{plan['summary']['edit_group_count']} edit groups."
    )


if __name__ == "__main__":
    main()

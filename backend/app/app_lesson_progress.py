import copy
import re
from collections import defaultdict
from functools import lru_cache

from app.resolver import resolve_lesson

APP_PAGE_ORDER = [
    "prepare",
    "comprehension",
    "transcript",
    "apply",
    "understand",
    "extra_tip",
    "common_mistake",
    "phrases_verbs",
    "culture_note",
    "practice",
]

CARD_SECTION_TYPES = {
    "understand",
    "extra_tip",
    "common_mistake",
    "culture_note",
}

APP_KEY_PREFIX = "app:"


def build_app_page_key(page_name):
    return f"{APP_KEY_PREFIX}page:{page_name}"


def build_app_card_key(section_type, card_slug):
    return f"{APP_KEY_PREFIX}card:{section_type}:{card_slug}"


def build_app_exercise_key(exercise_id):
    return f"{APP_KEY_PREFIX}exercise:{exercise_id}"


def build_app_comprehension_exercise_key():
    return f"{APP_KEY_PREFIX}exercise:comprehension_quiz"


def build_app_example_reveal_key(name="apply"):
    return f"{APP_KEY_PREFIX}example_reveal:{name}"


def is_app_unit_key(unit_key):
    return isinstance(unit_key, str) and unit_key.startswith(APP_KEY_PREFIX)


def _clean_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", _clean_text(value).lower()).strip("-")
    return slug or "card"


def _node_text(node):
    if not isinstance(node, dict):
        return ""

    text_value = node.get("text")
    if isinstance(text_value, dict):
        text = _clean_text(text_value.get("en") or text_value.get("th"))
        if text:
            return text
    elif isinstance(text_value, str):
        text = _clean_text(text_value)
        if text:
            return text

    for field in ("header_en", "header", "title", "prompt", "prompt_en"):
        text = _clean_text(node.get(field))
        if text:
            return text

    inlines = node.get("inlines")
    if isinstance(inlines, list):
        merged = "".join(_clean_text(inline.get("text")) for inline in inlines if isinstance(inline, dict))
        return _clean_text(merged)

    return ""


def _is_all_caps_heading(node):
    if not isinstance(node, dict) or node.get("kind") != "heading":
        return False

    text = _node_text(node)
    if not text:
        return False

    letters = re.sub(r"[^A-Za-z]+", "", text)
    if not letters:
        return False
    return letters == letters.upper()


def _is_quick_practice_heading(text):
    normalized = _clean_text(text).lower()
    return "quick practice" in normalized or "แบบฝึกหัด" in text or "ฝึกหัด" in text


def _build_card_units(section_type, nodes, parent_page_key, base_sort_order):
    if section_type not in CARD_SECTION_TYPES or not isinstance(nodes, list):
        return []

    headings = []
    seen_slugs = defaultdict(int)

    for node in nodes:
        if not _is_all_caps_heading(node):
            continue
        heading_text = _node_text(node)
        if _is_quick_practice_heading(heading_text):
            continue

        slug = _slugify(heading_text)
        seen_slugs[slug] += 1
        if seen_slugs[slug] > 1:
            slug = f"{slug}-{seen_slugs[slug]}"
        headings.append((heading_text, slug))

    units = []
    for idx, (heading_text, slug) in enumerate(headings, start=1):
        units.append(
            {
                "unit_type": "card",
                "unit_key": build_app_card_key(section_type, slug),
                "parent_unit_key": parent_page_key,
                "section_key": parent_page_key,
                "sort_order": base_sort_order + idx,
                "label": heading_text,
            }
        )
    return units


@lru_cache(maxsize=256)
def _build_app_lesson_expectations_cached(lesson_id):
    resolved = resolve_lesson(lesson_id, "en")
    sections = resolved.get("sections") or []
    questions = resolved.get("questions") or []
    transcript = resolved.get("transcript") or []
    practice_exercises = resolved.get("practice_exercises") or []
    phrases = resolved.get("phrases") or []

    section_by_type = {}
    for section in sections:
        section_type = _clean_text(section.get("type")).lower()
        if section_type and section_type not in section_by_type:
            section_by_type[section_type] = section

    has_phrase_content = any(
        _clean_text(item.get("content"))
        or _clean_text(item.get("content_th"))
        or bool(item.get("content_jsonb"))
        or bool(item.get("content_jsonb_th"))
        for item in phrases
    )

    units = []
    for page_index, page_name in enumerate(APP_PAGE_ORDER, start=1):
        page_key = build_app_page_key(page_name)
        page_sort_order = page_index * 100

        if page_name == "prepare":
            if page_name in section_by_type:
                units.append(
                    {
                        "unit_type": "page",
                        "unit_key": page_key,
                        "parent_unit_key": None,
                        "section_key": None,
                        "sort_order": page_sort_order,
                        "label": "Prepare",
                    }
                )
            continue

        if page_name == "comprehension":
            if questions:
                units.append(
                    {
                        "unit_type": "page",
                        "unit_key": page_key,
                        "parent_unit_key": None,
                        "section_key": None,
                        "sort_order": page_sort_order,
                        "label": "Comprehension",
                    }
                )
                units.append(
                    {
                        "unit_type": "exercise",
                        "unit_key": build_app_comprehension_exercise_key(),
                        "parent_unit_key": page_key,
                        "section_key": page_key,
                        "sort_order": page_sort_order + 1,
                        "label": "Comprehension Quiz",
                    }
                )
            continue

        if page_name == "transcript":
            if transcript:
                units.append(
                    {
                        "unit_type": "page",
                        "unit_key": page_key,
                        "parent_unit_key": None,
                        "section_key": None,
                        "sort_order": page_sort_order,
                        "label": "Transcript",
                    }
                )
            continue

        if page_name == "practice":
            if practice_exercises:
                units.append(
                    {
                        "unit_type": "page",
                        "unit_key": page_key,
                        "parent_unit_key": None,
                        "section_key": None,
                        "sort_order": page_sort_order,
                        "label": "Practice",
                    }
                )
                for exercise_index, exercise in enumerate(
                    sorted(practice_exercises, key=lambda row: row.get("sort_order") or 0),
                    start=1,
                ):
                    exercise_id = exercise.get("id")
                    if not exercise_id:
                        continue
                    units.append(
                        {
                            "unit_type": "exercise",
                            "unit_key": build_app_exercise_key(exercise_id),
                            "parent_unit_key": page_key,
                            "section_key": page_key,
                            "sort_order": page_sort_order + exercise_index,
                            "label": _clean_text(exercise.get("title")) or f"Exercise {exercise_index}",
                        }
                    )
            continue

        if page_name == "phrases_verbs":
            if has_phrase_content:
                units.append(
                    {
                        "unit_type": "page",
                        "unit_key": page_key,
                        "parent_unit_key": None,
                        "section_key": None,
                        "sort_order": page_sort_order,
                        "label": "Phrases & Verbs",
                    }
                )
            continue

        section = section_by_type.get(page_name)
        if not section:
            continue

        units.append(
            {
                "unit_type": "page",
                "unit_key": page_key,
                "parent_unit_key": None,
                "section_key": None,
                "sort_order": page_sort_order,
                "label": page_name.replace("_", " ").title(),
            }
        )

        if page_name == "apply":
            content_jsonb = section.get("content_jsonb")
            has_response = False
            if isinstance(content_jsonb, dict):
                has_response = bool(
                    _clean_text(content_jsonb.get("response"))
                    or (isinstance(content_jsonb.get("response_nodes"), list) and content_jsonb.get("response_nodes"))
                )
            if has_response:
                units.append(
                    {
                        "unit_type": "example_reveal",
                        "unit_key": build_app_example_reveal_key("apply"),
                        "parent_unit_key": page_key,
                        "section_key": page_key,
                        "sort_order": page_sort_order + 1,
                        "label": "See Example Answer",
                    }
                )
            continue

        card_units = _build_card_units(
            page_name,
            section.get("content_jsonb") or [],
            page_key,
            page_sort_order,
        )
        units.extend(card_units)

    units.sort(key=lambda unit: unit["sort_order"])
    return {
        "lesson_id": lesson_id,
        "units": units,
        "unit_keys": [unit["unit_key"] for unit in units],
    }


def build_app_lesson_expectations(lesson_id):
    return copy.deepcopy(_build_app_lesson_expectations_cached(lesson_id))


def build_app_lesson_expectations_for_many(lesson_ids):
    expectations = {}
    for lesson_id in lesson_ids:
        if not lesson_id:
            continue
        expectations[lesson_id] = build_app_lesson_expectations(lesson_id)
    return expectations


def derive_app_resume(progress_row, unit_rows_by_key):
    if not progress_row:
        return None

    last_unit_type = progress_row.get("last_unit_type")
    last_unit_key = progress_row.get("last_unit_key")
    if not is_app_unit_key(last_unit_key):
        return None

    if last_unit_type in {"page", "card"}:
        return {
            "unit_type": last_unit_type,
            "unit_key": last_unit_key,
        }

    if last_unit_type in {"exercise", "example_reveal"}:
        unit_row = unit_rows_by_key.get(last_unit_key) or {}
        parent_key = unit_row.get("section_key")
        if is_app_unit_key(parent_key):
            parent_type = "card" if parent_key.startswith(f"{APP_KEY_PREFIX}card:") else "page"
            return {
                "unit_type": parent_type,
                "unit_key": parent_key,
            }

    return None


def summarize_app_lesson_progress(lesson_ids, progress_rows, unit_rows, expectations_by_lesson):
    lesson_ids = [lesson_id for lesson_id in lesson_ids if lesson_id]
    progress_by_lesson = {
        row.get("lesson_id"): row
        for row in (progress_rows or [])
        if row.get("lesson_id")
    }

    unit_rows_by_lesson = defaultdict(list)
    seen_units_by_lesson = defaultdict(set)
    completed_units_by_lesson = defaultdict(set)
    unit_rows_by_lesson_key = defaultdict(dict)

    for row in unit_rows or []:
        lesson_id = row.get("lesson_id")
        unit_key = row.get("unit_key")
        if not lesson_id or not is_app_unit_key(unit_key):
            continue
        unit_rows_by_lesson[lesson_id].append(row)
        unit_rows_by_lesson_key[lesson_id][unit_key] = row
        seen_units_by_lesson[lesson_id].add(unit_key)
        if row.get("is_completed"):
            completed_units_by_lesson[lesson_id].add(unit_key)

    summaries = {}
    for lesson_id in lesson_ids:
        expected = expectations_by_lesson.get(lesson_id) or {"units": [], "unit_keys": []}
        expected_unit_keys = expected.get("unit_keys") or []
        expected_units_set = set(expected_unit_keys)
        completed_units = completed_units_by_lesson.get(lesson_id, set())
        completed_count = sum(1 for unit_key in expected_unit_keys if unit_key in completed_units)
        total_units = len(expected_unit_keys)
        is_completed = total_units > 0 and completed_count >= total_units
        progress_row = progress_by_lesson.get(lesson_id) or {}
        has_started = bool(seen_units_by_lesson.get(lesson_id)) or bool(
            is_app_unit_key(progress_row.get("last_unit_key"))
        )
        resume = derive_app_resume(
            progress_row,
            unit_rows_by_lesson_key.get(lesson_id, {}),
        )

        summaries[lesson_id] = {
            "lesson_id": lesson_id,
            "has_started": has_started,
            "percent_complete": round((completed_count / total_units) * 100) if total_units > 0 else 0,
            "is_completed": is_completed,
            "completed_units": completed_count,
            "total_units": total_units,
            "resume": resume,
            "completed_unit_keys": [
                unit_key for unit_key in expected_unit_keys if unit_key in completed_units
            ],
            "expected_units": [
                unit for unit in (expected.get("units") or []) if unit.get("unit_key") in expected_units_set
            ],
        }

    return summaries

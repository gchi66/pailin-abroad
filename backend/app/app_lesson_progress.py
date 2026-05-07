import copy
import json
import re
import time
from collections import defaultdict

from app.supabase_client import supabase

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
APP_EXPECTATIONS_TTL_SECONDS = 900
_app_expectations_cache = {}


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


def _is_retryable_supabase_error(exc):
    message = str(exc or "")
    retry_markers = (
        "ConnectionTerminated",
        "PROTOCOL_ERROR",
        "COMPRESSION_ERROR",
    )
    return any(marker in message for marker in retry_markers)


def _execute_with_retry(build_query, label, retries=2, base_delay=0.2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return build_query().execute()
        except Exception as exc:
            last_error = exc
            if attempt >= retries or not _is_retryable_supabase_error(exc):
                raise
            delay = base_delay * (attempt + 1)
            print(
                f"Retrying {label} after transient Supabase error "
                f"(attempt {attempt + 1}/{retries + 1}): {exc}",
                flush=True,
            )
            time.sleep(delay)
    raise last_error


def _coerce_jsonish(value):
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


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


def _fetch_app_progress_source_rows(lesson_ids):
    lesson_ids = [lesson_id for lesson_id in lesson_ids if lesson_id]
    if not lesson_ids:
        return {
            "sections": [],
            "transcript": [],
            "questions": [],
            "exercises": [],
            "lesson_phrases": [],
            "phrases": [],
        }

    sections_result = _execute_with_retry(
        lambda: (
            supabase.table("lesson_sections")
            .select("lesson_id, id, type, sort_order, content_jsonb, content_jsonb_th")
            .in_("lesson_id", lesson_ids)
            .order("sort_order", desc=False)
        ),
        "app lesson progress lesson_sections",
    )
    transcript_result = _execute_with_retry(
        lambda: (
            supabase.table("transcript_lines")
            .select("lesson_id")
            .in_("lesson_id", lesson_ids)
        ),
        "app lesson progress transcript_lines",
    )
    questions_result = _execute_with_retry(
        lambda: (
            supabase.table("comprehension_questions")
            .select("lesson_id, id")
            .in_("lesson_id", lesson_ids)
        ),
        "app lesson progress comprehension_questions",
    )
    exercises_result = _execute_with_retry(
        lambda: (
            supabase.table("practice_exercises")
            .select("lesson_id, id, title, sort_order")
            .in_("lesson_id", lesson_ids)
            .order("sort_order", desc=False)
        ),
        "app lesson progress practice_exercises",
    )
    lesson_phrases_result = _execute_with_retry(
        lambda: (
            supabase.table("lesson_phrases")
            .select("lesson_id, phrase_id")
            .in_("lesson_id", lesson_ids)
        ),
        "app lesson progress lesson_phrases",
    )

    phrase_ids = sorted({
        row.get("phrase_id")
        for row in (lesson_phrases_result.data or [])
        if row.get("phrase_id")
    })
    phrases = []
    if phrase_ids:
        phrases_result = _execute_with_retry(
            lambda: (
                supabase.table("phrases")
                .select("id, content, content_th, content_jsonb, content_jsonb_th")
                .in_("id", phrase_ids)
            ),
            "app lesson progress phrases",
        )
        phrases = phrases_result.data or []

    return {
        "sections": sections_result.data or [],
        "transcript": transcript_result.data or [],
        "questions": questions_result.data or [],
        "exercises": exercises_result.data or [],
        "lesson_phrases": lesson_phrases_result.data or [],
        "phrases": phrases,
    }


def _get_cached_app_expectation(lesson_id):
    cached = _app_expectations_cache.get(lesson_id)
    if not cached:
        return None
    if time.time() - cached["ts"] > APP_EXPECTATIONS_TTL_SECONDS:
        _app_expectations_cache.pop(lesson_id, None)
        return None
    return copy.deepcopy(cached["value"])


def _set_cached_app_expectation(lesson_id, expectation):
    _app_expectations_cache[lesson_id] = {
        "ts": time.time(),
        "value": copy.deepcopy(expectation),
    }


def _build_app_lesson_expectations_from_rows(lesson_ids, source_rows):
    sections_by_lesson = defaultdict(list)
    for row in source_rows.get("sections") or []:
        sections_by_lesson[row.get("lesson_id")].append(row)

    transcript_counts = defaultdict(int)
    for row in source_rows.get("transcript") or []:
        transcript_counts[row.get("lesson_id")] += 1

    question_counts = defaultdict(int)
    for row in source_rows.get("questions") or []:
        question_counts[row.get("lesson_id")] += 1

    exercises_by_lesson = defaultdict(list)
    for row in source_rows.get("exercises") or []:
        exercises_by_lesson[row.get("lesson_id")].append(row)

    phrases_by_id = {
        row.get("id"): row
        for row in source_rows.get("phrases") or []
        if row.get("id")
    }
    has_phrase_content = defaultdict(bool)
    for link in source_rows.get("lesson_phrases") or []:
        lesson_id = link.get("lesson_id")
        phrase = phrases_by_id.get(link.get("phrase_id")) or {}
        if (
            _clean_text(phrase.get("content"))
            or _clean_text(phrase.get("content_th"))
            or _coerce_jsonish(phrase.get("content_jsonb"))
            or _coerce_jsonish(phrase.get("content_jsonb_th"))
        ):
            has_phrase_content[lesson_id] = True

    expectations = {}
    for lesson_id in lesson_ids:
        section_by_type = {}
        for section in sections_by_lesson.get(lesson_id, []):
            section_type = _clean_text(section.get("type")).lower()
            if section_type and section_type not in section_by_type:
                section_by_type[section_type] = section

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
                if question_counts.get(lesson_id, 0) > 0:
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
                if transcript_counts.get(lesson_id, 0) > 0:
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
                practice_exercises = exercises_by_lesson.get(lesson_id, [])
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
                if has_phrase_content.get(lesson_id):
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
                content_jsonb = _coerce_jsonish(section.get("content_jsonb"))
                has_response = False
                if isinstance(content_jsonb, dict):
                    has_response = bool(
                        _clean_text(content_jsonb.get("response"))
                        or (
                            isinstance(content_jsonb.get("response_nodes"), list)
                            and content_jsonb.get("response_nodes")
                        )
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
                _coerce_jsonish(section.get("content_jsonb")) or [],
                page_key,
                page_sort_order,
            )
            units.extend(card_units)

        units.sort(key=lambda unit: unit["sort_order"])
        expectations[lesson_id] = {
            "lesson_id": lesson_id,
            "units": units,
            "unit_keys": [unit["unit_key"] for unit in units],
        }

    return expectations


def build_app_lesson_expectations(lesson_id):
    expectations = build_app_lesson_expectations_for_many([lesson_id])
    return copy.deepcopy(
        expectations.get(lesson_id)
        or {"lesson_id": lesson_id, "units": [], "unit_keys": []}
    )


def build_app_lesson_expectations_for_many(lesson_ids):
    lesson_ids = [lesson_id for lesson_id in lesson_ids if lesson_id]
    if not lesson_ids:
        return {}
    expectations = {}
    uncached_lesson_ids = []
    for lesson_id in lesson_ids:
        cached = _get_cached_app_expectation(lesson_id)
        if cached is not None:
            expectations[lesson_id] = cached
        else:
            uncached_lesson_ids.append(lesson_id)

    if uncached_lesson_ids:
        source_rows = _fetch_app_progress_source_rows(uncached_lesson_ids)
        fresh_expectations = _build_app_lesson_expectations_from_rows(uncached_lesson_ids, source_rows)
        for lesson_id, expectation in fresh_expectations.items():
            _set_cached_app_expectation(lesson_id, expectation)
            expectations[lesson_id] = copy.deepcopy(expectation)

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

    seen_units_by_lesson = defaultdict(set)
    completed_units_by_lesson = defaultdict(set)
    unit_rows_by_lesson_key = defaultdict(dict)

    for row in unit_rows or []:
        lesson_id = row.get("lesson_id")
        unit_key = row.get("unit_key")
        if not lesson_id or not is_app_unit_key(unit_key):
            continue
        unit_rows_by_lesson_key[lesson_id][unit_key] = row
        seen_units_by_lesson[lesson_id].add(unit_key)
        if row.get("is_completed"):
            completed_units_by_lesson[lesson_id].add(unit_key)

    summaries = {}
    for lesson_id in lesson_ids:
        expected = expectations_by_lesson.get(lesson_id) or {"units": [], "unit_keys": []}
        expected_unit_keys = expected.get("unit_keys") or []
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
            "expected_units": list(expected.get("units") or []),
        }

    return summaries

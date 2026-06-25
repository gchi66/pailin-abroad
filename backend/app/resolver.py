# app/resolver.py
import copy
import os
import re
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from app.supabase_client import supabase
from app.merge_jsonb import merge_content_nodes
from app.config import Config

Lang = str  # "en" | "th"
TEXT_KINDS = {"heading", "paragraph", "list_item", "misc_item"}
AUDIO_TAG_RE = re.compile(r"\[audio:([^\]\s]+)\]", re.I)
RESOLVED_LESSON_CACHE_TTL_SECONDS = 5 * 60
GLOBAL_LESSON_IMAGES_CACHE_TTL_SECONDS = 10 * 60
AUDIO_SNIPPETS_CACHE_TTL_SECONDS = 10 * 60

_resolved_lesson_cache = {}
_global_images_cache = {"data": None, "timestamp": 0.0}
_audio_snippets_cache = {}


def _now():
    return time.perf_counter()


def _elapsed_ms(start):
    return max(0, round((time.perf_counter() - start) * 1000))


def _cache_fresh(timestamp: float, ttl_seconds: int) -> bool:
    return (time.time() - timestamp) < ttl_seconds


def _exec(q):
    res = q.execute()
    if getattr(res, "error", None):
        msg = getattr(res.error, "message", None) or str(res.error)
        raise RuntimeError(msg)
    return res.data


def _exec_logged(label: str, q):
    try:
      data = _exec(q)
      size = len(data) if isinstance(data, list) else (1 if data else 0)
      print(f"[resolver] {label} ok count={size}", flush=True)
      return data
    except Exception as exc:
      print(f"[resolver] {label} failed: {exc}", flush=True)
      raise


def _get_cached_global_images():
    if (
        _global_images_cache["data"] is not None
        and _cache_fresh(
            _global_images_cache["timestamp"],
            GLOBAL_LESSON_IMAGES_CACHE_TTL_SECONDS,
        )
    ):
        return _global_images_cache["data"], True

    data = _exec_logged(
        "lesson_images_global",
        supabase.table("lesson_images")
        .select("image_key, url")
        .is_("lesson_id", None)
    )
    _global_images_cache["data"] = data
    _global_images_cache["timestamp"] = time.time()
    return data, False


def _get_cached_audio_snippets(lesson_external_id: str):
    if not lesson_external_id:
        return [], False

    entry = _audio_snippets_cache.get(lesson_external_id)
    if entry and _cache_fresh(entry["timestamp"], AUDIO_SNIPPETS_CACHE_TTL_SECONDS):
        return entry["data"], True

    data = _exec(
        supabase.table("audio_snippets")
        .select("audio_key, section, seq")
        .eq("lesson_external_id", lesson_external_id)
    )
    _audio_snippets_cache[lesson_external_id] = {
        "data": data,
        "timestamp": time.time(),
    }
    return data, False


def _pick_lang(en: Optional[Any], th: Optional[Any], lang: Lang) -> Optional[str]:
    def clean(v):
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return None
        s = str(v).strip()
        return s if s != "" else None

    if lang == "th":
        return clean(th) or clean(en)
    return clean(en) or clean(th)


def _normalize_rich_nodes(nodes: Any, lang: Lang) -> List[Dict[str, Any]]:
    if not isinstance(nodes, list):
        return []
    out: List[Dict[str, Any]] = []
    for node in nodes:
        kind = node.get("kind")
        if kind not in TEXT_KINDS:
            # keep non-text kinds too, just ensure shape is consistent
            node.setdefault("inlines", [])
        else:
            if "inlines" not in node or not isinstance(node["inlines"], list):
                node["inlines"] = []
        out.append(node)
    return out


def _enrich_image_nodes(nodes: Any, image_lookup: Dict[str, str]) -> None:
    if not image_lookup or not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("kind") == "image":
            key = (node.get("image_key") or "").strip()
            if key and key in image_lookup:
                node["image_url"] = image_lookup[key]


def _normalize_audio_key(raw_key: str) -> str:
    key = (raw_key or "").strip()
    if not key:
        return ""
    if key.startswith("phrases_verbs_"):
        return key
    if "_" in key:
        prefix, suffix = key.rsplit("_", 1)
        if suffix.isdigit():
            return f"{prefix}_{int(suffix):02d}"
    return key


def _ensure_json_list(value: Any) -> Any:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        return parsed if isinstance(parsed, list) else value
    return value


def _inject_audio_metadata(nodes: List[Dict[str, Any]], fallback_section: Optional[str] = None) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        inlines = node.get("inlines") or []
        if not inlines:
            continue
        text_blob = " ".join(str(span.get("text", "")) for span in inlines if isinstance(span, dict))
        match = AUDIO_TAG_RE.search(text_blob)
        if not match:
            continue
        raw_key = match.group(1)
        normalized_key = _normalize_audio_key(raw_key)
        if normalized_key:
            node["audio_key"] = normalized_key
        if "_" in raw_key:
            suffix = raw_key.rsplit("_", 1)[-1]
            if suffix.isdigit():
                node["audio_seq"] = int(suffix)
        if fallback_section and not node.get("audio_section"):
            node["audio_section"] = fallback_section


def _inline_text(node: Dict[str, Any]) -> str:
    return "".join(str(span.get("text", "")) for span in (node.get("inlines") or []) if isinstance(span, dict)).strip()


def _normalize_title_key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _build_scm_label_node(label_text: str) -> Dict[str, Any]:
    return {
        "kind": "paragraph",
        "level": None,
        "scm_label": True,
        "inlines": [
            {
                "text": label_text,
                "bold": True,
                "italic": False,
                "underline": False,
                "color": "#FF4545",
            }
        ],
        "indent": 0,
        "detection_indent": 0,
        "indent_level": 0,
        "indent_start_pts": 0,
        "indent_first_line_pts": 0,
        "indent_first_line_level": 0,
    }


def _inject_scm_labels_into_section_nodes(
    nodes: List[Dict[str, Any]],
    common_mistake_items: List[Dict[str, Any]],
    lang: Lang,
) -> List[Dict[str, Any]]:
    if not isinstance(nodes, list) or not nodes:
        return nodes

    scm_titles = {
        _normalize_title_key(item.get("title")): item
        for item in (common_mistake_items or [])
        if item.get("scm") and item.get("title")
    }
    if not scm_titles:
        return nodes

    label_text = "SUPER COMMON MISTAKE! 🚨" if lang != "th" else "ข้อผิดพลาดที่พบบ่อยมาก! 🚨"
    out: List[Dict[str, Any]] = []
    inserted_titles = set()

    for node in nodes:
        out.append(node)
        if node.get("kind") != "heading":
            continue
        heading_key = _normalize_title_key(_inline_text(node))
        if heading_key in scm_titles and heading_key not in inserted_titles:
            out.append(_build_scm_label_node(label_text))
            inserted_titles.add(heading_key)

    return out


def _fetch_lesson_bundle(lesson_id: str) -> Dict[str, Any]:
    bundle_start = _now()
    print(f"[lesson-resolver] bundle_start lesson_id={lesson_id}", flush=True)

    lesson_start = _now()
    lesson = _exec_logged(
        "lessons",
        supabase.table("lessons")
        .select(
            "id, stage, level, lesson_order, image_url, conversation_audio_url, "
            "lesson_external_id, "
            "title, title_th, subtitle, subtitle_th, focus, focus_th, backstory, backstory_th, "
            "header_img"
        )
        .eq("id", lesson_id)
        .single()
    )
    lesson_ms = _elapsed_ms(lesson_start)

    def load_sections():
        start = _now()
        data = _exec_logged(
            "lesson_sections",
            supabase.table("lesson_sections").select("*").eq("lesson_id", lesson_id).order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    def load_transcript():
        start = _now()
        data = _exec_logged(
            "transcript_lines",
            supabase.table("transcript_lines").select("*").eq("lesson_id", lesson_id).order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    def load_questions():
        start = _now()
        data = _exec_logged(
            "comprehension_questions",
            supabase.table("comprehension_questions").select("*").eq("lesson_id", lesson_id).order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    def load_exercises():
        start = _now()
        data = _exec_logged(
            "practice_exercises",
            supabase.table("practice_exercises").select("*").eq("lesson_id", lesson_id).order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    def load_phrase_links():
        start = _now()
        data = _exec_logged(
            "lesson_phrases_with_phrases",
            supabase.table("lesson_phrases")
            .select("lesson_id, phrase_id, sort_order, phrases(*)")
            .eq("lesson_id", lesson_id)
            .order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    def load_images():
        start = _now()
        data = _exec_logged(
            "lesson_images",
            supabase.table("lesson_images").select("image_key, url").eq("lesson_id", lesson_id)
        )
        return data, _elapsed_ms(start)

    def load_common_mistakes():
        start = _now()
        data = _exec_logged(
            "common_mistakes",
            supabase.table("common_mistakes")
            .select("id, lesson_id, mistake_code, title, title_th, sort_order, scm, content_jsonb, content_jsonb_th")
            .eq("lesson_id", lesson_id)
            .order("sort_order", desc=False)
        )
        return data, _elapsed_ms(start)

    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            "sections": executor.submit(load_sections),
            "transcript": executor.submit(load_transcript),
            "questions": executor.submit(load_questions),
            "exercises": executor.submit(load_exercises),
            "phrase_links": executor.submit(load_phrase_links),
            "images": executor.submit(load_images),
            "common_mistakes": executor.submit(load_common_mistakes),
        }

        sections, sections_ms = futures["sections"].result()
        transcript, transcript_ms = futures["transcript"].result()
        questions, questions_ms = futures["questions"].result()
        exercises, exercises_ms = futures["exercises"].result()
        phrase_links, phrase_links_ms = futures["phrase_links"].result()
        images, images_ms = futures["images"].result()
        common_mistakes, common_mistakes_ms = futures["common_mistakes"].result()

    global_images_start = _now()
    global_images, global_images_cache_hit = _get_cached_global_images()
    global_images_ms = _elapsed_ms(global_images_start)

    print(
        f"[lesson-resolver] bundle_done lesson_id={lesson_id} "
        f"lesson_ms={lesson_ms} sections_ms={sections_ms} transcript_ms={transcript_ms} "
        f"questions_ms={questions_ms} exercises_ms={exercises_ms} phrase_links_ms={phrase_links_ms} "
        f"images_ms={images_ms} common_mistakes_ms={common_mistakes_ms} global_images_ms={global_images_ms} "
        f"global_images_cache_hit={global_images_cache_hit} total_ms={_elapsed_ms(bundle_start)}",
        flush=True,
    )

    return {
        "lesson": lesson,
        "sections": sections,
        "transcript": transcript,
        "questions": questions,
        "exercises": exercises,
        "phrase_links": phrase_links,
        "images": images,
        "common_mistakes": common_mistakes,
        "global_images": global_images,
    }


def resolve_lesson(lesson_id: str, lang: Lang) -> Dict[str, Any]:
    route_start = _now()
    cache_key = f"{lesson_id}:{lang}"
    cached_entry = _resolved_lesson_cache.get(cache_key)
    if cached_entry and _cache_fresh(
        cached_entry["timestamp"], RESOLVED_LESSON_CACHE_TTL_SECONDS
    ):
        print(
            f"[lesson-resolver] cache_hit lesson_id={lesson_id} lang={lang} "
            f"elapsed_ms={_elapsed_ms(route_start)}",
            flush=True,
        )
        return copy.deepcopy(cached_entry["data"])

    fetch_start = _now()
    raw = _fetch_lesson_bundle(lesson_id)
    fetch_ms = _elapsed_ms(fetch_start)

    transform_start = _now()
    L = raw["lesson"]
    images_lookup: Dict[str, str] = {}
    for img in raw.get("global_images", []) or []:
        key = img.get("image_key")
        url = img.get("url")
        if key and url:
            images_lookup[key] = url
    for img in raw.get("images", []) or []:
        key = img.get("image_key")
        url = img.get("url")
        if key and url:
            images_lookup[key] = url

    resolved = {
        "id": L["id"],
        "stage": L.get("stage"),
        "level": L.get("level"),
        "lesson_order": L.get("lesson_order"),
        "lesson_external_id": L.get("lesson_external_id"),
        "image_url": L.get("image_url"),
        "conversation_audio_url": L.get("conversation_audio_url"),
        "title": _pick_lang(L.get("title"), L.get("title_th"), lang),
        "subtitle": _pick_lang(L.get("subtitle"), L.get("subtitle_th"), lang),
        "focus": _pick_lang(L.get("focus"), L.get("focus_th"), lang),
        "backstory": _pick_lang(L.get("backstory"), L.get("backstory_th"), lang),
        "title_en": L.get("title"),
        "title_th": L.get("title_th"),
        "subtitle_en": L.get("subtitle"),
        "subtitle_th": L.get("subtitle_th"),
        "focus_en": L.get("focus"),
        "focus_th": L.get("focus_th"),
        "backstory_en": L.get("backstory"),
        "backstory_th": L.get("backstory_th"),
    }

    # header image resolution
    raw_header_img = (L.get("header_img") or "").strip()
    header_image_path: Optional[str] = None
    header_image_url: Optional[str] = None
    if raw_header_img:
        lowered = raw_header_img.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            header_image_url = raw_header_img
        else:
            relative = raw_header_img.lstrip("/")
            if relative.lower().startswith("lesson-images/"):
                relative = relative.split("/", 1)[1]
            relative = relative.split("?", 1)[0].split("#", 1)[0]
            if not relative.lower().startswith("headers/") and "/" not in relative:
                relative = f"headers/{relative}"
            if not os.path.splitext(relative)[1]:
                relative = f"{relative}.webp"
            header_image_path = relative
            base_url = (Config.SUPABASE_URL or "").rstrip("/")
            if base_url:
                header_image_url = (
                    f"{base_url}/storage/v1/object/public/lesson-images/{relative}"
                )

    resolved["header_img"] = raw_header_img or None
    resolved["header_image_path"] = header_image_path
    resolved["header_image_url"] = header_image_url

    # sections
    resolved_sections: List[Dict[str, Any]] = []
    lesson_external_id = L.get("lesson_external_id")
    audio_lookup: Dict[tuple, str] = {}
    audio_cache_hit = False
    if lesson_external_id:
        audio_snippets, audio_cache_hit = _get_cached_audio_snippets(lesson_external_id)
        audio_lookup = {
            (a["section"], a["seq"]): a["audio_key"]
            for a in audio_snippets
            if a.get("audio_key")
        }

    common_mistake_items = []
    for item in raw.get("common_mistakes", []) or []:
        item_en_nodes = _normalize_rich_nodes(item.get("content_jsonb") or [], lang)
        _enrich_image_nodes(item_en_nodes, images_lookup)
        if lesson_external_id:
            for node in item_en_nodes:
                if (
                    node.get("audio_section")
                    and node.get("audio_seq")
                    and not node.get("audio_key")
                ):
                    lookup_key = (node["audio_section"], node["audio_seq"])
                    if lookup_key in audio_lookup:
                        node["audio_key"] = audio_lookup[lookup_key]
                if not node.get("audio_key"):
                    _inject_audio_metadata([node], "common_mistake")

        item_th_nodes = (
            _normalize_rich_nodes(item.get("content_jsonb_th") or [], lang)
            if item.get("content_jsonb_th")
            else None
        )
        if item_th_nodes:
            _enrich_image_nodes(item_th_nodes, images_lookup)
            if lesson_external_id:
                for node in item_th_nodes:
                    if (
                        node.get("audio_section")
                        and node.get("audio_seq")
                        and not node.get("audio_key")
                    ):
                        lookup_key = (node["audio_section"], node["audio_seq"])
                        if lookup_key in audio_lookup:
                            node["audio_key"] = audio_lookup[lookup_key]
                    if not node.get("audio_key"):
                        _inject_audio_metadata([node], "common_mistake")

        common_mistake_items.append(
            {
                "id": item.get("id"),
                "lesson_id": item.get("lesson_id"),
                "mistake_code": item.get("mistake_code"),
                "title": item.get("title"),
                "title_th": item.get("title_th"),
                "sort_order": item.get("sort_order"),
                "scm": bool(item.get("scm")),
                "content_jsonb": item_en_nodes,
                "content_jsonb_th": item_th_nodes,
            }
        )

    for s in raw["sections"]:
        section_type = (s.get("type") or "").lower()

        # ---- special case for phrases/verbs ----
        if section_type in ["phrases_verbs", "phrases & verbs"]:
            content_nodes = _normalize_rich_nodes(s.get("content_jsonb") or [], lang)
            _inject_audio_metadata(content_nodes, "phrases_verbs")
            content_nodes_th = (
                _normalize_rich_nodes(s.get("content_jsonb_th") or [], lang)
                if s.get("content_jsonb_th")
                else None
            )
            if content_nodes_th:
                _inject_audio_metadata(content_nodes_th, "phrases_verbs")
            resolved_sections.append(
                {
                    "id": s["id"],
                    "lesson_id": s["lesson_id"],
                    "sort_order": s.get("sort_order"),
                    "type": s.get("type"),
                    "render_mode": s.get("render_mode"),
                    "audio_url": s.get("audio_url"),
                    "content": _pick_lang(s.get("content"), s.get("content_th"), lang),
                    "content_jsonb": content_nodes,
                    "content_jsonb_th": content_nodes_th,
                }
            )
            continue
        # ----------------------------------------

        raw_en_nodes = s.get("content_jsonb")
        raw_th_nodes = s.get("content_jsonb_th")
        if isinstance(raw_en_nodes, dict) or isinstance(raw_th_nodes, dict):
            preferred = raw_th_nodes if lang == "th" and isinstance(raw_th_nodes, dict) else raw_en_nodes
            resolved_sections.append(
                {
                    "id": s["id"],
                    "lesson_id": s["lesson_id"],
                    "sort_order": s.get("sort_order"),
                    "type": s.get("type"),
                    "render_mode": s.get("render_mode"),
                    "audio_url": s.get("audio_url"),
                    "content": _pick_lang(s.get("content"), s.get("content_th"), lang),
                    "content_jsonb": preferred if isinstance(preferred, dict) else None,
                    "content_jsonb_th": raw_th_nodes if isinstance(raw_th_nodes, dict) else None,
                }
            )
            continue

        en_nodes = raw_en_nodes or []
        th_nodes = raw_th_nodes or []
        merged_nodes = merge_content_nodes(en_nodes, th_nodes) if lang == "th" else en_nodes
        merged_nodes = _normalize_rich_nodes(merged_nodes, lang)
        _enrich_image_nodes(merged_nodes, images_lookup)

        # temporary audio enrichment
        if lesson_external_id:
            for node in merged_nodes:
                if (
                    node.get("audio_section")
                    and node.get("audio_seq")
                    and not node.get("audio_key")
                ):
                    lookup_key = (node["audio_section"], node["audio_seq"])
                    if lookup_key in audio_lookup:
                        node["audio_key"] = audio_lookup[lookup_key]
                if not node.get("audio_key"):
                    _inject_audio_metadata([node], s.get("type"))

        normalized_th_nodes = _normalize_rich_nodes(th_nodes, lang) if th_nodes else None
        if normalized_th_nodes:
            _enrich_image_nodes(normalized_th_nodes, images_lookup)

        if section_type == "common_mistake" and common_mistake_items:
            merged_nodes = _inject_scm_labels_into_section_nodes(
                merged_nodes,
                common_mistake_items,
                lang,
            )
            if normalized_th_nodes:
                normalized_th_nodes = _inject_scm_labels_into_section_nodes(
                    normalized_th_nodes,
                    common_mistake_items,
                    "th",
                )

        resolved_sections.append(
            {
                "id": s["id"],
                "lesson_id": s["lesson_id"],
                "sort_order": s.get("sort_order"),
                "type": s.get("type"),
                "render_mode": s.get("render_mode"),
                "audio_url": s.get("audio_url"),
                "content": _pick_lang(s.get("content"), s.get("content_th"), lang),
                "content_jsonb": merged_nodes,
                "content_jsonb_th": normalized_th_nodes,
                **({"items": common_mistake_items} if section_type == "common_mistake" else {}),
            }
        )

    # transcript
    resolved_transcript: List[Dict[str, Any]] = []
    for t in raw["transcript"]:
        resolved_transcript.append(
            {
                "id": t["id"],
                "lesson_id": t["lesson_id"],
                "sort_order": t.get("sort_order"),
                "speaker": t.get("speaker"),
                "speaker_th": t.get("speaker_th"),
                "line_text": t.get("line_text"),
                "line_text_th": t.get("line_text_th"),
            }
        )

    # comprehension questions
    rq: List[Dict[str, Any]] = []
    for q in raw["questions"]:
        opts = q.get("options_th") if (lang == "th" and q.get("options_th")) else q.get("options")
        rq.append(
            {
                "id": q["id"],
                "lesson_id": q["lesson_id"],
                "sort_order": q.get("sort_order"),
                "prompt": _pick_lang(q.get("prompt"), q.get("prompt_th"), lang),
                "answer_key": q.get("answer_key_th")
                if (lang == "th" and q.get("answer_key_th"))
                else q.get("answer_key"),
                "options": opts,
            }
        )

    # exercises
    rexs: List[Dict[str, Any]] = []
    for ex in raw["exercises"]:
        title_en = ex.get("title")
        title_th = ex.get("title_th")
        prompt_md = ex.get("prompt_md")
        prompt_en = prompt_md or ex.get("prompt")
        prompt_th = ex.get("prompt_th")
        prompt_blocks = ex.get("prompt_blocks")
        prompt_blocks_th = ex.get("prompt_blocks_th")
        paragraph_en = ex.get("paragraph")
        paragraph_th = ex.get("paragraph_th")
        items_en = _ensure_json_list(ex.get("items"))
        items_th = _ensure_json_list(ex.get("items_th"))
        options_en = _ensure_json_list(ex.get("options"))
        options_th = _ensure_json_list(ex.get("options_th"))
        answer_key_th = ex.get("answer_key_th")

        resolved_prompt_blocks = (
            prompt_blocks_th if (lang == "th" and prompt_blocks_th) else prompt_blocks
        )

        rexs.append(
            {
                "id": ex["id"],
                "lesson_id": ex["lesson_id"],
                "sort_order": ex.get("sort_order"),
                "kind": ex.get("kind"),
                "title": _pick_lang(title_en, title_th, lang),
                "title_en": title_en,
                "title_th": title_th,
                "prompt": _pick_lang(prompt_en, prompt_th, lang),
                "prompt_en": prompt_en,
                "prompt_th": prompt_th,
                "prompt_md": prompt_md,
                "prompt_blocks": resolved_prompt_blocks,
                "prompt_blocks_th": prompt_blocks_th,
                "paragraph": _pick_lang(paragraph_en, paragraph_th, lang),
                "paragraph_en": paragraph_en,
                "paragraph_th": paragraph_th,
                "items": items_th if (lang == "th" and items_th) else items_en,
                "items_en": items_en,
                "items_th": items_th,
                "options": options_en,
                "options_th": options_th,
                "answer_key": ex.get("answer_key"),
                "answer_key_th": answer_key_th,
            }
        )

    # phrases
    rphr: List[Dict[str, Any]] = []
    for link in raw["phrase_links"]:
        phrase = link.get("phrases") or {}
        lesson_id = link.get("lesson_id")
        phrase_id = phrase.get("id") or link.get("phrase_id")
        sort_order = link.get("sort_order")

        en_nodes = phrase.get("content_jsonb") or []
        th_nodes = phrase.get("content_jsonb_th") or []
        merged_nodes = merge_content_nodes(en_nodes, th_nodes) if lang == "th" else en_nodes
        merged_nodes = _normalize_rich_nodes(merged_nodes, lang)
        _enrich_image_nodes(merged_nodes, images_lookup)
        _inject_audio_metadata(merged_nodes, "phrases_verbs")

        normalized_th_nodes = _normalize_rich_nodes(th_nodes, lang) if th_nodes else None
        if normalized_th_nodes:
            _inject_audio_metadata(normalized_th_nodes, "phrases_verbs")
            _enrich_image_nodes(normalized_th_nodes, images_lookup)

        primary_id = phrase_id
        if not primary_id:
            # lesson_phrases rows do not expose a primary key; synthesize a stable fallback
            lesson_part = lesson_id or ""
            phrase_part = link.get("phrase_id") or ""
            primary_id = f"{lesson_part}:{phrase_part}:{sort_order}"

        rphr.append(
            {
                "id": primary_id,
                "lesson_id": lesson_id,
                "sort_order": sort_order,
                "phrase_id": link.get("phrase_id") or phrase_id,
                "phrase": phrase.get("phrase"),
                "phrase_th": phrase.get("phrase_th"),
                "content": _pick_lang(phrase.get("content"), phrase.get("content_th"), lang),
                "content_th": phrase.get("content_th"),
                "content_md": phrase.get("content_md"),
                "content_md_th": phrase.get("content_md_th"),
                "content_jsonb": merged_nodes,
                "content_jsonb_th": normalized_th_nodes,
                "audio_url": phrase.get("audio_url"),
                "variant": phrase.get("variant"),
            }
        )

    images_dict = images_lookup

    resolved.update(
        {
            "sections": resolved_sections,
            "transcript": resolved_transcript,
            "questions": rq,
            "practice_exercises": rexs,
            "phrases": rphr,
            "images": images_dict,
        }
    )

    transform_ms = _elapsed_ms(transform_start)
    total_ms = _elapsed_ms(route_start)
    print(
        f"[lesson-resolver] resolved lesson_id={lesson_id} lang={lang} "
        f"fetch_ms={fetch_ms} transform_ms={transform_ms} total_ms={total_ms} "
        f"audio_cache_hit={audio_cache_hit} "
        f"sections={len(resolved_sections)} transcript={len(resolved_transcript)} "
        f"questions={len(rq)} exercises={len(rexs)} phrases={len(rphr)}",
        flush=True,
    )

    _resolved_lesson_cache[cache_key] = {
        "data": copy.deepcopy(resolved),
        "timestamp": time.time(),
    }
    return copy.deepcopy(resolved)

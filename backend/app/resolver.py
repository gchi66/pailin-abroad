# app/resolver.py
import os
import re
import json
from typing import Any, Dict, List, Optional
from app.supabase_client import supabase
from app.merge_jsonb import merge_content_nodes
from app.config import Config

Lang = str  # "en" | "th"
TEXT_KINDS = {"heading", "paragraph", "list_item", "misc_item"}
AUDIO_TAG_RE = re.compile(r"\[audio:([^\]\s]+)\]", re.I)


def _exec(q):
    res = q.execute()
    if getattr(res, "error", None):
        msg = getattr(res.error, "message", None) or str(res.error)
        raise RuntimeError(msg)
    return res.data


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


def _fetch_lesson_bundle(lesson_id: str) -> Dict[str, Any]:
    lesson = _exec(
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

    sections = _exec(
        supabase.table("lesson_sections")
        .select("*")
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    transcript = _exec(
        supabase.table("transcript_lines")
        .select("*")
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    questions = _exec(
        supabase.table("comprehension_questions")
        .select("*")
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    exercises = _exec(
        supabase.table("practice_exercises")
        .select("*")
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    phrase_links = _exec(
        supabase.table("lesson_phrases")
        .select(
            "lesson_id, phrase_id, sort_order, phrases(*)"
        )
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    images = _exec(
        supabase.table("lesson_images")
        .select("image_key, url")
        .eq("lesson_id", lesson_id)
    )

    global_images = _exec(
        supabase.table("lesson_images")
        .select("image_key, url")
        .is_("lesson_id", None)
    )

    return {
        "lesson": lesson,
        "sections": sections,
        "transcript": transcript,
        "questions": questions,
        "exercises": exercises,
        "phrase_links": phrase_links,
        "images": images,
        "global_images": global_images,
    }


def resolve_lesson(lesson_id: str, lang: Lang) -> Dict[str, Any]:
    raw = _fetch_lesson_bundle(lesson_id)
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
    if lesson_external_id:
        audio_snippets = _exec(
            supabase.table("audio_snippets")
            .select("audio_key, section, seq")
            .eq("lesson_external_id", lesson_external_id)
        )
        audio_lookup = {
            (a["section"], a["seq"]): a["audio_key"]
            for a in audio_snippets
            if a.get("audio_key")
        }

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

    return resolved

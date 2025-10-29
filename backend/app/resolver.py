# app/resolver.py
import os
from typing import Any, Dict, List, Optional
from app.supabase_client import supabase
from app.merge_jsonb import merge_content_nodes
from app.config import Config

Lang = str  # "en" | "th"

TEXT_KINDS = {"heading", "paragraph", "list_item", "misc_item"}


def _exec(q):
    res = q.execute()
    if getattr(res, "error", None):  # supabase-py v2 errors live on res.error; stringify safely
        msg = getattr(res.error, "message", None) or str(res.error)
        raise RuntimeError(msg)
    return res.data

def _pick_lang(en: Optional[Any], th: Optional[Any], lang: Lang) -> Optional[str]:
    def clean(v):
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return None  # don’t try to treat JSON as a string
        s = str(v).strip()
        return s if s != "" else None

    if lang == "th":
        return clean(th) or clean(en)
    return clean(en) or clean(th)

def _inline_from_text_value(val, lang: Lang) -> Optional[Dict[str, Any]]:
    """Build a single inline dict from a 'text' value that may be str or {en, th}."""
    if val is None:
        return None
    # if it's already a dict of language strings
    if isinstance(val, dict):
        # pick language-specific string
        chosen = val.get("th") if lang == "th" else val.get("en")
        if chosen is None:
            # fallbacks
            chosen = next((v for v in val.values() if isinstance(v, str) and v.strip()), None)
        if chosen is None:
            return None
        return {"bold": False, "italic": False, "underline": False, "text": str(chosen)}
    # if it's a raw string
    s = str(val).strip()
    if not s:
        return None
    return {"bold": False, "italic": False, "underline": False, "text": s}

def _normalize_rich_nodes(nodes: Any, lang: Lang) -> List[Dict[str, Any]]:
    """Ensure every text node in content_jsonb has an 'inlines' array.
    Also tolerates malformed/mixed shapes from legacy TH JSON."""
    out: List[Dict[str, Any]] = []
    if not nodes:
        return out
    if not isinstance(nodes, list):
        # sometimes saved as JSON object accidentally; ignore rather than crash
        return out
    for n in nodes:
        if not isinstance(n, dict):
            continue
        kind = n.get("kind") or n.get("type")
        node = dict(n)  # shallow copy
        # For text-ish nodes, ensure inlines exists
        if kind in TEXT_KINDS:
            inlines = node.get("inlines")
            if not isinstance(inlines, list) or not inlines:
                inline = _inline_from_text_value(node.get("text"), lang)
                if inline:
                    node["inlines"] = [inline]
                else:
                    # guarantee an array so UI can safely map()
                    node["inlines"] = []
        # Debug: check if audio_key exists
        if node.get("audio_key"):
            print(f"🎵 _normalize_rich_nodes preserving audio_key: {node.get('audio_key')} for kind: {kind}")

        # Normalize table cells (optional: keep as-is)
        out.append(node)
    return out

def _fetch_lesson_bundle(lesson_id: str) -> Dict[str, Any]:
    # LESSON (header/scalars) - keeping original structure as no example provided
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

    # SECTIONS - based on actual example
    sections = _exec(
        supabase.table("lesson_sections")
        .select(
            "id, lesson_id, type, sort_order, render_mode, audio_url, "
            "content, content_th, content_jsonb, content_jsonb_th"
        )
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    # TRANSCRIPT - based on actual example
    transcript = _exec(
        supabase.table("transcript_lines")
        .select(
            "id, lesson_id, sort_order, "
            "speaker, speaker_th, line_text, line_text_th"
        )
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    # QUESTIONS - based on actual example
    questions = _exec(
        supabase.table("comprehension_questions")
        .select(
            "id, lesson_id, sort_order, "
            "prompt, prompt_th, answer_key, answer_key_th, "
            "options, options_th"
        )
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    # PRACTICE - based on actual example
    exercises = _exec(
        supabase.table("practice_exercises")
        .select(
            "id, lesson_id, sort_order, kind, "
            "title, title_th, prompt_md, prompt_th, "
            "paragraph, paragraph_th, items, items_th, "
            "options, answer_key"
        )
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    # PHRASES - based on actual example
    phrase_links = _exec(
        supabase.table("lesson_phrases")
        .select("sort_order, phrases(id, phrase, phrase_th, content, content_th, content_jsonb, content_jsonb_th, audio_url, variant)")
        .eq("lesson_id", lesson_id)
        .order("sort_order", desc=False)
    )

    # IMAGES - fetch lesson images for practice exercises and other content
    images = _exec(
        supabase.table("lesson_images")
        .select("image_key, url")
        .eq("lesson_id", lesson_id)
    )

    return {
        "lesson": lesson,
        "sections": sections,
        "transcript": transcript,
        "questions": questions,
        "exercises": exercises,
        "phrase_links": phrase_links,
        "images": images,
    }

def resolve_lesson(lesson_id: str, lang: Lang) -> Dict[str, Any]:
    raw = _fetch_lesson_bundle(lesson_id)

    L = raw["lesson"]
    if not L:
        raise KeyError("Lesson not found")

    resolved: Dict[str, Any] = {
        "id": L["id"],
        "stage": L.get("stage"),
        "level": L.get("level"),
        "lesson_order": L.get("lesson_order"),
        "image_url": L.get("image_url"),
        "conversation_audio_url": L.get("conversation_audio_url"),
        "lesson_external_id": L.get("lesson_external_id"),
        # scalar text with TH→EN fallback (or EN→TH if lang=en)
        "title": _pick_lang(L.get("title"), L.get("title_th"), lang),
        "subtitle": _pick_lang(L.get("subtitle"), L.get("subtitle_th"), lang),
        "focus": _pick_lang(L.get("focus"), L.get("focus_th"), lang),
        "backstory": _pick_lang(L.get("backstory"), L.get("backstory_th"), lang),
    }

    resolved.update({
        "title_en": (L.get("title") or None),
        "title_th": (L.get("title_th") or None),
        "subtitle_en": (L.get("subtitle") or None),
        "subtitle_th": (L.get("subtitle_th") or None),
        "focus_en": (L.get("focus") or None),
        "focus_th": (L.get("focus_th") or None),
        "backstory_en": (L.get("backstory") or None),
        "backstory_th": (L.get("backstory_th") or None),
    })

    raw_header_img = (L.get("header_img") or "").strip() if L else ""
    header_image_path: Optional[str] = None
    header_image_url: Optional[str] = None

    if raw_header_img:
        lowered = raw_header_img.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            header_image_url = raw_header_img
        else:
            relative = raw_header_img.lstrip("/")
            if relative.lower().startswith("lesson-images/"):
                # strip bucket name if present
                relative = relative.split("/", 1)[1]
            if "?" in relative:
                # drop query params for normalization
                relative = relative.split("?", 1)[0]
            if "#" in relative:
                relative = relative.split("#", 1)[0]
            if not relative.lower().startswith("headers/") and "/" not in relative:
                relative = f"headers/{relative}"

            filename = relative.rsplit("/", 1)[-1]
            root, ext = os.path.splitext(filename)
            if not ext:
                relative = f"{relative}.webp"

            header_image_path = relative
            base_url = (Config.SUPABASE_URL or "").rstrip("/")
            if base_url:
                header_image_url = f"{base_url}/storage/v1/object/public/lesson-images/{relative}"

    resolved["header_img"] = raw_header_img or None
    resolved["header_image_path"] = header_image_path
    resolved["header_image_url"] = header_image_url

    # Sections: deep-merge content_jsonb when lang==th; simple for titles/plain content
    resolved_sections: List[Dict[str, Any]] = []
    for s in raw["sections"]:
        en_nodes = s.get("content_jsonb") or []
        th_nodes = s.get("content_jsonb_th") or []
        
        # Debug: check raw data from database
        print(f"🎵 Raw section {s.get('type')} en_nodes with audio_key: {len([n for n in en_nodes if n.get('audio_key')])}")
        
        merged_nodes = merge_content_nodes(en_nodes, th_nodes) if lang == "th" else en_nodes
        merged_nodes = _normalize_rich_nodes(merged_nodes, lang)

        # Debug: check if audio_key exists in section nodes after processing
        audio_key_count = len([n for n in merged_nodes if n.get('audio_key')])
        if audio_key_count > 0:
            print(f"🎵 Section {s.get('type')} has {audio_key_count} nodes with audio_key after processing")
        
        # TEMPORARY FIX: Enrich nodes with audio_key from audio_snippets table
        # This should be removed once the database is re-imported with proper audio_key fields
        lesson_external_id = raw["lesson"].get("lesson_external_id")
        if lesson_external_id:
            # Fetch audio snippets for this lesson
            audio_snippets = _exec(
                supabase.table("audio_snippets")
                .select("audio_key, section, seq")
                .eq("lesson_external_id", lesson_external_id)
            )
            
            # Create a lookup map: (section, seq) -> audio_key
            audio_lookup = {}
            for snippet in audio_snippets:
                if snippet.get("audio_key") and snippet.get("section") and snippet.get("seq"):
                    audio_lookup[(snippet["section"], snippet["seq"])] = snippet["audio_key"]
            
            # Enrich nodes with audio_key
            for node in merged_nodes:
                if node.get("audio_section") and node.get("audio_seq") and not node.get("audio_key"):
                    lookup_key = (node["audio_section"], node["audio_seq"])
                    if lookup_key in audio_lookup:
                        node["audio_key"] = audio_lookup[lookup_key]
                        print(f"🎵 Enriched node with audio_key: {node['audio_key']}")

        resolved_sections.append({
            "id": s["id"],
            "lesson_id": s["lesson_id"],
            "type": s.get("type"),
            "sort_order": s.get("sort_order"),
            "render_mode": s.get("render_mode"),
            "audio_url": s.get("audio_url"),
            "content": _pick_lang(s.get("content"), s.get("content_th"), lang),
            "content_jsonb": merged_nodes,  # Use the merged and normalized nodes
            "content_jsonb_th": _normalize_rich_nodes(th_nodes, lang) if th_nodes else None,
        })

    # Transcript - only fields from actual example
    resolved_transcript: List[Dict[str, Any]] = []
    for t in raw["transcript"]:
        resolved_transcript.append({
            "id": t["id"],
            "lesson_id": t["lesson_id"],
            "sort_order": t.get("sort_order"),
            "speaker": _pick_lang(t.get("speaker"), t.get("speaker_th"), lang),
            "line_text": _pick_lang(t.get("line_text"), t.get("line_text_th"), lang),
        })

    # Questions - only fields from actual example
    rq: List[Dict[str, Any]] = []
    for q in raw["questions"]:
        # Options are stored as JSON (array). We just pass through the array for the requested language.
        opts = q.get("options_th") if (lang == "th" and q.get("options_th")) else q.get("options")
        rq.append({
            "id": q["id"],
            "lesson_id": q["lesson_id"],
            "sort_order": q.get("sort_order"),
            "prompt": _pick_lang(q.get("prompt"), q.get("prompt_th"), lang),
            "answer_key": q.get("answer_key_th") if (lang == "th" and q.get("answer_key_th")) else q.get("answer_key"),
            "options": opts,
        })

    # Exercises - only fields from actual example
    rexs: List[Dict[str, Any]] = []
    for ex in raw["exercises"]:
        title_en = ex.get("title")
        title_th = ex.get("title_th")
        prompt_md = ex.get("prompt_md")
        prompt_en = prompt_md or ex.get("prompt")
        prompt_th = ex.get("prompt_th")
        paragraph_en = ex.get("paragraph")
        paragraph_th = ex.get("paragraph_th")
        items_en = ex.get("items")
        items_th = ex.get("items_th")
        options_en = ex.get("options")
        options_th = ex.get("options_th")
        answer_key_th = ex.get("answer_key_th")

        rexs.append({
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
            "paragraph": _pick_lang(paragraph_en, paragraph_th, lang),
            "paragraph_en": paragraph_en,
            "paragraph_th": paragraph_th,
            # Localized JSON fields
            "items": items_th if (lang == "th" and items_th) else items_en,
            "items_en": items_en,
            "items_th": items_th,
            "options": options_en,
            "options_th": options_th,
            "answer_key": ex.get("answer_key"),
            "answer_key_th": answer_key_th,
        })

    # Phrases - only fields from actual example
    rphr: List[Dict[str, Any]] = []
    for row in raw["phrase_links"]:
        p = (row.get("phrases") or {})

        # Handle content_jsonb like sections
        en_nodes = p.get("content_jsonb") or []
        th_nodes = p.get("content_jsonb_th") or []
        merged_nodes = merge_content_nodes(en_nodes, th_nodes) if lang == "th" else en_nodes
        merged_nodes = _normalize_rich_nodes(merged_nodes, lang)

        rphr.append({
            "id": p.get("id"),
            "sort_order": row.get("sort_order"),
            "phrase": p.get("phrase"),  # no Thai version available
            "phrase_th": p.get("phrase_th"),
            "content": _pick_lang(p.get("content"), p.get("content_th"), lang),
            "content_jsonb": merged_nodes,
            "audio_url": p.get("audio_url"),
            "variant": p.get("variant"),
        })

    # Convert images list to a dictionary for easy lookup by image_key
    images_dict = {img["image_key"]: img["url"] for img in raw["images"]}

    resolved.update({
        "sections": resolved_sections,
        "transcript": resolved_transcript,
        "questions": rq,
        "practice_exercises": rexs,
        "phrases": rphr,
        "images": images_dict,
    })

    return resolved

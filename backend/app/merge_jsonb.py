# app/merge_jsonb.py
from typing import Any, Dict, List, Optional, Tuple
import hashlib

TEXT_KINDS = {"heading", "paragraph", "list_item", "misc_item"}

def _clean(s):
    if isinstance(s, str):
        return s.strip()
    return s or ""

def _nonempty_inlines(inlines):
    return bool(inlines) and any(_clean(i.get("text")) for i in inlines or [])

def _substantive_th_node(th: Dict[str, Any]) -> bool:
    kind = th.get("kind") or th.get("type")
    if kind in TEXT_KINDS:
        return _nonempty_inlines(th.get("inlines")) or bool(_clean(th.get("text")))
    if kind == "table" or th.get("type") == "table":
        cells = th.get("cells") or []
        return any(_clean(cell) for row in cells for cell in (row or []))
    # fallback: any meaningful field beyond pure metadata
    meta = {"audio_seq","audio_section","lesson_context","section_context","indent","level","type","kind","id","cols","rows"}
    return any(v not in (None, "", [], {}) for k,v in th.items() if k not in meta)

def _first_text_hash(node: Dict[str, Any]) -> str:
    for it in node.get("inlines") or []:
        t = _clean(it.get("text"))
        if t:
            return hashlib.sha1(t.encode()).hexdigest()[:12]
    return ""

def _soft_key(node: Dict[str, Any]) -> Tuple[Any, Any, str]:
    return (node.get("kind"), node.get("indent"), _first_text_hash(node))

def _merge_inlines(en, th):
    en, th = en or [], th or []
    if len(th) == 1 and _clean(th[0].get("text")):
        return [th[0]]
    out = []
    for i in range(max(len(en), len(th))):
        e = en[i] if i < len(en) else {}
        t = th[i] if i < len(th) else {}
        tt, et = _clean(t.get("text")), _clean(e.get("text"))
        if tt:
            merged = {**e, **{k:v for k,v in t.items() if k != "text"}}
            merged["text"] = tt
            out.append(merged)
        else:
            out.append(e if et else (t or e))
    while out and not _clean(out[-1].get("text")):
        out.pop()
    return out

def _merge_table(en, th):
    en_cells, th_cells = en.get("cells") or [], th.get("cells") or []
    shapes_match = len(en_cells) == len(th_cells) and all(len(er or []) == len(tr or []) for er,tr in zip(en_cells, th_cells))
    if not shapes_match:
        return en
    merged = []
    for er, tr in zip(en_cells, th_cells):
        merged.append([tc if _clean(tc) else ec for ec, tc in zip(er or [], tr or [])])
    out = {**en, **th}
    out["cells"] = merged
    return out

def _merge_node(en, th):
    if not th:
        return en
    if _substantive_th_node(th):
        kind = en.get("kind") or th.get("kind") or en.get("type") or th.get("type")
        if kind in TEXT_KINDS:
            base = {**en}
            base["inlines"] = _merge_inlines(en.get("inlines"), th.get("inlines"))
            return base
        if kind == "table" or en.get("type") == "table" or th.get("type") == "table":
            return _merge_table(en, th)
        merged = {**en, **th}
        for k in ("audio_seq","audio_section","lesson_context","section_context","indent","level"):
            if k in en and k not in th:
                merged[k] = en[k]
        return merged
    return en

def merge_content_nodes(en_nodes: List[Dict], th_nodes: Optional[List[Dict]]) -> List[Dict]:
    if not th_nodes:
        return en_nodes
    th_by_id = {n.get("id"): n for n in th_nodes if n.get("id")}
    th_by_audio = {(n.get("audio_seq"), n.get("audio_section")): n
                   for n in th_nodes if n.get("audio_seq") is not None and n.get("audio_section") is not None}
    th_by_soft = {_soft_key(n): n for n in th_nodes}
    used = set()
    out = []
    for idx, en in enumerate(en_nodes):
        th = None
        if en.get("id") and en["id"] in th_by_id:
            th = th_by_id[en["id"]]
        elif (en.get("audio_seq"), en.get("audio_section")) in th_by_audio:
            th = th_by_audio[(en.get("audio_seq"), en.get("audio_section"))]
        elif _soft_key(en) in th_by_soft:
            th = th_by_soft[_soft_key(en)]
        elif idx < len(th_nodes):
            th = th_nodes[idx]
        if th:
            used.add(id(th))
        out.append(_merge_node(en, th))

    unmatched_th = [n for n in th_nodes if id(n) not in used and _substantive_th_node(n)]

    if len(th_nodes) > len(en_nodes) * 1.5 and len(unmatched_th) > len(en_nodes) * 0.3:
        # This looks like a phrases-style content with interleaved translations
        # Use TH order instead of broken merged order
        return th_nodes
    else:
        # Original behavior for normal content
        for n in unmatched_th:
            out.append(n)
        return out
    return out

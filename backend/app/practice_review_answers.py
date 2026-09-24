"""Reveal polished lesson-practice answers, with a source-aware AI cache."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from flask import Blueprint, jsonify, request
from openai import OpenAI

from app.supabase_client import create_auth_client, supabase_admin


practice_review_answers = Blueprint("practice_review_answers", __name__)
REVIEW_MODEL = os.getenv("PRACTICE_REVIEW_ANSWER_MODEL", "gpt-4o-mini")


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _item_key(exercise_id: str, item: dict[str, Any], index: int) -> str:
    return str(item.get("id") or f"{exercise_id}-{index + 1}")


def _source_hash(exercise: dict[str, Any], item: dict[str, Any]) -> str:
    source = {
        "kind": exercise.get("kind"),
        "prompt": exercise.get("prompt_md"),
        "paragraph": exercise.get("paragraph"),
        "item": {key: value for key, value in item.items() if key != "review_answer"},
    }
    encoded = json.dumps(source, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _generate_review_answer(exercise: dict[str, Any], item: dict[str, Any]) -> str:
    answer = _text(item.get("answer"))
    if not answer and _text(item.get("correct")).lower() == "yes":
        answer = _text(item.get("text")) or _text(item.get("prompt"))
    if not answer:
        answers_v2 = item.get("answers_v2")
        if isinstance(answers_v2, list):
            answer = ", ".join(
                str(group[0]).strip() for group in answers_v2
                if isinstance(group, list) and group and str(group[0]).strip()
            )
    if not answer:
        raise ValueError("No accepted answer is available")

    context = {
        "exercise_type": exercise.get("kind"),
        "instruction": _text(exercise.get("prompt_md"))[:1500],
        "paragraph": _text(exercise.get("paragraph"))[:1500],
        "question": (_text(item.get("text")) or _text(item.get("prompt")))[:1500],
        "accepted_answer": answer[:500],
    }
    response = OpenAI(api_key=os.getenv("OPENAI_API_KEY")).chat.completions.create(
        model=REVIEW_MODEL,
        temperature=0,
        max_tokens=150,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Create one polished English answer to show a learner after an incorrect lesson practice attempt. "
                "Return JSON with exactly one string field named review_answer. Keep the accepted answer's "
                "meaning and scope; do not add an explanation or unrelated words. Restore capitalization, "
                "apostrophes, contractions, and appropriate punctuation. Use the question and instruction "
                "to tell whether the accepted answer is a word, a complete sentence, or a sentence fragment. "
                "For a fragment that continues into the rest of a sentence, end it with an ellipsis (…). "
                "For a single word, do not add sentence punctuation. For a complete sentence, use natural "
                "terminal punctuation. For example, if 'ive looked everywhere' is a beginning fragment, "
                "show 'I've looked everywhere…'. Do not copy the raw accepted answer without polishing it."
            )},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
    )
    payload = json.loads(response.choices[0].message.content or "{}")
    result = _text(payload.get("review_answer"))
    if not result or len(result) > 500 or "\n" in result:
        raise ValueError("Invalid generated review answer")
    return result


@practice_review_answers.post("/api/lessons/practice/review-answer")
def reveal_practice_review_answer():
    auth = request.headers.get("Authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return jsonify({"error": "Authorization required"}), 401
    try:
        user = create_auth_client().auth.get_user(token.strip()).user
        if not user or not getattr(user, "id", None):
            return jsonify({"error": "Invalid session"}), 401
    except Exception:
        return jsonify({"error": "Invalid session"}), 401

    data = request.get_json(silent=True) or {}
    exercise_id = _text(data.get("exercise_id"))
    item_key = _text(data.get("item_key"))
    if not exercise_id or not item_key:
        return jsonify({"error": "Exercise and item are required"}), 400

    try:
        response = (supabase_admin.table("practice_exercises")
                    .select("id,kind,prompt_md,paragraph,items")
                    .eq("id", exercise_id).single().execute())
        exercise = response.data if isinstance(response.data, dict) else None
    except Exception:
        return jsonify({"error": "Practice exercise is unavailable"}), 503
    if not exercise or exercise.get("kind") not in {"sentence_transform", "fill_blank"}:
        return jsonify({"error": "Practice exercise not found"}), 404

    items = exercise.get("items") or []
    found = next(
        ((item, index) for index, item in enumerate(items)
         if isinstance(item, dict) and _item_key(exercise_id, item, index) == item_key),
        None,
    )
    if not found:
        return jsonify({"error": "Practice item not found"}), 404
    item, _ = found
    authored = _text(item.get("review_answer")) or _text(item.get("display_answer"))
    if authored:
        return jsonify({"review_answer": authored, "source": "authored"})

    source_hash = _source_hash(exercise, item)
    try:
        cached_response = (supabase_admin.table("practice_review_answer_cache")
                           .select("review_answer,source_hash")
                           .eq("exercise_id", exercise_id)
                           .eq("item_key", item_key).limit(1).execute())
        cached = (cached_response.data or [None])[0]
        if cached and cached.get("source_hash") == source_hash and _text(cached.get("review_answer")):
            return jsonify({"review_answer": cached["review_answer"], "source": "cache"})
    except Exception:
        return jsonify({"error": "Answer cache is unavailable"}), 503

    try:
        review_answer = _generate_review_answer(exercise, item)
        (supabase_admin.table("practice_review_answer_cache")
         .upsert({"exercise_id": exercise_id, "item_key": item_key,
                  "source_hash": source_hash, "review_answer": review_answer},
                 on_conflict="exercise_id,item_key").execute())
    except ValueError:
        return jsonify({"error": "Answer is not available yet"}), 422
    except Exception:
        return jsonify({"error": "Could not prepare the answer right now"}), 503
    return jsonify({"review_answer": review_answer, "source": "generated"})

"""Generate polished learner-facing answers for Exercise Bank v2 questions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Mapping

from openai import OpenAI


REVIEW_ANSWER_MODEL = os.getenv("EXERCISE_BANK_REVIEW_ANSWER_MODEL", "gpt-4o-mini")
REVIEW_ANSWER_PROMPT_VERSION = "exercise-bank-review-answer-v1"
REVIEW_CONTENT_KEYS = {"review_answer", "review_answer_meta"}


def _clean_content(content: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in content.items() if key not in REVIEW_CONTENT_KEYS}


def review_answer_source_hash(
    *, exercise_type: str, display_type: str, prompt: str, content: Mapping[str, Any]
) -> str:
    source = {
        "exercise_type": exercise_type,
        "display_type": display_type,
        "prompt": prompt,
        "content": _clean_content(content),
        "prompt_version": REVIEW_ANSWER_PROMPT_VERSION,
    }
    encoded = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def existing_review_answer_is_current(
    content: Mapping[str, Any], source_hash: str
) -> bool:
    answer = content.get("review_answer")
    metadata = content.get("review_answer_meta")
    return (
        isinstance(answer, str)
        and bool(answer.strip())
        and isinstance(metadata, dict)
        and metadata.get("source_hash") == source_hash
        and metadata.get("prompt_version") == REVIEW_ANSWER_PROMPT_VERSION
    )


def _validate_review_answer(value: Any, *, require_complete_sentence: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError("AI review_answer must be a string")
    answer = " ".join(value.split()).strip()
    if not answer or len(answer) > 500:
        raise ValueError("AI review_answer is empty or too long")
    if answer.startswith(("{", "[")) or answer.endswith(("}", "]")):
        raise ValueError("AI review_answer contains unexpected structured output")
    if require_complete_sentence:
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", answer)
        if len(words) < 2 or answer[-1] not in ".?!":
            raise ValueError("AI review_answer is not a complete punctuated sentence")
    return answer


def generate_review_answer(
    *,
    exercise_type: str,
    display_type: str,
    prompt: str,
    content: Mapping[str, Any],
    client: OpenAI | None = None,
    model: str = REVIEW_ANSWER_MODEL,
) -> str:
    """Return one polished answer suitable for display after a learner attempt."""
    clean_content = _clean_content(content)
    if exercise_type == "multiple_choice":
        correct_label = str(clean_content.get("correct_option") or "").strip()
        for option in clean_content.get("options") or []:
            if isinstance(option, dict) and str(option.get("label") or "").strip() == correct_label:
                option_text = str(option.get("text") or "").strip()
                return _validate_review_answer(
                    f"{correct_label}. {option_text}" if option_text else correct_label,
                    require_complete_sentence=False,
                )
        return _validate_review_answer(correct_label, require_complete_sentence=False)

    api_key = os.getenv("OPENAI_API_KEY")
    ai_client = client or OpenAI(api_key=api_key)
    system_prompt = (
        "You create polished learner-facing answers for English grammar exercises. "
        "Return strict JSON with exactly one key: review_answer. The answer must be a complete, "
        "natural, grammatically correct English sentence. Preserve the intended meaning and apply "
        "the correction indicated by the internal accepted answers. Restore capitalization, "
        "apostrophes, contractions, and terminal punctuation. Do not include explanations, labels, "
        "alternatives, markdown, or commentary. For a correct/incorrect exercise whose sentence is "
        "already correct, return that sentence polished. For fill-in-the-blank, return the complete "
        "sentence with the blank filled. Internal answers may be normalized grading fragments and "
        "must never be copied as an incomplete display answer."
    )
    user_prompt = json.dumps(
        {
            "exercise_type": exercise_type,
            "display_type": display_type,
            "instruction": prompt,
            "question_content": clean_content,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    completion = ai_client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=180,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw = completion.choices[0].message.content or ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("AI returned invalid review-answer JSON") from exc
    return _validate_review_answer(payload.get("review_answer"))


def enrich_question_content(
    *,
    exercise_type: str,
    display_type: str,
    prompt: str,
    content: Mapping[str, Any],
    existing_content: Mapping[str, Any] | None = None,
    client: OpenAI | None = None,
    model: str = REVIEW_ANSWER_MODEL,
) -> tuple[dict[str, Any], bool]:
    """Add or reuse a generated review answer; return content and generation status."""
    enriched = dict(content)
    source_hash = review_answer_source_hash(
        exercise_type=exercise_type,
        display_type=display_type,
        prompt=prompt,
        content=enriched,
    )
    reusable = existing_content or enriched
    if existing_review_answer_is_current(reusable, source_hash):
        enriched["review_answer"] = reusable["review_answer"]
        enriched["review_answer_meta"] = dict(reusable["review_answer_meta"])
        return enriched, False

    answer = generate_review_answer(
        exercise_type=exercise_type,
        display_type=display_type,
        prompt=prompt,
        content=enriched,
        client=client,
        model=model,
    )
    enriched["review_answer"] = answer
    enriched["review_answer_meta"] = {
        "model": model,
        "prompt_version": REVIEW_ANSWER_PROMPT_VERSION,
        "source_hash": source_hash,
    }
    return enriched, True

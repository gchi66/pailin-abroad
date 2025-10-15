import json
import os
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from openai import OpenAI

from app.supabase_client import supabase

bp = Blueprint("ai_evaluate", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def _parse_ai_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse the AI response as JSON, falling back to substring parsing."""
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        snippet = raw_text[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            return None
    return None


@bp.route("/api/evaluate_answer", methods=["POST"])
def evaluate_answer():
    """
    Evaluate a learner's exercise answer with GPT and persist the AI assessment.
    """
    payload = request.get_json(silent=True) or {}

    required_fields = [
        "user_id",
        "exercise_type",
        "user_answer",
        "correct_answer",
        "source_type",
    ]
    missing = [field for field in required_fields if not payload.get(field)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    exercise_type = payload.get("exercise_type")
    if exercise_type not in {"fill_blank", "open", "sentence_transform"}:
        return jsonify({"error": "Invalid exercise_type"}), 400

    source_type = payload.get("source_type")
    if source_type not in {"bank", "practice"}:
        return jsonify({"error": "Invalid source_type"}), 400

    exercise_bank_id = payload.get("exercise_bank_id")
    practice_exercise_id = payload.get("practice_exercise_id")

    if source_type == "bank":
        if exercise_bank_id is None:
            return jsonify({"error": "exercise_bank_id is required for bank source"}), 400
        practice_exercise_id = None
    else:
        if practice_exercise_id is None:
            return jsonify({"error": "practice_exercise_id is required for practice source"}), 400
        exercise_bank_id = None

    prompt = (
        "You are an English and Thai language tutor evaluating a learner's response.\n"
        "Return a strict JSON object with the following keys: "
        '"correct" (boolean), "score" (number between 0 and 1), '
        '"feedback_en" (short English feedback), '
        '"feedback_th" (short Thai feedback).\n'
        "Consider grammar, vocabulary, and meaning when scoring."
    )

    user_message = (
        f"Exercise type: {exercise_type}\n"
        f"Expected answer: {payload['correct_answer']}\n"
        f"Learner answer: {payload['user_answer']}"
    )

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=150,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to contact AI service: {exc}"}), 500

    ai_message = ""
    try:
        choice = completion.choices[0]
        message_content = getattr(choice.message, "content", "")
        if isinstance(message_content, list):
            ai_message = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in message_content
            )
        else:
            ai_message = message_content or ""
    except (AttributeError, IndexError, TypeError):
        ai_message = ""

    # Optional: Uncomment to log the raw GPT response for debugging.
    # print("GPT raw response:", ai_message)

    parsed = _parse_ai_json(ai_message)
    if not parsed:
        return jsonify({"error": "AI returned an unreadable result"}), 500

    correct = bool(parsed.get("correct"))

    score = parsed.get("score")
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 0.0

    feedback_en = parsed.get("feedback_en") or ""
    feedback_th = parsed.get("feedback_th") or ""

    record = {
        "user_id": payload["user_id"],
        "exercise_type": exercise_type,
        "user_answer": payload["user_answer"],
        "ai_correct": correct,
        "ai_score": score,
        "ai_feedback_en": feedback_en,
        "ai_feedback_th": feedback_th,
        "ai_model": "gpt-4o-mini",
    }

    if exercise_bank_id is not None:
        record["exercise_bank_id"] = exercise_bank_id
        record["practice_exercise_id"] = None
    if practice_exercise_id is not None:
        record["practice_exercise_id"] = practice_exercise_id
        record["exercise_bank_id"] = None

    try:
        supabase_response = (
            supabase.table("user_exercise_answers").upsert(record).execute()
        )
        if getattr(supabase_response, "error", None):
            return jsonify({"error": "Failed to store AI evaluation"}), 500
    except Exception as exc:
        return jsonify({"error": f"Supabase error: {exc}"}), 500

    result = {
        "correct": correct,
        "score": score,
        "feedback_en": feedback_en,
        "feedback_th": feedback_th,
    }

    return jsonify(result), 200

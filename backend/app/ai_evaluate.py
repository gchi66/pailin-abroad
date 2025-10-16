import json
import os
import re
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, jsonify, request
from openai import OpenAI

from app.supabase_client import supabase

bp = Blueprint("ai_evaluate", __name__)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


CONTRACTIONS_MAP = {
    "i'm": "i am",
    "you're": "you are",
    "he's": "he is",
    "she's": "she is",
    "it's": "it is",
    "we're": "we are",
    "they're": "they are",
    "i've": "i have",
    "you've": "you have",
    "we've": "we have",
    "they've": "they have",
    "i'd": "i would",
    "you'd": "you would",
    "he'd": "he would",
    "she'd": "she would",
    "we'd": "we would",
    "they'd": "they would",
    "i'll": "i will",
    "you'll": "you will",
    "he'll": "he will",
    "she'll": "she will",
    "we'll": "we will",
    "they'll": "they will",
    "that's": "that is",
    "there's": "there is",
    "who's": "who is",
    "what's": "what is",
    "where's": "where is",
    "when's": "when is",
    "won't": "will not",
    "can't": "cannot",
    "shan't": "shall not",
    "don't": "do not",
    "doesn't": "does not",
    "didn't": "did not",
    "shouldn't": "should not",
    "wouldn't": "would not",
    "couldn't": "could not",
    "isn't": "is not",
    "aren't": "are not",
    "wasn't": "was not",
    "weren't": "were not",
    "hasn't": "has not",
    "haven't": "have not",
    "hadn't": "had not",
    "mustn't": "must not",
    "mightn't": "might not",
}


SYSTEM_PROMPTS = {
    "fill_blank": (
        "You are grading a fill-in-the-blank grammar question for an English learner. "
        "Address the learner directly using 'you' and 'your'. "
        "Accept contractions and equivalent grammatical forms. "
        "Allow minor spelling or plural variations if they are grammatically valid. "
        "Do not reveal the expected answer or give the solution explicitly; provide guidance instead. "
        "Always respond with strict JSON containing keys: correct (bool), score (0-1 float), "
        "feedback_en (English), feedback_th (Thai)."
    ),
    "sentence_transform": (
        "You are grading a sentence transformation exercise. "
        "Address the learner directly using 'you' and 'your'. "
        "Mark correct if the student's sentence contains or correctly applies the grammatical structure "
        "of the correct answer, even if rewritten. Do not penalize for extra words or rephrasing. "
        "Do not reveal the expected answer; offer constructive guidance only. "
        "Respond only with JSON keys: correct (bool), score (0-1 float), feedback_en, feedback_th."
    ),
    "open": (
        "You are grading a short open-ended response. "
        "Address the learner directly using 'you' and 'your'. "
        "Evaluate grammar, fluency, and relevance to the prompt. "
        "Provide a score between 0 and 1 and give concise bilingual feedback. "
        "Do not reveal the expected answer; provide guidance instead. "
        "Respond strictly with JSON keys: correct (bool), score (0-1 float), feedback_en, feedback_th."
    ),
}


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


def _value_to_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def _normalize_for_contains(text: str) -> str:
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _expand_contractions(text: str) -> str:
    lowered = text.lower().replace("’", "'")
    for contraction, expansion in CONTRACTIONS_MAP.items():
        pattern = rf"\b{re.escape(contraction)}\b"
        lowered = re.sub(pattern, expansion, lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def contractions_equivalent(user_answer: str, correct_answer: str) -> bool:
    if not user_answer or not correct_answer:
        return False
    expanded_user = _expand_contractions(user_answer)
    expanded_correct = _expand_contractions(correct_answer)
    if not expanded_user or not expanded_correct:
        return False
    if expanded_correct in expanded_user:
        return True
    if expanded_user in expanded_correct:
        return True
    return False


def get_prompt_for_type(
    exercise_type: str, question: str, user_answer: str, correct_answer: str
) -> Tuple[str, str]:
    base_prompt = SYSTEM_PROMPTS[exercise_type]
    question_block = f"Question: {question}\n" if question else ""
    expected_line = f"Expected answer: {correct_answer}\n" if correct_answer else ""
    user_prompt = (
        f"{question_block}"
        f"{expected_line}"
        f"Learner answer: {user_answer}\n"
        "Compare the learner answer to the expected answer following the instructions. "
        "Respond with JSON only."
    )
    return base_prompt, user_prompt


def evaluate_with_gpt(
    exercise_type: str, question: str, user_answer: str, correct_answer: str
) -> Dict[str, Any]:
    system_prompt, user_prompt = get_prompt_for_type(
        exercise_type, question, user_answer, correct_answer
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        max_tokens=180,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

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

    parsed = _parse_ai_json(ai_message)
    if not parsed:
        raise ValueError("AI returned an unreadable result")

    return parsed


def _personalize_feedback(text: str) -> str:
    if not text:
        return ""
    replacements = [
        (r"\bthe learner's\b", "your"),
        (r"\bthe learner\b", "you"),
        (r"\bthe student\b", "you"),
        (r"\bthe student's\b", "your"),
    ]
    sanitized = text
    for pattern, repl in replacements:
        sanitized = re.sub(pattern, repl, sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(?i)suggested answer:?[^.\n]*", "", sanitized)
    return " ".join(sanitized.split())


def _collect_answer_phrases(value: Any, phrases: set) -> None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            phrases.add(stripped)
    elif isinstance(value, dict):
        for nested in value.values():
            _collect_answer_phrases(nested, phrases)
    elif isinstance(value, list):
        for nested in value:
            _collect_answer_phrases(nested, phrases)


def _extract_answer_phrases(raw_correct: str) -> Tuple[str, ...]:
    phrases: set = set()
    if not raw_correct:
        return tuple()

    stripped = raw_correct.strip()
    if stripped:
        phrases.add(stripped)

    parsed = None
    try:
        parsed = json.loads(raw_correct)
    except Exception:
        parsed = None

    if parsed is not None:
        _collect_answer_phrases(parsed, phrases)

    extended_phrases = set(phrases)
    for phrase in list(phrases):
        tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ']+", phrase)
        for token in tokens:
            token_clean = token.strip("'").lower()
            if len(token_clean) >= 4:
                extended_phrases.add(token_clean)

    return tuple(sorted(extended_phrases, key=len, reverse=True))


def _remove_correct_answer(text: str, correct_answer_raw: str) -> str:
    if not text:
        return ""
    sanitized = text
    phrases = _extract_answer_phrases(correct_answer_raw)
    for phrase in phrases:
        if not phrase:
            continue
        pattern = re.escape(phrase)
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"\s+['\"`]{2,}\s*", " ", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


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
    missing = [field for field in required_fields if field not in payload]
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

    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return jsonify({"error": "user_id cannot be empty"}), 400

    user_answer_raw = _value_to_string(payload.get("user_answer"))
    if not user_answer_raw:
        return jsonify({"error": "user_answer cannot be empty"}), 400

    correct_answer_value = payload.get("correct_answer")
    correct_answer_raw = _value_to_string(correct_answer_value)
    if exercise_type in {"fill_blank", "sentence_transform"} and not correct_answer_raw:
        return jsonify({"error": "correct_answer cannot be empty for this exercise"}), 400

    question_text = (
        payload.get("question")
        or payload.get("question_prompt")
        or payload.get("question_text")
        or ""
    )

    normalized_user = _normalize_for_contains(user_answer_raw)
    normalized_correct = _normalize_for_contains(correct_answer_raw)

    used_contains = False
    used_contractions = False
    used_gpt = False

    result_payload: Dict[str, Any] = {}
    ai_model_used = "gpt-4o-mini"

    if normalized_user and normalized_correct and normalized_correct in normalized_user:
        used_contains = True
        result_payload = {
            "correct": True,
            "score": 1.0,
            "feedback_en": "Great job! Your answer matches the expected solution.",
            "feedback_th": "เยี่ยมมาก! คำตอบของคุณตรงกับที่คาดไว้",
        }
        ai_model_used = "rule:contains"
    elif contractions_equivalent(user_answer_raw, correct_answer_raw):
        used_contractions = True
        result_payload = {
            "correct": True,
            "score": 1.0,
            "feedback_en": "Nice work! Contraction and full form are equivalent here.",
            "feedback_th": "ทำได้ดี! รูปย่อและรูปเต็มมีความหมายเท่ากันในบริบทนี้",
        }
        ai_model_used = "rule:contraction"
    else:
        used_gpt = True
        try:
            parsed = evaluate_with_gpt(
                exercise_type=exercise_type,
                question=question_text,
                user_answer=user_answer_raw,
                correct_answer=correct_answer_raw,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500
        except Exception as exc:
            return jsonify({"error": f"Failed to contact AI service: {exc}"}), 500

        correct = bool(parsed.get("correct"))
        score_value = parsed.get("score")
        try:
            score_value = float(score_value)
        except (TypeError, ValueError):
            score_value = 1.0 if correct else 0.0
        score_value = max(0.0, min(1.0, score_value))

        result_payload = {
            "correct": correct,
            "score": score_value,
            "feedback_en": parsed.get("feedback_en") or "",
            "feedback_th": parsed.get("feedback_th") or "",
        }

    print(
        f"Evaluation path: contains={used_contains}, "
        f"contractions={used_contractions}, gpt_called={used_gpt}"
    )

    correct_flag = bool(result_payload.get("correct"))
    score = result_payload.get("score")
    try:
        score = float(score)
    except (TypeError, ValueError):
        score = 1.0 if correct_flag else 0.0
    score = max(0.0, min(1.0, score))

    feedback_en = result_payload.get("feedback_en") or ""
    feedback_th = result_payload.get("feedback_th") or ""

    feedback_en = _remove_correct_answer(
        _personalize_feedback(feedback_en), correct_answer_raw
    )
    feedback_th = _remove_correct_answer(feedback_th, correct_answer_raw)

    record = {
        "user_id": user_id,
        "exercise_type": exercise_type,
        "user_answer": user_answer_raw,
        "ai_correct": correct_flag,
        "ai_score": score,
        "ai_feedback_en": feedback_en,
        "ai_feedback_th": feedback_th,
        "ai_model": ai_model_used,
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
        "correct": correct_flag,
        "score": score,
        "feedback_en": feedback_en,
        "feedback_th": feedback_th,
    }

    return jsonify(result), 200

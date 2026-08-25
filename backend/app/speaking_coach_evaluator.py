"""Provider-independent Azure Speech plus text-only Gemini evaluation."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.config import Config
from app.speaking_coach_audio import AudioNormalizationError, normalize_speaking_audio
from app.speaking_coach_azure import (
    AZURE_SPEECH_MODEL,
    AzureSpeechError,
    AzureSpeechResult,
    assess_with_azure_speech,
)


PROMPT_VERSION = "speaking-coach-hybrid-v1"
EVALUATOR_SCHEMA_VERSION = "speaking-evaluation-v1"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MIN_RECOGNITION_CONFIDENCE = 0.35
MAX_DISPLAYED_ISSUES = 2
FOCUS_WORD_ACCURACY_THRESHOLD = 70
FOCUS_PHONEME_ACCURACY_THRESHOLD = 45
FOCUS_SYLLABLE_ACCURACY_THRESHOLD = 50
FOCUS_COMPLETENESS_SUPPORT_THRESHOLD = 85
SEVERE_WORD_ACCURACY_THRESHOLD = 45
SEVERE_PHONEME_ACCURACY_THRESHOLD = 15
LOW_COMPLETENESS_THRESHOLD = 70
SEVERE_CANDIDATE_PRIORITY = 70


class EvaluationStatus(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    CONTINUE_WITH_CORRECTION = "continue_with_correction"
    UNCLEAR_AUDIO = "unclear_audio"


class IssueCategory(str, Enum):
    FOCUS = "focus"
    MEANING = "meaning"
    RELEVANCE = "relevance"
    GRAMMAR = "grammar"
    VOCABULARY = "vocabulary"
    PRONUNCIATION = "pronunciation"
    INTELLIGIBILITY = "intelligibility"
    AUDIO_QUALITY = "audio_quality"


class EvaluationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: IssueCategory
    description_en: str = Field(min_length=1, max_length=240)
    description_th: str = Field(min_length=1, max_length=300)


class ContentEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meaning_correct: bool | None = None
    relevant: bool | None = None
    target_usage_correct: bool | None = None
    grammar_correct: bool | None = None


class AssessmentTokenStatus(str, Enum):
    CLEAR = "clear"
    NEEDS_WORK = "needs_work"
    MISSING = "missing"


class PronunciationAssessmentToken(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=80)
    status: AssessmentTokenStatus = AssessmentTokenStatus.CLEAR
    issue_index: int | None = Field(default=None, ge=0, le=2)


class PronunciationEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intelligible: bool | None = None
    issues: list[EvaluationIssue] = Field(default_factory=list, max_length=8)
    assessment_tokens: list[PronunciationAssessmentToken] = Field(
        default_factory=list, max_length=100
    )


class SpeakingEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EvaluationStatus
    transcript: str | None = Field(default=None, max_length=1000)
    content: ContentEvaluation
    pronunciation: PronunciationEvaluation
    detected_issues: list[EvaluationIssue] = Field(default_factory=list, max_length=12)
    displayed_issues: list[EvaluationIssue] = Field(default_factory=list, max_length=3)
    corrected_answer: str | None = Field(default=None, max_length=1000)
    feedback_en: str = Field(min_length=1, max_length=500)
    feedback_th: str = Field(min_length=1, max_length=700)
    retry_focus: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_status_fields(self) -> "SpeakingEvaluation":
        if self.status == EvaluationStatus.UNCLEAR_AUDIO:
            self.detected_issues = []
            self.displayed_issues = []
            self.retry_focus = []
            self.corrected_answer = None
        elif self.status == EvaluationStatus.RETRY and not self.retry_focus:
            raise ValueError("retry requires at least one retry_focus item")
        elif (
            self.status == EvaluationStatus.CONTINUE_WITH_CORRECTION
            and not self.corrected_answer
        ):
            raise ValueError("continue_with_correction requires corrected_answer")
        return self


class LanguageEvaluation(BaseModel):
    """Gemini's language-only result; the backend owns final status."""

    model_config = ConfigDict(extra="forbid")

    material_error: bool
    content: ContentEvaluation
    detected_issues: list[EvaluationIssue] = Field(default_factory=list, max_length=12)
    displayed_issues: list[EvaluationIssue] = Field(default_factory=list, max_length=3)
    corrected_answer: str | None = Field(default=None, max_length=1000)
    feedback_en: str = Field(min_length=1, max_length=500)
    feedback_th: str = Field(min_length=1, max_length=700)
    retry_focus: list[str] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def validate_language_findings(self) -> "LanguageEvaluation":
        forbidden = {
            IssueCategory.PRONUNCIATION,
            IssueCategory.INTELLIGIBILITY,
            IssueCategory.AUDIO_QUALITY,
        }
        if any(issue.category in forbidden for issue in self.detected_issues):
            raise ValueError("text evaluator cannot return speech or audio issues")
        if any(issue.category in forbidden for issue in self.displayed_issues):
            raise ValueError("text evaluator cannot display speech or audio issues")
        if self.material_error and not (self.retry_focus or self.displayed_issues):
            raise ValueError("material_error requires an actionable issue")
        return self


class EvaluatorError(RuntimeError):
    """Safe provider error with a stable application failure code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class EvaluatorResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    evaluation: SpeakingEvaluation
    provider: str
    model: str
    latency_ms: int
    usage: dict[str, Any]
    provider_metadata: dict[str, Any]
    provider_output_text: str
    evaluation_context: dict[str, Any]


class GeminiLanguageResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    evaluation: LanguageEvaluation
    model: str
    latency_ms: int
    usage: dict[str, Any]
    provider_metadata: dict[str, Any]
    provider_output_text: str


def _language_system_instructions(instructional_attempt_number: int) -> str:
    attempt_rules = (
        "This is Attempt 1. Mark material_error only for one meaningful, "
        "correctable language or meaning problem."
        if instructional_attempt_number == 1
        else "This is a follow-up. Primarily check whether the previous retry focus "
        "was fixed; introduce a new issue only when it is severe."
    )
    return f"""
You evaluate the language content of a short English answer from a Thai learner.
You receive Azure Speech transcripts and confidence data, never audio. Evaluate only
meaning, relevance, grammar, vocabulary, and exercise-specific target usage. Never
make a pronunciation, phoneme, accent, intelligibility, or audio-quality claim.

Treat transcript alternatives as uncertain recognition evidence. Do not confidently
criticize a word when credible alternatives disagree about it. For open speaking,
accept varied relevant answers. For translation, accept natural semantic equivalents
rather than exact strings. Apply the private FOCUS rubric before general refinement.
Ignore minor imperfections that do not justify asking the learner to record again.
Normally display one issue, at most two. Feedback must be concise, encouraging,
actionable, and bilingual. {attempt_rules}

Return only the requested structured language evaluation. Do not return a final
application status; the backend derives it.
""".strip()


def _evaluation_context(
    *,
    practice_type: str,
    focus: str,
    prompt_en: str | None,
    prompt_th: str | None,
    target_answers: list[str],
    examples: list[dict[str, Any]],
    instructional_attempt_number: int,
    previous_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "practice_type": practice_type,
        "focus": focus,
        "prompt_en": prompt_en,
        "prompt_th": prompt_th,
        "target_answers": target_answers,
        "examples": examples,
        "instructional_attempt_number": instructional_attempt_number,
        "previous_evaluation": previous_evaluation,
    }


def _extract_output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    for collection_key in ("steps", "outputs", "output"):
        collection = payload.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    if part["text"].strip():
                        return part["text"].strip()
    raise EvaluatorError(
        "gemini_output_missing", "Gemini returned no structured output text."
    )


def _gemini_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in ("id", "object", "status", "model", "created_at"):
        if payload.get(key) is not None:
            metadata[key] = payload[key]
    steps = payload.get("steps")
    if isinstance(steps, list):
        metadata["step_types"] = [
            step.get("type") for step in steps if isinstance(step, dict)
        ]
    return metadata


def _normalize_attempt_status(
    evaluation: SpeakingEvaluation, instructional_attempt_number: int
) -> SpeakingEvaluation:
    if (
        instructional_attempt_number == 1
        and evaluation.status == EvaluationStatus.CONTINUE_WITH_CORRECTION
    ):
        evaluation.status = EvaluationStatus.RETRY
        if not evaluation.retry_focus:
            evaluation.retry_focus = [
                issue.description_en for issue in evaluation.displayed_issues[:2]
            ] or ["the main correction"]
    return SpeakingEvaluation.model_validate(evaluation.model_dump())


def _unclear_audio_evaluation(transcript: str | None = None) -> SpeakingEvaluation:
    return SpeakingEvaluation(
        status=EvaluationStatus.UNCLEAR_AUDIO,
        transcript=transcript,
        content=ContentEvaluation(),
        pronunciation=PronunciationEvaluation(intelligible=None),
        feedback_en="I couldn't hear that clearly. Please record it once more.",
        feedback_th="ยังฟังไม่ชัดเจน กรุณาลองอัดเสียงอีกครั้ง",
    )


def _azure_is_unclear(result: AzureSpeechResult) -> bool:
    if result.recognition_status.lower() != "success" or not result.transcript:
        return True
    return (
        result.confidence is not None
        and result.confidence < MIN_RECOGNITION_CONFIDENCE
    )


@dataclass
class _PronunciationCandidate:
    word_index: int | None
    focus_match: bool
    severity: int
    status: AssessmentTokenStatus
    issue: EvaluationIssue


def _normalized_match_text(value: str) -> str:
    return value.lower().replace("’", "'")


def _focus_matches_word(word: str, focus: str) -> bool:
    normalized_word = _normalized_match_text(word)
    normalized_focus = _normalized_match_text(focus)
    if re.search(
        rf"(?<![a-z0-9]){re.escape(normalized_word)}(?![a-z0-9])",
        normalized_focus,
    ):
        return True
    if "'" in normalized_word and "contraction" in normalized_focus:
        return True
    return normalized_word.endswith("ing") and (
        "-ing" in normalized_focus or "/ɪŋ/" in normalized_focus
    )


def _nested_accuracy_score(item: dict[str, Any]) -> float | None:
    value = item.get("AccuracyScore")
    if not isinstance(value, bool) and isinstance(value, (int, float)):
        return float(value)
    nested = item.get("PronunciationAssessment")
    if isinstance(nested, dict):
        nested_value = nested.get("AccuracyScore")
        if not isinstance(nested_value, bool) and isinstance(
            nested_value, (int, float)
        ):
            return float(nested_value)
    return None


def _lowest_scored_item(
    items: list[dict[str, Any]], name_key: str
) -> tuple[str, float] | None:
    scored: list[tuple[str, float]] = []
    for item in items:
        name = item.get(name_key)
        score = _nested_accuracy_score(item)
        if isinstance(name, str) and name.strip() and score is not None:
            scored.append((name.strip(), score))
    return min(scored, key=lambda item: item[1]) if scored else None


def _expected_phoneme_is_not_leading(
    items: list[dict[str, Any]], expected_phoneme: str | None
) -> bool:
    if not expected_phoneme:
        return False
    expected = expected_phoneme.strip().lower()
    for item in items:
        phoneme = item.get("Phoneme")
        if not isinstance(phoneme, str) or phoneme.strip().lower() != expected:
            continue
        candidates = item.get("NBestPhonemes")
        nested = item.get("PronunciationAssessment")
        if not isinstance(candidates, list) and isinstance(nested, dict):
            candidates = nested.get("NBestPhonemes")
        if not isinstance(candidates, list) or not candidates:
            return False
        leading = candidates[0]
        if not isinstance(leading, dict):
            return False
        leading_phoneme = leading.get("Phoneme")
        return isinstance(leading_phoneme, str) and (
            leading_phoneme.strip().lower() != expected
        )
    return False


def _focus_phoneme_candidate(
    items: list[dict[str, Any]],
) -> tuple[str, float] | None:
    scored: list[tuple[str, float]] = []
    mismatched: list[tuple[str, float]] = []
    for item in items:
        name = item.get("Phoneme")
        score = _nested_accuracy_score(item)
        if not isinstance(name, str) or not name.strip() or score is None:
            continue
        candidate = (name.strip(), score)
        scored.append(candidate)
        if (
            score <= FOCUS_PHONEME_ACCURACY_THRESHOLD
            and _expected_phoneme_is_not_leading(items, candidate[0])
        ):
            mismatched.append(candidate)
    pool = mismatched or scored
    return min(pool, key=lambda candidate: candidate[1]) if pool else None


def _word_issue(
    *,
    word: str,
    phoneme: str | None,
    focus_match: bool,
    final_phoneme: bool,
) -> EvaluationIssue:
    category = IssueCategory.FOCUS if focus_match else IssueCategory.PRONUNCIATION
    if phoneme and focus_match:
        return EvaluationIssue(
            category=category,
            description_en=f"Make the /{phoneme}/ sound in '{word}' clear.",
            description_th=f"ออกเสียง /{phoneme}/ ในคำว่า '{word}' ให้ชัดเจน",
        )
    if phoneme and final_phoneme:
        return EvaluationIssue(
            category=category,
            description_en=f"Finish '{word}' with a clear /{phoneme}/ sound.",
            description_th=f"ออกเสียงท้ายคำว่า '{word}' ด้วยเสียง /{phoneme}/ ให้ชัดเจน",
        )
    if phoneme:
        return EvaluationIssue(
            category=category,
            description_en=f"Practice the /{phoneme}/ sound in '{word}'.",
            description_th=f"ฝึกเสียง /{phoneme}/ ในคำว่า '{word}'",
        )
    return EvaluationIssue(
        category=category,
        description_en=f"Say '{word}' again slowly and clearly.",
        description_th=f"ลองพูดคำว่า '{word}' อีกครั้งอย่างช้า ๆ และชัดเจน",
    )


def _select_display_candidates(
    candidates: list[_PronunciationCandidate],
) -> list[_PronunciationCandidate]:
    ordered = sorted(
        candidates,
        key=lambda candidate: (candidate.focus_match, candidate.severity),
        reverse=True,
    )
    selected: list[_PronunciationCandidate] = []
    focus_candidate = next(
        (candidate for candidate in ordered if candidate.focus_match), None
    )
    if focus_candidate:
        selected.append(focus_candidate)
    severe_off_focus = next(
        (
            candidate
            for candidate in ordered
            if not candidate.focus_match
            and candidate.severity >= SEVERE_CANDIDATE_PRIORITY
        ),
        None,
    )
    if severe_off_focus and severe_off_focus not in selected:
        selected.append(severe_off_focus)
    for candidate in ordered:
        if len(selected) >= MAX_DISPLAYED_ISSUES:
            break
        if candidate not in selected:
            selected.append(candidate)
    return selected[:MAX_DISPLAYED_ISSUES]


def _assessment_tokens(
    reference_text: str,
    azure: AzureSpeechResult,
    displayed: list[_PronunciationCandidate],
) -> list[PronunciationAssessmentToken]:
    if not azure.pronunciation:
        return []
    issue_by_word_index = {
        candidate.word_index: (index, candidate.status)
        for index, candidate in enumerate(displayed)
        if candidate.word_index is not None
    }
    raw_tokens = re.findall(
        r"\s+|[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*|[^\w\s]",
        reference_text,
    )
    result: list[PronunciationAssessmentToken] = []
    azure_index = 0
    for token in raw_tokens:
        is_word = bool(re.fullmatch(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*", token))
        if not is_word:
            result.append(PronunciationAssessmentToken(text=token))
            continue
        while (
            azure_index < len(azure.pronunciation.words)
            and azure.pronunciation.words[azure_index].error_type.lower()
            == "insertion"
        ):
            azure_index += 1
        annotation = issue_by_word_index.get(azure_index)
        if annotation:
            issue_index, status = annotation
            result.append(
                PronunciationAssessmentToken(
                    text=token,
                    status=status,
                    issue_index=issue_index,
                )
            )
        else:
            result.append(PronunciationAssessmentToken(text=token))
        azure_index += 1
    return result


def _pronunciation_evaluation(
    azure: AzureSpeechResult,
    *,
    reference_text: str,
    focus: str,
) -> SpeakingEvaluation:
    if _azure_is_unclear(azure):
        return _unclear_audio_evaluation(azure.transcript)
    assessment = azure.pronunciation
    if assessment is None:
        raise EvaluatorError(
            "azure_assessment_missing",
            "Azure returned recognition without pronunciation assessment data.",
        )

    candidates: list[_PronunciationCandidate] = []
    has_content_miscue = False
    for word_index, word in enumerate(assessment.words):
        error_type = word.error_type.lower()
        focus_match = _focus_matches_word(word.word, focus)
        lowest_phoneme = (
            _focus_phoneme_candidate(word.phonemes)
            if focus_match
            else _lowest_scored_item(word.phonemes, "Phoneme")
        )
        lowest_syllable = _lowest_scored_item(word.syllables, "Syllable")
        phoneme_name = lowest_phoneme[0] if lowest_phoneme else None
        phoneme_score = lowest_phoneme[1] if lowest_phoneme else None
        syllable_score = lowest_syllable[1] if lowest_syllable else None
        final_phoneme = bool(
            lowest_phoneme
            and word.phonemes
            and word.phonemes[-1].get("Phoneme") == phoneme_name
        )
        focus_phoneme_support = sum(
            (
                syllable_score is not None
                and syllable_score <= FOCUS_SYLLABLE_ACCURACY_THRESHOLD,
                word.accuracy_score is not None
                and word.accuracy_score <= FOCUS_WORD_ACCURACY_THRESHOLD,
                assessment.completeness_score is not None
                and assessment.completeness_score
                < FOCUS_COMPLETENESS_SUPPORT_THRESHOLD,
                _expected_phoneme_is_not_leading(
                    word.phonemes, phoneme_name
                ),
            )
        )
        if error_type == "omission":
            has_content_miscue = True
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=100,
                    status=AssessmentTokenStatus.MISSING,
                    issue=EvaluationIssue(
                        category=IssueCategory.FOCUS,
                        description_en=f"Include the missing word '{word.word}'.",
                        description_th=f"อย่าลืมพูดคำว่า '{word.word}'",
                    ),
                )
            )
        elif error_type == "insertion":
            has_content_miscue = True
            candidates.append(
                _PronunciationCandidate(
                    word_index=None,
                    focus_match=focus_match,
                    severity=95,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    issue=EvaluationIssue(
                        category=IssueCategory.FOCUS,
                        description_en=f"Leave out the extra word '{word.word}'.",
                        description_th=f"ตัดคำที่เกินมา '{word.word}' ออก",
                    ),
                )
            )
            continue

        focus_phoneme_problem = (
            focus_match
            and phoneme_score is not None
            and phoneme_score <= FOCUS_PHONEME_ACCURACY_THRESHOLD
            and focus_phoneme_support >= 2
        )
        focus_word_problem = (
            focus_match
            and word.accuracy_score is not None
            and word.accuracy_score <= FOCUS_WORD_ACCURACY_THRESHOLD
        )
        severe_word_problem = (
            not focus_match
            and word.accuracy_score is not None
            and word.accuracy_score <= SEVERE_WORD_ACCURACY_THRESHOLD
            and (
                error_type == "mispronunciation"
                or (
                    phoneme_score is not None
                    and phoneme_score <= SEVERE_PHONEME_ACCURACY_THRESHOLD
                )
            )
        )
        if focus_phoneme_problem or focus_word_problem or severe_word_problem:
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=(
                        90
                        if focus_phoneme_problem
                        else 80 if focus_word_problem else 70
                    ),
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    issue=_word_issue(
                        word=word.word,
                        phoneme=phoneme_name,
                        focus_match=focus_match,
                        final_phoneme=final_phoneme,
                    ),
                )
            )

    if (
        not candidates
        and assessment.accuracy_score is not None
        and assessment.accuracy_score <= SEVERE_WORD_ACCURACY_THRESHOLD
    ):
        candidates.append(
            _PronunciationCandidate(
                word_index=None,
                focus_match=False,
                severity=60,
                status=AssessmentTokenStatus.NEEDS_WORK,
                issue=EvaluationIssue(
                    category=IssueCategory.PRONUNCIATION,
                    description_en="Try the sentence once more, slowly and clearly.",
                    description_th="ลองพูดประโยคอีกครั้งอย่างช้า ๆ และชัดเจน",
                ),
            )
        )
    if (
        not candidates
        and assessment.completeness_score is not None
        and assessment.completeness_score < LOW_COMPLETENESS_THRESHOLD
    ):
        candidates.append(
            _PronunciationCandidate(
                word_index=None,
                focus_match=True,
                severity=75,
                status=AssessmentTokenStatus.MISSING,
                issue=EvaluationIssue(
                    category=IssueCategory.FOCUS,
                    description_en="Say the complete target sentence once more.",
                    description_th="ลองพูดประโยคเป้าหมายให้ครบอีกครั้ง",
                ),
            )
        )

    ordered_candidates = sorted(
        candidates,
        key=lambda candidate: (candidate.focus_match, candidate.severity),
        reverse=True,
    )
    displayed_candidates = _select_display_candidates(candidates)
    detected = [candidate.issue for candidate in ordered_candidates[:12]]
    displayed = [candidate.issue for candidate in displayed_candidates]
    assessment_tokens = _assessment_tokens(
        reference_text, azure, displayed_candidates
    )
    if not displayed:
        return SpeakingEvaluation(
            status=EvaluationStatus.PASS,
            transcript=azure.transcript,
            content=ContentEvaluation(
                meaning_correct=True,
                relevant=True,
                target_usage_correct=True,
                grammar_correct=True,
            ),
            pronunciation=PronunciationEvaluation(
                intelligible=True,
                assessment_tokens=_assessment_tokens(reference_text, azure, []),
            ),
            feedback_en="Clear and complete—nice work!",
            feedback_th="ชัดเจนและครบถ้วน ทำได้ดีมาก!",
        )

    return SpeakingEvaluation(
        status=EvaluationStatus.RETRY,
        transcript=azure.transcript,
        content=ContentEvaluation(
            meaning_correct=not has_content_miscue,
            relevant=True,
            target_usage_correct=not has_content_miscue,
            grammar_correct=not has_content_miscue,
        ),
        pronunciation=PronunciationEvaluation(
            intelligible=True,
            issues=detected,
            assessment_tokens=assessment_tokens,
        ),
        detected_issues=detected,
        displayed_issues=displayed,
        corrected_answer=reference_text,
        feedback_en=(
            displayed[0].description_en
            if len(displayed) == 1
            else "Focus on these two parts, then try once more."
        ),
        feedback_th=(
            displayed[0].description_th
            if len(displayed) == 1
            else "เน้นสองจุดนี้ แล้วลองพูดอีกครั้ง"
        ),
        retry_focus=[issue.description_en for issue in displayed],
    )


def evaluate_language_with_gemini(
    *,
    azure: AzureSpeechResult,
    evaluation_context: dict[str, Any],
    instructional_attempt_number: int,
) -> GeminiLanguageResult:
    api_key = (Config.GEMINI_API_KEY or "").strip()
    model = (Config.SPEAKING_COACH_MODEL or "gemini-3.5-flash-lite").strip()
    if not api_key:
        raise EvaluatorError(
            "gemini_not_configured", "GEMINI_API_KEY is not configured."
        )

    speech_evidence = {
        "transcript": azure.transcript,
        "confidence": azure.confidence,
        "alternatives": [
            item.model_dump(mode="json") for item in azure.alternatives
        ],
    }
    request_context = {**evaluation_context, "azure_speech": speech_evidence}
    request_payload = {
        "model": model,
        "system_instruction": _language_system_instructions(
            instructional_attempt_number
        ),
        "input": [
            {
                "type": "text",
                "text": "Evaluate this recognized answer using the private context:\n"
                + json.dumps(
                    request_context,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        ],
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": LanguageEvaluation.model_json_schema(),
        },
        "store": False,
        "generation_config": {
            "thinking_level": Config.SPEAKING_COACH_THINKING_LEVEL,
            "max_output_tokens": 1200,
        },
    }

    started = time.monotonic()
    try:
        response = requests.post(
            GEMINI_INTERACTIONS_URL,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=request_payload,
            timeout=Config.SPEAKING_COACH_EVALUATION_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise EvaluatorError("gemini_timeout", "Gemini evaluation timed out.") from exc
    except requests.RequestException as exc:
        raise EvaluatorError(
            "gemini_unavailable", "Gemini evaluation request failed."
        ) from exc
    latency_ms = round((time.monotonic() - started) * 1000)

    try:
        payload = response.json()
    except ValueError as exc:
        raise EvaluatorError(
            "gemini_invalid_response", "Gemini returned a non-JSON response."
        ) from exc
    if not response.ok:
        raise EvaluatorError(
            f"gemini_http_{response.status_code}",
            f"Gemini rejected the request with status {response.status_code}.",
        )
    if not isinstance(payload, dict):
        raise EvaluatorError(
            "gemini_invalid_response", "Gemini returned an invalid response object."
        )

    output_text = _extract_output_text(payload)
    try:
        evaluation = LanguageEvaluation.model_validate_json(output_text)
    except (ValidationError, ValueError) as exc:
        raise EvaluatorError(
            "gemini_schema_invalid", "Gemini output failed evaluator validation."
        ) from exc
    usage = payload.get("usage") or payload.get("usage_metadata") or {}
    return GeminiLanguageResult(
        evaluation=evaluation,
        model=model,
        latency_ms=latency_ms,
        usage=usage if isinstance(usage, dict) else {},
        provider_metadata=_gemini_metadata(payload),
        provider_output_text=output_text,
    )


def _compose_language_evaluation(
    azure: AzureSpeechResult, language: LanguageEvaluation
) -> SpeakingEvaluation:
    displayed = (language.displayed_issues or language.detected_issues)[
        :MAX_DISPLAYED_ISSUES
    ]
    retry_focus = language.retry_focus[:2]
    if language.material_error and not retry_focus:
        retry_focus = [issue.description_en for issue in displayed]
    return SpeakingEvaluation(
        status=(
            EvaluationStatus.RETRY
            if language.material_error
            else EvaluationStatus.PASS
        ),
        transcript=azure.transcript,
        content=language.content,
        pronunciation=PronunciationEvaluation(intelligible=True),
        detected_issues=language.detected_issues,
        displayed_issues=displayed,
        corrected_answer=language.corrected_answer,
        feedback_en=language.feedback_en,
        feedback_th=language.feedback_th,
        retry_focus=retry_focus,
    )


def evaluate_speaking_attempt(
    *,
    audio_bytes: bytes,
    audio_mime_type: str,
    practice_type: Literal["pronunciation", "open", "translation"],
    focus: str,
    prompt_en: str | None,
    prompt_th: str | None,
    target_answers: list[str],
    examples: list[dict[str, Any]],
    instructional_attempt_number: int,
    previous_evaluation: dict[str, Any] | None = None,
) -> EvaluatorResult:
    context = _evaluation_context(
        practice_type=practice_type,
        focus=focus,
        prompt_en=prompt_en,
        prompt_th=prompt_th,
        target_answers=target_answers,
        examples=examples,
        instructional_attempt_number=instructional_attempt_number,
        previous_evaluation=previous_evaluation,
    )
    try:
        normalized_wav = normalize_speaking_audio(
            audio_bytes,
            audio_mime_type,
            max_duration_seconds=30 if practice_type == "pronunciation" else 60,
        )
    except AudioNormalizationError as exc:
        raise EvaluatorError(exc.code, exc.detail) from exc

    reference_text = None
    if practice_type == "pronunciation":
        reference_text = next(
            (answer.strip() for answer in target_answers if answer.strip()),
            (prompt_en or "").strip(),
        )
        if not reference_text:
            raise EvaluatorError(
                "pronunciation_reference_missing",
                "The pronunciation exercise has no reference text.",
            )
    try:
        azure = assess_with_azure_speech(
            normalized_wav,
            reference_text=reference_text,
        )
    except AzureSpeechError as exc:
        raise EvaluatorError(exc.code, exc.detail) from exc

    azure_usage = {
        "duration_100ns": azure.duration_100ns,
        "request_count": 1,
    }
    azure_metadata = {
        "model": AZURE_SPEECH_MODEL,
        "region": Config.AZURE_SPEECH_REGION,
        "response": azure.raw_payload,
    }
    if practice_type == "pronunciation":
        evaluation = _pronunciation_evaluation(
            azure, reference_text=reference_text or "", focus=focus
        )
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=azure.latency_ms,
            usage={"azure": azure_usage},
            provider_metadata={"azure": azure_metadata},
            provider_output_text=json.dumps(
                azure.raw_payload, ensure_ascii=False, separators=(",", ":")
            ),
            evaluation_context=context,
        )

    if _azure_is_unclear(azure):
        evaluation = _unclear_audio_evaluation(azure.transcript)
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=azure.latency_ms,
            usage={"azure": azure_usage},
            provider_metadata={"azure": azure_metadata},
            provider_output_text=json.dumps(
                azure.raw_payload, ensure_ascii=False, separators=(",", ":")
            ),
            evaluation_context=context,
        )

    gemini = evaluate_language_with_gemini(
        azure=azure,
        evaluation_context=context,
        instructional_attempt_number=instructional_attempt_number,
    )
    evaluation = _compose_language_evaluation(azure, gemini.evaluation)
    return EvaluatorResult(
        evaluation=evaluation,
        provider="microsoft+google",
        model=f"{AZURE_SPEECH_MODEL}+{gemini.model}",
        latency_ms=azure.latency_ms + gemini.latency_ms,
        usage={"azure": azure_usage, "gemini": gemini.usage},
        provider_metadata={
            "azure": azure_metadata,
            "gemini": gemini.provider_metadata,
        },
        provider_output_text=gemini.provider_output_text,
        evaluation_context=context,
    )

"""Provider-independent Azure Speech plus text-only Gemini evaluation."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
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
from app.speaking_coach_thai_patterns import (
    pattern_by_id,
    substitution_pattern,
    thai_pronunciation_catalog,
)


PROMPT_VERSION = "speaking-coach-hybrid-v4"
EVALUATOR_SCHEMA_VERSION = "speaking-evaluation-v1"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MIN_RECOGNITION_CONFIDENCE = 0.35
MAX_DISPLAYED_ISSUES = 2
MAX_OPEN_DISPLAYED_ISSUES = 3
FOCUS_WORD_ACCURACY_THRESHOLD = 70
FOCUS_PHONEME_ACCURACY_THRESHOLD = 45
FOCUS_SYLLABLE_ACCURACY_THRESHOLD = 50
FOCUS_COMPLETENESS_SUPPORT_THRESHOLD = 85
SEVERE_WORD_ACCURACY_THRESHOLD = 45
SEVERE_PHONEME_ACCURACY_THRESHOLD = 15
LOW_COMPLETENESS_THRESHOLD = 70
SEVERE_CANDIDATE_PRIORITY = 70
UNSCRIPTED_TRANSFER_PHONEME_THRESHOLD = 45
UNSCRIPTED_SEVERE_PHONEME_THRESHOLD = 30
UNSCRIPTED_SEVERE_WORD_SUPPORT_THRESHOLD = 65
UNSCRIPTED_MIN_EVIDENCE_SCORE = 55
FOCUS_TEXT_VALIDATION_CONFIDENCE = 0.55
IPA_VOWELS = {
    "a",
    "æ",
    "ɑ",
    "ɒ",
    "ʌ",
    "ə",
    "ɛ",
    "ɜ",
    "ɪ",
    "i",
    "ɔ",
    "ʊ",
    "u",
    "eɪ",
    "aɪ",
    "ɔɪ",
    "aʊ",
    "oʊ",
}
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


def _unclear_audio_evaluation(_transcript: str | None = None) -> SpeakingEvaluation:
    return SpeakingEvaluation(
        status=EvaluationStatus.UNCLEAR_AUDIO,
        transcript=None,
        content=ContentEvaluation(),
        pronunciation=PronunciationEvaluation(intelligible=None),
        feedback_en=(
            "I couldn't confidently understand that. Please record it once more."
        ),
        feedback_th="ยังไม่สามารถเข้าใจได้อย่างมั่นใจ กรุณาลองอัดเสียงอีกครั้ง",
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
    pattern_id: str | None = None
    evidence_score: int = 0
    priority_score: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)


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


def _leading_spoken_phoneme(item: dict[str, Any]) -> str | None:
    candidates = item.get("NBestPhonemes")
    nested = item.get("PronunciationAssessment")
    if not isinstance(candidates, list) and isinstance(nested, dict):
        candidates = nested.get("NBestPhonemes")
    if not isinstance(candidates, list) or not candidates:
        return None
    leading = candidates[0]
    if not isinstance(leading, dict):
        return None
    phoneme = leading.get("Phoneme")
    return phoneme.strip() if isinstance(phoneme, str) and phoneme.strip() else None


def _phoneme_evidence_score(
    *,
    expected_accuracy: float,
    word_accuracy: float | None,
    candidate_mismatch: bool,
    error_type: str,
) -> int:
    score = (100 - expected_accuracy) * 0.55
    if candidate_mismatch:
        score += 20
    if word_accuracy is not None:
        score += min(15, max(0, 100 - word_accuracy) * 0.3)
    if error_type.lower() == "mispronunciation":
        score += 10
    return round(min(100, max(0, score)))


def _priority_score(
    evidence_score: int, *, focus_match: bool, pattern_weight: int
) -> int:
    return min(100, evidence_score + pattern_weight + (10 if focus_match else 0))


def _display_phoneme(phoneme: str) -> str:
    return "r" if phoneme == "ɹ" else phoneme


def _focus_mentions_phoneme(focus: str, *phonemes: str) -> bool:
    normalized = _normalized_match_text(focus)
    labels = {_display_phoneme(phoneme).lower() for phoneme in phonemes}
    return any(
        marker in normalized
        for label in labels
        for marker in (f"/{label}/", f"'{label}'", f'"{label}"')
    )


def _english_context_text(evaluation_context: dict[str, Any]) -> str:
    parts = [
        str(evaluation_context.get("prompt_en") or ""),
        str(evaluation_context.get("focus") or ""),
    ]
    parts.extend(
        str(answer)
        for answer in evaluation_context.get("target_answers") or []
        if isinstance(answer, str)
    )
    for example in evaluation_context.get("examples") or []:
        if isinstance(example, dict) and isinstance(example.get("en"), str):
            parts.append(example["en"])
    return " ".join(parts)


def _st_cluster_target(evaluation_context: dict[str, Any]) -> str | None:
    words = re.findall(r"\b[a-z]+\b", _english_context_text(evaluation_context).lower())
    return next((word for word in words if word.startswith("st")), None)


def _cluster_epenthesis_candidate(
    azure: AzureSpeechResult,
    *,
    focus: str,
    evaluation_context: dict[str, Any],
) -> _PronunciationCandidate | None:
    assessment = azure.pronunciation
    target_word = _st_cluster_target(evaluation_context)
    if not assessment or not target_word:
        return None
    stream: list[tuple[int, str]] = []
    for word_index, word in enumerate(assessment.words):
        for phoneme in word.phonemes:
            spoken = _leading_spoken_phoneme(phoneme)
            expected = phoneme.get("Phoneme")
            sound = spoken or (expected if isinstance(expected, str) else None)
            if sound:
                stream.append((word_index, sound.strip().lower()))
    for index in range(len(stream) - 2):
        first, inserted, final = stream[index : index + 3]
        if first[1] != "s" or inserted[1] not in IPA_VOWELS or final[1] != "t":
            continue
        pattern = pattern_by_id("cluster_epenthesis")
        if not pattern:
            return None
        focus_match = _focus_matches_word(
            target_word, focus
        ) or "consonant cluster" in _normalized_match_text(focus)
        evidence_score = 90
        priority_score = _priority_score(
            evidence_score,
            focus_match=focus_match,
            pattern_weight=pattern.priority_weight,
        )
        return _PronunciationCandidate(
            word_index=first[0],
            focus_match=focus_match,
            severity=priority_score,
            status=AssessmentTokenStatus.NEEDS_WORK,
            pattern_id=pattern.id,
            evidence_score=evidence_score,
            priority_score=priority_score,
            evidence={
                "target_word": target_word,
                "expected_cluster": ["s", "t"],
                "spoken_sequence": [first[1], inserted[1], final[1]],
                "context_aligned": True,
            },
            issue=EvaluationIssue(
                category=(
                    IssueCategory.FOCUS
                    if focus_match
                    else IssueCategory.PRONUNCIATION
                ),
                description_en=(
                    f"Say '{target_word}' again smoothly without adding "
                    "an extra sound."
                ),
                description_th=(
                    f"ลองพูดคำว่า '{target_word}' อีกครั้งให้ต่อเนื่อง "
                    "โดยไม่เพิ่มเสียงแทรก"
                ),
            ),
        )
    return None


def _unscripted_pronunciation_candidates(
    azure: AzureSpeechResult,
    *,
    focus: str,
    evaluation_context: dict[str, Any],
) -> list[_PronunciationCandidate]:
    assessment = azure.pronunciation
    if not assessment:
        return []
    candidates: list[_PronunciationCandidate] = []
    for word_index, word in enumerate(assessment.words):
        for phoneme in word.phonemes:
            expected = phoneme.get("Phoneme")
            score = _nested_accuracy_score(phoneme)
            if (
                not isinstance(expected, str)
                or not expected.strip()
                or score is None
            ):
                continue
            expected = expected.strip().lower()
            spoken = _leading_spoken_phoneme(phoneme)
            if not spoken:
                continue
            spoken = spoken.lower()
            final_phoneme = bool(
                word.phonemes and word.phonemes[-1] is phoneme
            )
            matched_pattern = substitution_pattern(expected, spoken)
            if (
                matched_pattern
                and matched_pattern.contexts == ["word_final"]
                and not final_phoneme
            ):
                matched_pattern = None
            is_known_transfer = (
                score <= UNSCRIPTED_TRANSFER_PHONEME_THRESHOLD
                and matched_pattern is not None
            )
            is_severe_mismatch = (
                score <= UNSCRIPTED_SEVERE_PHONEME_THRESHOLD
                and spoken != expected
                and (
                    word.error_type.lower() == "mispronunciation"
                    or (
                        word.accuracy_score is not None
                        and word.accuracy_score
                        <= UNSCRIPTED_SEVERE_WORD_SUPPORT_THRESHOLD
                    )
                )
            )
            if not is_known_transfer and not is_severe_mismatch:
                continue
            evidence_score = _phoneme_evidence_score(
                expected_accuracy=score,
                word_accuracy=word.accuracy_score,
                candidate_mismatch=spoken != expected,
                error_type=word.error_type,
            )
            if evidence_score < UNSCRIPTED_MIN_EVIDENCE_SCORE:
                continue
            focus_match = _focus_matches_word(
                word.word, focus
            ) or _focus_mentions_phoneme(focus, expected, spoken)
            catalog_pattern = matched_pattern
            if not catalog_pattern and final_phoneme:
                final_pattern = pattern_by_id("final_consonant_weakening")
                if final_pattern and expected in final_pattern.expected_phonemes:
                    catalog_pattern = final_pattern
            if not catalog_pattern:
                inventory_pattern = pattern_by_id("non_native_consonant_mapping")
                if (
                    inventory_pattern
                    and expected in inventory_pattern.expected_phonemes
                ):
                    catalog_pattern = inventory_pattern
            pattern_weight = catalog_pattern.priority_weight if catalog_pattern else 0
            priority_score = _priority_score(
                evidence_score,
                focus_match=focus_match,
                pattern_weight=pattern_weight,
            )
            if final_phoneme:
                description_en = f"Say '{word.word}' again, focusing on the ending."
                description_th = f"ลองพูดคำว่า '{word.word}' อีกครั้ง โดยเน้นเสียงท้ายคำ"
            else:
                description_en = f"Say '{word.word}' again clearly."
                description_th = f"ลองพูดคำว่า '{word.word}' อีกครั้งให้ชัดเจน"
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=priority_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id=(catalog_pattern.id if catalog_pattern else None),
                    evidence_score=evidence_score,
                    priority_score=priority_score,
                    evidence={
                        "word": word.word,
                        "expected_phoneme": expected,
                        "leading_spoken_phoneme": spoken,
                        "expected_accuracy": score,
                        "word_accuracy": word.accuracy_score,
                        "error_type": word.error_type,
                    },
                    issue=EvaluationIssue(
                        category=(
                            IssueCategory.FOCUS
                            if focus_match
                            else IssueCategory.PRONUNCIATION
                        ),
                        description_en=description_en,
                        description_th=description_th,
                    ),
                )
            )
    cluster_candidate = _cluster_epenthesis_candidate(
        azure,
        focus=focus,
        evaluation_context=evaluation_context,
    )
    if cluster_candidate:
        candidates.append(cluster_candidate)
    return _select_display_candidates(candidates)[:2]


def _pronunciation_policy_metadata(
    candidates: list[_PronunciationCandidate],
    *,
    focus_issues: list[EvaluationIssue],
    prosody_score: float | None = None,
) -> dict[str, Any]:
    catalog = thai_pronunciation_catalog()
    return {
        "catalog_version": catalog.catalog_version,
        "learner_feedback_policy": catalog.learner_feedback_policy,
        "matches": [
            {
                "pattern_id": candidate.pattern_id,
                "evidence_score": candidate.evidence_score,
                "priority_score": candidate.priority_score,
                "focus_match": candidate.focus_match,
                "evidence": candidate.evidence,
            }
            for candidate in candidates
        ],
        "focus_validation_issue_count": len(focus_issues),
        "prosody": {
            "enabled": True,
            "score": prosody_score,
            "learner_feedback_enabled": False,
        },
    }


def _uses_present_continuous(transcript: str) -> bool:
    normalized = _normalized_match_text(transcript)
    be = r"(?:am|is|are|i'm|you're|we're|they're|he's|she's|it's)"
    return bool(re.search(rf"\b{be}\s+[a-z]+ing\b", normalized))


def _focus_validation_issues(
    azure: AzureSpeechResult, *, focus: str
) -> list[EvaluationIssue]:
    normalized_focus = _normalized_match_text(focus)
    if "present continuous" not in normalized_focus:
        return []
    if (
        azure.confidence is None
        or azure.confidence < FOCUS_TEXT_VALIDATION_CONFIDENCE
        or not azure.transcript
        or _uses_present_continuous(azure.transcript)
    ):
        return []
    return [
        EvaluationIssue(
            category=IssueCategory.FOCUS,
            description_en=(
                "Use am/is/are plus a verb ending in -ing "
                "(for example, 'I'm studying ...')."
            ),
            description_th=(
                "ใช้ am/is/are ตามด้วยคำกริยาที่ลงท้ายด้วย -ing "
                "เช่น 'I'm studying ...'"
            ),
        )
    ]


def _unscripted_pronunciation_retry(
    azure: AzureSpeechResult, candidates: list[_PronunciationCandidate]
) -> SpeakingEvaluation:
    issues = [candidate.issue for candidate in candidates[:1]]
    issue = issues[0]
    return SpeakingEvaluation(
        status=EvaluationStatus.RETRY,
        transcript=None,
        content=ContentEvaluation(),
        pronunciation=PronunciationEvaluation(intelligible=None, issues=issues),
        detected_issues=issues,
        displayed_issues=issues,
        feedback_en=issue.description_en,
        feedback_th=issue.description_th,
        retry_focus=[issue.description_en],
    )


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
    if phoneme and final_phoneme:
        return EvaluationIssue(
            category=category,
            description_en=f"Say '{word}' again, focusing on the ending.",
            description_th=f"ลองพูดคำว่า '{word}' อีกครั้ง โดยเน้นเสียงท้ายคำ",
        )
    return EvaluationIssue(
        category=category,
        description_en=f"Say '{word}' again clearly.",
        description_th=f"ลองพูดคำว่า '{word}' อีกครั้งให้ชัดเจน",
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
    azure: AzureSpeechResult,
    language: LanguageEvaluation,
    pronunciation_candidates: list[_PronunciationCandidate] | None = None,
    focus_issues: list[EvaluationIssue] | None = None,
    include_transcript: bool = True,
) -> SpeakingEvaluation:
    pronunciation_issues = [
        candidate.issue for candidate in (pronunciation_candidates or [])[:2]
    ]
    deterministic_focus_issues = (focus_issues or [])[:1]
    language_displayed = language.displayed_issues or language.detected_issues
    displayed = _dedupe_language_issues(
        deterministic_focus_issues + language_displayed + pronunciation_issues
    )[:MAX_OPEN_DISPLAYED_ISSUES]
    detected = _dedupe_language_issues(
        deterministic_focus_issues
        + language.detected_issues
        + pronunciation_issues
    )[:12]
    has_material_issue = (
        language.material_error
        or bool(deterministic_focus_issues)
        or bool(pronunciation_issues)
    )
    retry_focus: list[str] = []
    retry_concepts: set[str] = set()
    retry_candidates = [
        issue.description_en for issue in deterministic_focus_issues
    ] + language.retry_focus[:2] + [
        issue.description_en for issue in pronunciation_issues
    ]
    for retry_candidate in retry_candidates:
        concept = _language_text_concept(retry_candidate)
        if concept in retry_concepts:
            continue
        retry_concepts.add(concept)
        retry_focus.append(retry_candidate)
        if len(retry_focus) >= 3:
            break
    if has_material_issue and not retry_focus:
        retry_focus = [issue.description_en for issue in displayed]
    if deterministic_focus_issues and pronunciation_issues:
        feedback_en = "Fix the target structure and these pronunciation points."
        feedback_th = "แก้โครงสร้างเป้าหมายและจุดออกเสียงเหล่านี้"
    elif deterministic_focus_issues and not language.material_error:
        feedback_en = deterministic_focus_issues[0].description_en
        feedback_th = deterministic_focus_issues[0].description_th
    elif pronunciation_issues and not language.material_error:
        feedback_en = pronunciation_issues[0].description_en
        feedback_th = pronunciation_issues[0].description_th
    elif pronunciation_issues and language.material_error:
        feedback_en = "Focus on these two parts, then try once more."
        feedback_th = "เน้นสองจุดนี้ แล้วลองพูดอีกครั้ง"
    else:
        feedback_en = language.feedback_en
        feedback_th = language.feedback_th
    return SpeakingEvaluation(
        status=(
            EvaluationStatus.RETRY
            if has_material_issue
            else EvaluationStatus.PASS
        ),
        transcript=azure.transcript if include_transcript else None,
        content=ContentEvaluation(
            meaning_correct=language.content.meaning_correct,
            relevant=language.content.relevant,
            target_usage_correct=(
                False
                if deterministic_focus_issues
                else language.content.target_usage_correct
            ),
            grammar_correct=(
                False
                if deterministic_focus_issues
                else language.content.grammar_correct
            ),
        ),
        pronunciation=PronunciationEvaluation(
            intelligible=True,
            issues=pronunciation_issues,
        ),
        detected_issues=detected,
        displayed_issues=displayed,
        corrected_answer=language.corrected_answer,
        feedback_en=feedback_en,
        feedback_th=feedback_th,
        retry_focus=retry_focus,
    )


def _language_text_concept(value: str) -> str:
    text = re.sub(r"\s+", " ", value.lower()).strip()
    present_continuous_markers = (
        "present continuous",
        "am/is/are",
        "be + -ing",
        "be + ing",
        "after 'is'",
        'after "is"',
    )
    if any(marker in text for marker in present_continuous_markers):
        return "language:present_continuous_structure"
    normalized = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return normalized


def _language_issue_concept(issue: EvaluationIssue) -> str:
    concept = _language_text_concept(issue.description_en)
    if (
        concept == "language:present_continuous_structure"
        and issue.category in {IssueCategory.FOCUS, IssueCategory.GRAMMAR}
    ):
        return concept
    return f"{issue.category.value}:{concept}"


def _dedupe_language_issues(
    issues: list[EvaluationIssue],
) -> list[EvaluationIssue]:
    deduplicated: list[EvaluationIssue] = []
    seen: set[str] = set()
    for issue in issues:
        concept = _language_issue_concept(issue)
        if concept in seen:
            continue
        seen.add(concept)
        deduplicated.append(issue)
    return deduplicated


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
            enable_unscripted_assessment=practice_type == "open",
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

    pronunciation_candidates = (
        _unscripted_pronunciation_candidates(
            azure,
            focus=focus,
            evaluation_context=context,
        )
        if practice_type == "open"
        else []
    )
    focus_issues = (
        _focus_validation_issues(azure, focus=focus)
        if practice_type == "open"
        else []
    )
    policy_metadata = (
        _pronunciation_policy_metadata(
            pronunciation_candidates,
            focus_issues=focus_issues,
            prosody_score=(
                azure.pronunciation.prosody_score
                if azure.pronunciation
                else None
            ),
        )
        if practice_type == "open"
        else None
    )
    if _azure_is_unclear(azure):
        evaluation = (
            _unscripted_pronunciation_retry(azure, pronunciation_candidates)
            if pronunciation_candidates
            else _unclear_audio_evaluation(azure.transcript)
        )
        if practice_type == "open":
            evaluation = evaluation.model_copy(update={"transcript": None})
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=azure.latency_ms,
            usage={"azure": azure_usage},
            provider_metadata={
                "azure": azure_metadata,
                **({"policy": policy_metadata} if policy_metadata else {}),
            },
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
    evaluation = _compose_language_evaluation(
        azure,
        gemini.evaluation,
        pronunciation_candidates=pronunciation_candidates,
        focus_issues=focus_issues,
        include_transcript=practice_type != "open",
    )
    return EvaluatorResult(
        evaluation=evaluation,
        provider="microsoft+google",
        model=f"{AZURE_SPEECH_MODEL}+{gemini.model}",
        latency_ms=azure.latency_ms + gemini.latency_ms,
        usage={"azure": azure_usage, "gemini": gemini.usage},
        provider_metadata={
            "azure": azure_metadata,
            "gemini": gemini.provider_metadata,
            **({"policy": policy_metadata} if policy_metadata else {}),
        },
        provider_output_text=gemini.provider_output_text,
        evaluation_context=context,
    )

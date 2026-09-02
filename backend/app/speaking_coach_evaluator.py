"""Provider-independent Azure Speech plus text-only Gemini evaluation."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
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
from app.speaking_coach_target_alignment import (
    ExpectedPhoneme,
    ObservedPhoneme,
    PhonemeCandidate,
    TargetAlignmentResult,
    align_phonemes_to_target,
)


PROMPT_VERSION = "speaking-coach-hybrid-v10"
EVALUATOR_SCHEMA_VERSION = "speaking-evaluation-v1"
GEMINI_INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
MIN_RECOGNITION_CONFIDENCE = 0.35
MAX_DISPLAYED_ISSUES = 2
MAX_OPEN_DISPLAYED_ISSUES = 2
FOCUS_WORD_ACCURACY_THRESHOLD = 70
FOCUS_PHONEME_ACCURACY_THRESHOLD = 45
FOCUS_SYLLABLE_ACCURACY_THRESHOLD = 50
FOCUS_COMPLETENESS_SUPPORT_THRESHOLD = 85
SEVERE_WORD_ACCURACY_THRESHOLD = 45
SEVERE_PHONEME_ACCURACY_THRESHOLD = 15
LOW_COMPLETENESS_THRESHOLD = 70
UNSCRIPTED_TRANSFER_PHONEME_THRESHOLD = 45
UNSCRIPTED_SEVERE_PHONEME_THRESHOLD = 30
UNSCRIPTED_SEVERE_WORD_SUPPORT_THRESHOLD = 65
UNSCRIPTED_MIN_EVIDENCE_SCORE = 55
FOCUS_TEXT_VALIDATION_CONFIDENCE = 0.55
COACHING_IMPROVEMENT_EVIDENCE_DELTA = 5
CLUSTER_SECOND_CONSONANT_THRESHOLD = 45
CLUSTER_STRONG_VOWEL_CONSONANT_THRESHOLD = 60
CLUSTER_SECONDARY_VOWEL_SCORE_THRESHOLD = 50
CLUSTER_STRONG_SECONDARY_VOWEL_SCORE_THRESHOLD = 80
CLUSTER_ULTRA_STRONG_SECONDARY_VOWEL_SCORE_THRESHOLD = 90
CLUSTER_ULTRA_STRONG_SECONDARY_VOWEL_MAX_GAP = 10
CLUSTER_WORD_SUPPORT_THRESHOLD = 75
CLUSTER_SYLLABLE_SUPPORT_THRESHOLD = 65
CLUSTER_SEGMENT_DURATION_SUPPORT_100NS = 1_500_000
CLUSTER_ULTRA_STRONG_SEGMENT_DURATION_100NS = 2_000_000
CLUSTER_CONTEXT_MIN_INSERTED_VOWEL_DURATION_100NS = 800_000
RHOTIC_VOWEL_ACCURACY_THRESHOLD = 50
RHOTIC_VOWEL_MIN_EVIDENCE_SCORE = 68
RHOTIC_FINAL_MISMATCH_MIN_CANDIDATE_SCORE = 90
FINAL_CONSONANT_STRONG_MISMATCH_ACCURACY_THRESHOLD = 15
FINAL_CONSONANT_STRONG_MISMATCH_CANDIDATE_SCORE = 90
LOCAL_PHONEME_MISMATCH_CANDIDATE_SCORE = 90
LOCAL_PHONEME_MISMATCH_MIN_SCORE_MARGIN = 30
PROSODY_MIN_WORDS = 5
PROSODY_BREAK_CONFIDENCE_THRESHOLD = 0.75
SHORT_P1_GATE_MAX_WORDS = 3
SHORT_P1_GATE_UNRELATED_SIMILARITY = 0.45
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
CENTRAL_EPENTHETIC_VOWELS = {"ə", "ʌ", "ɜ", "ɐ"}
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
        return self


class LanguageEvaluationIssue(EvaluationIssue):
    """Text-model finding with an optional link to the authored focus rubric."""

    focus_item_index: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Zero-based index of the supporting evaluation_context.focus_items entry; "
            "null for a non-authored fallback finding."
        ),
    )

    def public_issue(self) -> EvaluationIssue:
        return EvaluationIssue(
            category=self.category,
            description_en=self.description_en,
            description_th=self.description_th,
        )


class LanguageEvaluation(BaseModel):
    """Gemini's language-only result; the backend owns final status."""

    model_config = ConfigDict(extra="forbid")

    material_error: bool
    content: ContentEvaluation
    detected_issues: list[LanguageEvaluationIssue] = Field(
        default_factory=list, max_length=12
    )
    displayed_issues: list[LanguageEvaluationIssue] = Field(
        default_factory=list, max_length=3
    )
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
The private context may contain ordered focus_items with priority 1, 2, or 3.
After an issue is supported by transcript evidence, prefer P1 over P2 over P3 and
preserve source order between supported items with the same priority.
For every detected or displayed issue supported by an authored focus item, set
focus_item_index to that item's zero-based position in focus_items. Set it to null
for an independently supported fallback finding. The backend validates the index
and derives priority from the authoritative focus_items; do not encode priority in
the issue text.
Treat issue category only as a description of the finding; it must never reorder
eligible authored findings. Put independently supported non-FOCUS findings only
after all supported authored findings.
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
    focus_items: list[dict[str, Any]] | None = None,
    prompt_en: str | None,
    prompt_th: str | None,
    target_answers: list[str],
    examples: list[dict[str, Any]],
    instructional_attempt_number: int,
    previous_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    public_previous_evaluation = (
        {
            key: value
            for key, value in previous_evaluation.items()
            if not key.startswith("_")
        }
        if isinstance(previous_evaluation, dict)
        else previous_evaluation
    )
    return {
        "practice_type": practice_type,
        "focus": focus,
        "focus_items": _normalized_focus_items(focus_items, focus=focus),
        "prompt_en": prompt_en,
        "prompt_th": prompt_th,
        "target_answers": target_answers,
        "examples": examples,
        "instructional_attempt_number": instructional_attempt_number,
        "previous_evaluation": public_previous_evaluation,
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
    focus_priority: int | None = None
    focus_order: int | None = None
    pattern_id: str | None = None
    evidence_score: int = 0
    priority_score: int = 0
    evidence: dict[str, Any] = field(default_factory=dict)
    blocking: bool = False


@dataclass(frozen=True)
class _P1FocusTarget:
    word: str
    word_index: int
    expected_segment: str
    position: Literal["initial", "medial", "final", "any"]
    instruction: str
    focus_order: int


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


def _focus_is_pronunciation_specific(focus: str) -> bool:
    normalized = _normalized_match_text(focus)
    return any(
        marker in normalized
        for marker in (
            "pronounc",
            "say ",
            "sound",
            "clearly",
            "clear ",
            "consonant",
            "vowel",
            "diphthong",
            "cluster",
            "syllable",
            "articulat",
            "audible",
            "omitted",
            "dropped",
            "replaced",
            "clipped",
            "ending",
            "stress",
            "intonation",
            "rhythm",
            "linking",
            "fluency",
            "accent",
        )
    )


def _pronunciation_focus_matches_word(word: str, focus: str) -> bool:
    return _focus_is_pronunciation_specific(focus) and _focus_matches_word(
        word, focus
    )


def _normalized_focus_items(
    focus_items: list[dict[str, Any]] | None,
    *,
    focus: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in focus_items or []:
        if not isinstance(item, dict):
            continue
        priority = item.get("priority")
        instruction = item.get("instruction")
        if (
            isinstance(priority, int)
            and not isinstance(priority, bool)
            and priority in {1, 2, 3}
            and isinstance(instruction, str)
            and instruction.strip()
        ):
            normalized.append(
                {
                    "priority": priority,
                    "instruction": instruction.strip(),
                }
            )
    if normalized:
        return normalized
    return (
        [{"priority": 1, "instruction": focus.strip()}]
        if focus.strip()
        else []
    )


_CONTRACTION_EXPANSIONS = {
    "i'm": ("i", "am"),
    "isn't": ("is", "not"),
    "they're": ("they", "are"),
    "we're": ("we", "are"),
    "you're": ("you", "are"),
}


def _spoken_words(value: str) -> list[str]:
    return [
        _normalized_match_text(word)
        for word in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*", value)
    ]


def _expanded_alignment_units(words: list[str]) -> list[tuple[str, int]]:
    units: list[tuple[str, int]] = []
    for word_index, word in enumerate(words):
        expansion = _CONTRACTION_EXPANSIONS.get(word, (word,))
        units.extend((unit, word_index) for unit in expansion)
    return units


def _focus_segment_position(
    instruction: str, marker_start: int
) -> Literal["initial", "medial", "final", "any"]:
    nearby = _normalized_match_text(
        instruction[max(0, marker_start - 45):marker_start]
    )
    if re.search(r"\b(final|ending|end)\b", nearby):
        return "final"
    if re.search(r"\b(initial|beginning|start)\b", nearby):
        return "initial"
    if re.search(r"\b(medial|middle)\b", nearby):
        return "medial"
    return "any"


def _short_p1_focus_targets(
    reference_text: str,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None,
) -> list[_P1FocusTarget]:
    reference_words = _spoken_words(reference_text)
    if not reference_words or len(reference_words) > SHORT_P1_GATE_MAX_WORDS:
        return []

    targets: list[_P1FocusTarget] = []
    seen: set[tuple[int, str, str]] = set()
    for focus_order, item in enumerate(
        _normalized_focus_items(focus_items, focus=focus)
    ):
        if item["priority"] != 1:
            continue
        instruction = item["instruction"]
        if not _focus_is_pronunciation_specific(instruction):
            continue
        matching_word_indexes = [
            index
            for index, word in enumerate(reference_words)
            if _focus_matches_word(word, instruction)
        ]
        if len(matching_word_indexes) != 1:
            continue
        word_index = matching_word_indexes[0]
        for marker in re.finditer(r"/([^/\n]{1,20})/", instruction):
            expected_segment = marker.group(1).strip().lower()
            if not expected_segment:
                continue
            position = _focus_segment_position(instruction, marker.start())
            key = (word_index, expected_segment, position)
            if key in seen:
                continue
            seen.add(key)
            targets.append(
                _P1FocusTarget(
                    word=reference_words[word_index],
                    word_index=word_index,
                    expected_segment=expected_segment,
                    position=position,
                    instruction=instruction,
                    focus_order=focus_order,
                )
            )
    return targets


def _word_alignment(
    target_units: list[tuple[str, int]],
    hypothesis_units: list[tuple[str, int]],
) -> dict[int, int | None]:
    target_count = len(target_units)
    hypothesis_count = len(hypothesis_units)
    costs = [
        [float("inf") for _ in range(hypothesis_count + 1)]
        for _ in range(target_count + 1)
    ]
    steps: list[list[tuple[int, int, str] | None]] = [
        [None for _ in range(hypothesis_count + 1)]
        for _ in range(target_count + 1)
    ]
    costs[0][0] = 0
    for target_index in range(1, target_count + 1):
        costs[target_index][0] = target_index * 0.8
        steps[target_index][0] = (target_index - 1, 0, "delete")
    for hypothesis_index in range(1, hypothesis_count + 1):
        costs[0][hypothesis_index] = hypothesis_index * 0.8
        steps[0][hypothesis_index] = (0, hypothesis_index - 1, "insert")

    for target_index in range(1, target_count + 1):
        for hypothesis_index in range(1, hypothesis_count + 1):
            target_word = target_units[target_index - 1][0]
            hypothesis_word = hypothesis_units[hypothesis_index - 1][0]
            substitution_cost = 1 - SequenceMatcher(
                None, target_word, hypothesis_word
            ).ratio()
            options = (
                (
                    costs[target_index - 1][hypothesis_index - 1]
                    + substitution_cost,
                    (target_index - 1, hypothesis_index - 1, "match"),
                ),
                (
                    costs[target_index - 1][hypothesis_index] + 0.8,
                    (target_index - 1, hypothesis_index, "delete"),
                ),
                (
                    costs[target_index][hypothesis_index - 1] + 0.8,
                    (target_index, hypothesis_index - 1, "insert"),
                ),
            )
            costs[target_index][hypothesis_index], steps[target_index][
                hypothesis_index
            ] = min(options, key=lambda option: option[0])

    mapping: dict[int, int | None] = {
        target_index: None for target_index in range(target_count)
    }
    target_index = target_count
    hypothesis_index = hypothesis_count
    while target_index or hypothesis_index:
        step = steps[target_index][hypothesis_index]
        if step is None:
            break
        previous_target, previous_hypothesis, operation = step
        if operation == "match":
            mapping[target_index - 1] = hypothesis_index - 1
        target_index, hypothesis_index = previous_target, previous_hypothesis
    return mapping


def _normalized_ipa(value: str) -> str:
    return (
        re.sub(r"[\s.ˈˌ-]+", "", value.lower())
        .replace("r", "ɹ")
        .replace("ɻ", "ɹ")
        .replace("ɫ", "l")
    )


def _target_alignment_observed_phonemes(
    azure: AzureSpeechResult,
) -> list[ObservedPhoneme]:
    if not azure.pronunciation:
        return []
    result: list[ObservedPhoneme] = []
    for word_index, word in enumerate(azure.pronunciation.words):
        for phoneme_index, item in enumerate(word.phonemes):
            leading = _leading_spoken_phoneme(item)
            if not leading and isinstance(item.get("Phoneme"), str):
                leading = item["Phoneme"].strip()
            if not leading:
                continue
            candidates = []
            for candidate in _nbest_phonemes(item)[:10]:
                sound = candidate.get("Phoneme")
                score = candidate.get("Score")
                if (
                    isinstance(sound, str)
                    and sound.strip()
                    and not isinstance(score, bool)
                    and isinstance(score, (int, float))
                ):
                    candidates.append(
                        PhonemeCandidate(phoneme=sound.strip(), score=float(score))
                    )
            result.append(
                ObservedPhoneme(
                    phoneme=leading,
                    word=word.word,
                    word_index=word_index,
                    phoneme_index=phoneme_index,
                    duration_100ns=(
                        item.get("Duration")
                        if isinstance(item.get("Duration"), int)
                        and not isinstance(item.get("Duration"), bool)
                        and item.get("Duration") >= 0
                        else None
                    ),
                    candidates=candidates,
                )
            )
    return result


def _target_alignment_expected_phonemes(
    azure: AzureSpeechResult,
) -> list[ExpectedPhoneme]:
    if not azure.pronunciation:
        return []
    result: list[ExpectedPhoneme] = []
    for word_index, word in enumerate(azure.pronunciation.words):
        usable = [
            item
            for item in word.phonemes
            if isinstance(item.get("Phoneme"), str) and item["Phoneme"].strip()
        ]
        for phoneme_index, item in enumerate(usable):
            result.append(
                ExpectedPhoneme(
                    phoneme=item["Phoneme"].strip(),
                    word=word.word,
                    word_index=word_index,
                    phoneme_index=phoneme_index,
                    word_final=phoneme_index == len(usable) - 1,
                )
            )
    return result


def _translation_alignment_reference(target_answers: list[str]) -> str | None:
    """Choose an expanded accepted answer for the first translation aligner."""
    usable = list(
        dict.fromkeys(answer.strip() for answer in target_answers if answer.strip())
    )
    if not usable:
        return None
    return max(
        usable,
        key=lambda answer: (len(_spoken_words(answer)), -len(answer)),
    )


def _target_alignment_candidates(
    alignment: TargetAlignmentResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None,
) -> list[_PronunciationCandidate]:
    candidates: list[_PronunciationCandidate] = []
    for operation in alignment.operations:
        word = operation.expected_word
        if not word or operation.expected_word_index is None:
            continue
        if operation.kind == "cluster_epenthesis":
            inserted_duration = operation.evidence.get(
                "inserted_vowel_duration_100ns"
            )
            if (
                isinstance(inserted_duration, int)
                and inserted_duration
                < CLUSTER_CONTEXT_MIN_INSERTED_VOWEL_DURATION_100NS
            ):
                continue
            focus_rank = _pronunciation_focus_rank(
                word,
                focus=focus,
                focus_items=focus_items,
                general_markers=("consonant cluster",),
            )
            evidence_score = max(55, round((1 - operation.cost) * 100))
            candidates.append(
                _PronunciationCandidate(
                    word_index=operation.expected_word_index,
                    focus_match=focus_rank is not None,
                    severity=evidence_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id="cluster_epenthesis",
                    evidence_score=evidence_score,
                    priority_score=evidence_score,
                    evidence={
                        **operation.evidence,
                        "alignment_operation": operation.model_dump(mode="json"),
                    },
                    issue=EvaluationIssue(
                        category=(
                            IssueCategory.FOCUS
                            if focus_rank is not None
                            else IssueCategory.PRONUNCIATION
                        ),
                        description_en=(
                            f"Say '{word}' smoothly without adding an extra sound "
                            "between the first consonants."
                        ),
                        description_th=(
                            f"พูดคำว่า '{word}' ให้ต่อเนื่อง "
                            "โดยไม่เพิ่มเสียงแทรกระหว่างพยัญชนะต้น"
                        ),
                    ),
                    focus_priority=focus_rank[0] if focus_rank else None,
                    focus_order=focus_rank[1] if focus_rank else None,
                )
            )
        elif (
            operation.kind == "candidate_supported_substitution"
            and operation.expected_word_final
        ):
            expected_sound = operation.expected[0] if operation.expected else ""
            focus_rank = _pronunciation_focus_rank(
                word,
                focus=focus,
                focus_items=focus_items,
                phonemes=(expected_sound,),
                general_markers=("ending", "final consonant"),
            )
            evidence_score = max(55, round((1 - operation.cost) * 100))
            candidates.append(
                _PronunciationCandidate(
                    word_index=operation.expected_word_index,
                    focus_match=focus_rank is not None,
                    severity=evidence_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id=operation.pattern_id,
                    evidence_score=evidence_score,
                    priority_score=evidence_score,
                    evidence={"alignment_operation": operation.model_dump(mode="json")},
                    issue=EvaluationIssue(
                        category=(
                            IssueCategory.FOCUS
                            if focus_rank is not None
                            else IssueCategory.PRONUNCIATION
                        ),
                        description_en=f"Say '{word}' again, focusing on the ending.",
                        description_th=(
                            f"ลองพูดคำว่า '{word}' อีกครั้ง โดยเน้นเสียงท้ายคำ"
                        ),
                    ),
                    focus_priority=focus_rank[0] if focus_rank else None,
                    focus_order=focus_rank[1] if focus_rank else None,
                )
            )
    return candidates


def _unbiased_word_phonemes(word: Any) -> tuple[str, bool]:
    spoken: list[str] = []
    has_nbest = False
    for item in word.phonemes:
        candidates = _nbest_phonemes(item)
        has_nbest = has_nbest or bool(candidates)
        phoneme = _leading_spoken_phoneme(item)
        if not phoneme and isinstance(item.get("Phoneme"), str):
            phoneme = item["Phoneme"].strip()
        if phoneme:
            spoken.append(_normalized_ipa(phoneme))
    return "".join(spoken), has_nbest


def _segment_matches_position(
    spoken: str,
    expected: str,
    position: Literal["initial", "medial", "final", "any"],
) -> bool:
    if expected == "ɹ":
        if position == "initial":
            return spoken.startswith("ɹ")
        if position == "final":
            return spoken.endswith(("ɹ", "ɚ", "ɝ"))
        return _contains_rhotic(spoken)
    if position == "initial":
        return spoken.startswith(expected)
    if position == "final":
        return spoken.endswith(expected)
    return expected in spoken


def _short_p1_gate_policy(
    azure: AzureSpeechResult,
    *,
    reference_text: str,
    targets: list[_P1FocusTarget],
) -> dict[str, Any]:
    target_words = _spoken_words(reference_text)
    hypothesis_words = [
        _normalized_match_text(word.word)
        for word in (azure.pronunciation.words if azure.pronunciation else [])
    ]
    target_units = _expanded_alignment_units(target_words)
    hypothesis_units = _expanded_alignment_units(hypothesis_words)
    target_text = " ".join(unit for unit, _ in target_units)
    hypothesis_text = " ".join(unit for unit, _ in hypothesis_units)
    similarity = SequenceMatcher(None, target_text, hypothesis_text).ratio()
    base = {
        "eligible": True,
        "decision": "ambiguous",
        "reference_word_count": len(target_words),
        "reference_text": reference_text,
        "unbiased_transcript": azure.transcript,
        "unbiased_confidence": azure.confidence,
        "text_similarity": round(similarity, 3),
        "targets": [],
    }
    if _azure_is_unclear(azure) or not azure.pronunciation:
        base["reason"] = "unbiased_recognition_unclear"
        return base
    if similarity < SHORT_P1_GATE_UNRELATED_SIMILARITY:
        base["decision"] = "unrelated"
        base["reason"] = "unbiased_transcript_does_not_resemble_reference"
        return base

    alignment = _word_alignment(target_units, hypothesis_units)
    divergent = False
    ambiguous = False
    for target in targets:
        target_unit_indexes = [
            index
            for index, (_, original_index) in enumerate(target_units)
            if original_index == target.word_index
        ]
        if not target_unit_indexes:
            continue
        target_unit_index = (
            target_unit_indexes[-1]
            if target.position == "final"
            else target_unit_indexes[0]
        )
        hypothesis_unit_index = alignment.get(target_unit_index)
        evidence: dict[str, Any] = {
            "word": target.word,
            "word_index": target.word_index,
            "expected_segment": target.expected_segment,
            "position": target.position,
            "focus_order": target.focus_order,
            "instruction": target.instruction,
        }
        if hypothesis_unit_index is None:
            evidence["result"] = "diverged"
            evidence["reason"] = "focused_word_or_contraction_part_missing"
            divergent = True
            base["targets"].append(evidence)
            continue

        hypothesis_word_index = hypothesis_units[hypothesis_unit_index][1]
        hypothesis_word = azure.pronunciation.words[hypothesis_word_index]
        spoken_phonemes, has_nbest = _unbiased_word_phonemes(hypothesis_word)
        expected_segment = _normalized_ipa(target.expected_segment)
        evidence.update(
            {
                "hypothesis_word": hypothesis_word.word,
                "spoken_phonemes": spoken_phonemes,
                "has_nbest_phonemes": has_nbest,
            }
        )
        if not spoken_phonemes:
            evidence["result"] = "ambiguous"
            evidence["reason"] = "unbiased_phonemes_missing"
            ambiguous = True
        elif _segment_matches_position(
            spoken_phonemes, expected_segment, target.position
        ):
            evidence["result"] = "plausible"
        else:
            target_unit = target_units[target_unit_index][0]
            hypothesis_unit = hypothesis_units[hypothesis_unit_index][0]
            if has_nbest or target_unit != hypothesis_unit:
                evidence["result"] = "diverged"
                evidence["reason"] = "focused_segment_missing_or_substituted"
                divergent = True
            else:
                evidence["result"] = "ambiguous"
                evidence["reason"] = "focused_segment_not_corroborated"
                ambiguous = True
        base["targets"].append(evidence)

    if divergent:
        base["decision"] = "diverged"
    elif ambiguous or not base["targets"]:
        base["decision"] = "ambiguous"
    else:
        base["decision"] = "plausible"
    return base


def _pronunciation_focus_rank(
    word: str,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None,
    phonemes: tuple[str, ...] = (),
    general_markers: tuple[str, ...] = (),
) -> tuple[int, int] | None:
    matches: list[tuple[int, int]] = []
    for index, item in enumerate(
        _normalized_focus_items(focus_items, focus=focus)
    ):
        instruction = item["instruction"]
        normalized_instruction = _normalized_match_text(instruction)
        if not _focus_is_pronunciation_specific(instruction):
            continue
        if (
            _focus_matches_word(word, instruction)
            or (
                phonemes
                and _focus_mentions_phoneme(instruction, *phonemes)
            )
            or any(marker in normalized_instruction for marker in general_markers)
        ):
            matches.append((item["priority"], index))
    return min(matches) if matches else None


def _local_mismatch_focus_rank(
    word: str,
    *,
    expected_phoneme: str,
    observed_phoneme: str,
    phoneme_index: int,
    word_final: bool,
    focus: str,
    focus_items: list[dict[str, Any]] | None,
) -> tuple[int, int] | None:
    """Match a local phoneme mismatch to the authored rubric precisely enough to grade."""
    matches: list[tuple[int, int]] = []
    for index, item in enumerate(_normalized_focus_items(focus_items, focus=focus)):
        instruction = item["instruction"]
        normalized = _normalized_match_text(instruction)
        mentioned_phonemes = re.findall(r"/([^/]+)/", normalized)
        if not _focus_is_pronunciation_specific(instruction) and not mentioned_phonemes:
            continue
        final_specific = any(
            marker in normalized
            for marker in ("word-final", "word final", "final consonant", "ending")
        )
        initial_specific = any(
            marker in normalized
            for marker in ("word-initial", "word initial", "initial consonant", "beginning")
        )
        if final_specific and not word_final:
            continue
        if initial_specific and phoneme_index != 0:
            continue

        word_match = _focus_matches_word(word, instruction)
        phoneme_match = _focus_mentions_phoneme(
            instruction, expected_phoneme, observed_phoneme
        )
        if word_match and mentioned_phonemes and not phoneme_match:
            continue
        if word_match or phoneme_match:
            matches.append((item["priority"], index))
    return min(matches) if matches else None


def _candidate_sort_key(
    candidate: _PronunciationCandidate,
) -> tuple[int, int, int, int]:
    return (
        1 if candidate.focus_match else 0,
        -(candidate.focus_priority or 4),
        -(candidate.focus_order if candidate.focus_order is not None else 10_000),
        candidate.severity,
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


def _leading_spoken_phoneme_score(item: dict[str, Any]) -> float | None:
    candidates = _nbest_phonemes(item)
    if not candidates:
        return None
    score = candidates[0].get("Score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    return float(score)


def _nbest_phonemes(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = item.get("NBestPhonemes")
    nested = item.get("PronunciationAssessment")
    if not isinstance(candidates, list) and isinstance(nested, dict):
        candidates = nested.get("NBestPhonemes")
    return (
        [candidate for candidate in candidates if isinstance(candidate, dict)]
        if isinstance(candidates, list)
        else []
    )


def _strong_local_phoneme_mismatch(
    items: list[dict[str, Any]], expected_phoneme: str | None
) -> dict[str, Any] | None:
    if not expected_phoneme:
        return None
    expected = expected_phoneme.strip().lower()
    for item in items:
        phoneme = item.get("Phoneme")
        if not isinstance(phoneme, str) or phoneme.strip().lower() != expected:
            continue
        candidates = _nbest_phonemes(item)
        if not candidates:
            return None
        leading = candidates[0]
        leading_phoneme = leading.get("Phoneme")
        leading_score = leading.get("Score")
        if (
            not isinstance(leading_phoneme, str)
            or leading_phoneme.strip().lower() == expected
            or isinstance(leading_score, bool)
            or not isinstance(leading_score, (int, float))
            or leading_score < LOCAL_PHONEME_MISMATCH_CANDIDATE_SCORE
        ):
            return None
        expected_candidate = next(
            (
                candidate
                for candidate in candidates
                if isinstance(candidate.get("Phoneme"), str)
                and candidate["Phoneme"].strip().lower() == expected
            ),
            None,
        )
        expected_candidate_score = (
            expected_candidate.get("Score")
            if isinstance(expected_candidate, dict)
            else None
        )
        if expected_candidate is None:
            if len(candidates) < 3:
                return None
            return {
                "leading_phoneme": leading_phoneme.strip(),
                "leading_score": float(leading_score),
                "expected_candidate_score": None,
                "expected_candidate_missing": True,
                "score_margin": None,
            }
        if (
            isinstance(expected_candidate_score, bool)
            or not isinstance(expected_candidate_score, (int, float))
        ):
            return None
        score_margin = float(leading_score) - float(expected_candidate_score)
        if score_margin < LOCAL_PHONEME_MISMATCH_MIN_SCORE_MARGIN:
            return None
        return {
            "leading_phoneme": leading_phoneme.strip(),
            "leading_score": float(leading_score),
            "expected_candidate_score": float(expected_candidate_score),
            "expected_candidate_missing": False,
            "score_margin": score_margin,
        }
    return None


def _strongest_vowel_candidate(
    item: dict[str, Any],
) -> tuple[str, float] | None:
    vowels: list[tuple[str, float]] = []
    for candidate in _nbest_phonemes(item):
        phoneme = candidate.get("Phoneme")
        score = candidate.get("Score")
        if (
            isinstance(phoneme, str)
            and phoneme.strip().lower() in IPA_VOWELS
            and not isinstance(score, bool)
            and isinstance(score, (int, float))
        ):
            vowels.append((phoneme.strip().lower(), float(score)))
    return max(vowels, key=lambda value: value[1]) if vowels else None


def _has_rhotic_candidate(item: dict[str, Any]) -> bool:
    return any(
        isinstance(candidate.get("Phoneme"), str)
        and _contains_rhotic(candidate["Phoneme"])
        for candidate in _nbest_phonemes(item)
    )


def _contains_rhotic(value: str) -> bool:
    normalized = value.strip().lower()
    return any(rhotic in normalized for rhotic in ("r", "ɹ", "ɚ", "ɝ"))


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
    evidence_score: int,
    *,
    focus_match: bool,
    pattern_weight: int,
    focus_priority: int | None = None,
) -> int:
    focus_bonus = (
        {1: 15, 2: 10, 3: 5}.get(focus_priority, 10)
        if focus_match
        else 0
    )
    return min(100, evidence_score + pattern_weight + focus_bonus)


def _catalog_pattern_for_local_mismatch(
    expected_phoneme: str,
    observed_phoneme: str,
    *,
    word_final: bool,
):
    pattern = substitution_pattern(expected_phoneme, observed_phoneme)
    if pattern and (
        "word_final" in pattern.contexts
        and "any" not in pattern.contexts
        and not word_final
    ):
        pattern = None
    if pattern:
        return pattern
    if word_final:
        final_pattern = pattern_by_id("final_consonant_weakening")
        if (
            final_pattern
            and final_pattern.runtime_support in ("active", "partial")
            and expected_phoneme in final_pattern.expected_phonemes
        ):
            return final_pattern
    inventory_pattern = pattern_by_id("non_native_consonant_mapping")
    if (
        inventory_pattern
        and inventory_pattern.runtime_support in ("active", "partial")
        and expected_phoneme in inventory_pattern.expected_phonemes
    ):
        return inventory_pattern
    return None


def _authorized_local_nbest_candidates(
    azure: AzureSpeechResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None,
) -> list[_PronunciationCandidate]:
    """Grade decisive local N-best mismatches authorized by focus or catalog."""
    assessment = azure.pronunciation
    if not assessment:
        return []
    candidates: list[_PronunciationCandidate] = []
    for word_index, word in enumerate(assessment.words):
        usable_phonemes = [
            item
            for item in word.phonemes
            if isinstance(item.get("Phoneme"), str) and item["Phoneme"].strip()
        ]
        for phoneme_index, phoneme in enumerate(usable_phonemes):
            expected = phoneme["Phoneme"].strip().lower()
            mismatch = _strong_local_phoneme_mismatch([phoneme], expected)
            if not mismatch:
                continue
            observed = mismatch["leading_phoneme"].lower()
            word_final = phoneme_index == len(usable_phonemes) - 1
            focus_rank = _local_mismatch_focus_rank(
                word.word,
                expected_phoneme=expected,
                observed_phoneme=observed,
                phoneme_index=phoneme_index,
                word_final=word_final,
                focus=focus,
                focus_items=focus_items,
            )
            catalog_pattern = _catalog_pattern_for_local_mismatch(
                expected, observed, word_final=word_final
            )
            if focus_rank is None and catalog_pattern is None:
                continue

            aggregate_accuracy = _nested_accuracy_score(phoneme)
            expected_candidate_score = mismatch.get("expected_candidate_score")
            local_expected_score = (
                float(expected_candidate_score)
                if isinstance(expected_candidate_score, (int, float))
                and not isinstance(expected_candidate_score, bool)
                else 0.0
            )
            evidence_score = _phoneme_evidence_score(
                expected_accuracy=local_expected_score,
                word_accuracy=word.accuracy_score,
                candidate_mismatch=True,
                error_type=word.error_type,
            )
            focus_priority = focus_rank[0] if focus_rank else None
            focus_order = focus_rank[1] if focus_rank else None
            priority_score = _priority_score(
                evidence_score,
                focus_match=focus_rank is not None,
                pattern_weight=(catalog_pattern.priority_weight if catalog_pattern else 0),
                focus_priority=focus_priority,
            )
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_rank is not None,
                    severity=priority_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id=(catalog_pattern.id if catalog_pattern else None),
                    evidence_score=evidence_score,
                    priority_score=priority_score,
                    evidence={
                        "word": word.word,
                        "expected_phoneme": expected,
                        "leading_spoken_phoneme": observed,
                        "expected_accuracy": aggregate_accuracy,
                        "word_accuracy": word.accuracy_score,
                        "error_type": word.error_type,
                        "strong_local_phoneme_mismatch": True,
                        "local_mismatch": mismatch,
                        "authorization": (
                            "authored_focus" if focus_rank is not None else "catalog"
                        ),
                    },
                    issue=_word_issue(
                        word=word.word,
                        phoneme=expected,
                        focus_match=focus_rank is not None,
                        final_phoneme=word_final,
                    ),
                    focus_priority=focus_priority,
                    focus_order=focus_order,
                )
            )
    return candidates


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


def _contextual_st_cluster_alignment(
    azure: AzureSpeechResult,
    *,
    evaluation_context: dict[str, Any],
) -> dict[str, Any] | None:
    assessment = azure.pronunciation
    target_word = _st_cluster_target(evaluation_context)
    if not assessment or not target_word:
        return None
    stream: list[dict[str, Any]] = []
    for word_index, word in enumerate(assessment.words):
        for phoneme in word.phonemes:
            spoken = _leading_spoken_phoneme(phoneme)
            expected = phoneme.get("Phoneme")
            sound = spoken or (expected if isinstance(expected, str) else None)
            if not sound:
                continue
            duration = phoneme.get("Duration")
            stream.append(
                {
                    "word_index": word_index,
                    "sound": sound.strip().lower(),
                    "duration_100ns": (
                        int(duration)
                        if isinstance(duration, (int, float))
                        and not isinstance(duration, bool)
                        else None
                    ),
                }
            )
    for index in range(len(stream) - 2):
        first, inserted, final = stream[index : index + 3]
        if (
            first["sound"] == "s"
            and inserted["sound"] in IPA_VOWELS
            and final["sound"] == "t"
        ):
            return {
                "target_word": target_word,
                "expected_cluster": ["s", "t"],
                "spoken_sequence": [
                    first["sound"],
                    inserted["sound"],
                    final["sound"],
                ],
                "first_word_index": first["word_index"],
                "inserted_word_index": inserted["word_index"],
                "final_word_index": final["word_index"],
                "inserted_vowel_duration_100ns": inserted["duration_100ns"],
                "context_aligned": True,
            }
    return None


def _cluster_artifact_language_transcript(
    azure: AzureSpeechResult,
    alignment: dict[str, Any] | None,
) -> str | None:
    assessment = azure.pronunciation
    if not assessment or not alignment:
        return None
    artifact_index = alignment.get("first_word_index")
    if (
        not isinstance(artifact_index, int)
        or alignment.get("inserted_word_index") != artifact_index
        or alignment.get("final_word_index") != artifact_index
        or artifact_index + 1 >= len(assessment.words)
    ):
        return None
    target_word = str(alignment.get("target_word") or "").lower()
    following_word = assessment.words[artifact_index + 1].word.lower()
    if following_word != target_word:
        return None
    cleaned = " ".join(
        word.word
        for index, word in enumerate(assessment.words)
        if index != artifact_index and word.error_type.lower() != "insertion"
    )
    return cleaned if _uses_present_continuous(cleaned) else None


def _cluster_epenthesis_candidate(
    azure: AzureSpeechResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None = None,
    evaluation_context: dict[str, Any],
) -> _PronunciationCandidate | None:
    alignment = _contextual_st_cluster_alignment(
        azure, evaluation_context=evaluation_context
    )
    if not alignment:
        return None
    inserted_duration = alignment.get("inserted_vowel_duration_100ns")
    if (
        not isinstance(inserted_duration, int)
        or inserted_duration
        < CLUSTER_CONTEXT_MIN_INSERTED_VOWEL_DURATION_100NS
    ):
        return None
    pattern = pattern_by_id("cluster_epenthesis")
    if not pattern:
        return None
    target_word = str(alignment["target_word"])
    focus_rank = _pronunciation_focus_rank(
        target_word,
        focus=focus,
        focus_items=focus_items,
        general_markers=("consonant cluster",),
    )
    focus_priority = focus_rank[0] if focus_rank else None
    focus_order = focus_rank[1] if focus_rank else None
    focus_match = focus_rank is not None
    duration_ms = inserted_duration / 10_000
    evidence_score = min(95, round(60 + max(0, duration_ms - 80) * 0.5))
    priority_score = _priority_score(
        evidence_score,
        focus_match=focus_match,
        pattern_weight=pattern.priority_weight,
        focus_priority=focus_priority,
    )
    return _PronunciationCandidate(
        word_index=int(alignment["first_word_index"]),
        focus_match=focus_match,
        severity=priority_score,
        status=AssessmentTokenStatus.NEEDS_WORK,
        pattern_id=pattern.id,
        evidence_score=evidence_score,
        priority_score=priority_score,
        evidence={
            **alignment,
            "duration_scored": True,
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
        focus_priority=focus_priority,
        focus_order=focus_order,
    )


def _s_cluster_epenthesis_candidates(
    azure: AzureSpeechResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None = None,
) -> list[_PronunciationCandidate]:
    assessment = azure.pronunciation
    pattern = pattern_by_id("cluster_epenthesis")
    if not assessment or not pattern:
        return []
    candidates: list[_PronunciationCandidate] = []
    for word_index, word in enumerate(assessment.words):
        if len(word.phonemes) < 2:
            continue
        syllable = _lowest_scored_item(word.syllables, "Syllable")
        syllable_score = syllable[1] if syllable else None
        for phoneme_index in (0,):
            first = word.phonemes[phoneme_index]
            second = word.phonemes[phoneme_index + 1]
            first_expected = first.get("Phoneme")
            second_expected = second.get("Phoneme")
            second_accuracy = _nested_accuracy_score(second)
            if (
                not isinstance(first_expected, str)
                or first_expected.strip().lower() != "s"
                or not isinstance(second_expected, str)
                or second_expected.strip().lower() in IPA_VOWELS
                or second_accuracy is None
                or second_accuracy > CLUSTER_STRONG_VOWEL_CONSONANT_THRESHOLD
            ):
                continue
            leading_spoken = _leading_spoken_phoneme(second)
            leading_spoken_score = _leading_spoken_phoneme_score(second)
            strongest_vowel = _strongest_vowel_candidate(second)
            if not leading_spoken or not strongest_vowel:
                continue
            vowel_phoneme, vowel_score = strongest_vowel
            if vowel_score < CLUSTER_SECONDARY_VOWEL_SCORE_THRESHOLD:
                continue
            vowel_is_leading = leading_spoken.lower() in IPA_VOWELS
            raw_duration = second.get("Duration")
            duration = (
                int(raw_duration)
                if isinstance(raw_duration, (int, float))
                and not isinstance(raw_duration, bool)
                else None
            )
            support = {
                "word_accuracy": (
                    word.accuracy_score is not None
                    and word.accuracy_score <= CLUSTER_WORD_SUPPORT_THRESHOLD
                ),
                "syllable_accuracy": (
                    syllable_score is not None
                    and syllable_score <= CLUSTER_SYLLABLE_SUPPORT_THRESHOLD
                ),
                "segment_duration": (
                    duration is not None
                    and duration >= CLUSTER_SEGMENT_DURATION_SUPPORT_100NS
                ),
            }
            support_count = sum(support.values())
            ultra_strong_central_vowel = (
                not vowel_is_leading
                and vowel_phoneme in CENTRAL_EPENTHETIC_VOWELS
                and vowel_score
                >= CLUSTER_ULTRA_STRONG_SECONDARY_VOWEL_SCORE_THRESHOLD
                and leading_spoken_score is not None
                and leading_spoken_score - vowel_score
                <= CLUSTER_ULTRA_STRONG_SECONDARY_VOWEL_MAX_GAP
                and duration is not None
                and duration >= CLUSTER_ULTRA_STRONG_SEGMENT_DURATION_100NS
            )
            strong_secondary_vowel_exception = (
                not vowel_is_leading
                and second_accuracy > CLUSTER_SECOND_CONSONANT_THRESHOLD
                and (
                    (
                        vowel_score
                        >= CLUSTER_STRONG_SECONDARY_VOWEL_SCORE_THRESHOLD
                        and support_count >= 2
                    )
                    or ultra_strong_central_vowel
                )
            )
            if (
                second_accuracy > CLUSTER_SECOND_CONSONANT_THRESHOLD
                and not strong_secondary_vowel_exception
            ):
                continue
            if (
                (vowel_is_leading and support_count < 1)
                or (
                    not vowel_is_leading
                    and support_count < 2
                    and not ultra_strong_central_vowel
                )
            ):
                continue
            base_evidence = _phoneme_evidence_score(
                expected_accuracy=second_accuracy,
                word_accuracy=word.accuracy_score,
                candidate_mismatch=vowel_is_leading,
                error_type=word.error_type,
            )
            vowel_strength_bonus = round(
                max(0, vowel_score - CLUSTER_SECONDARY_VOWEL_SCORE_THRESHOLD)
                * 0.3
            )
            evidence_score = min(
                100,
                base_evidence
                + 15
                + 3 * support_count
                + vowel_strength_bonus,
            )
            focus_rank = _pronunciation_focus_rank(
                word.word,
                focus=focus,
                focus_items=focus_items,
                general_markers=("consonant cluster",),
            )
            focus_priority = focus_rank[0] if focus_rank else None
            focus_order = focus_rank[1] if focus_rank else None
            focus_match = focus_rank is not None
            priority_score = _priority_score(
                evidence_score,
                focus_match=focus_match,
                pattern_weight=pattern.priority_weight,
                focus_priority=focus_priority,
            )
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=priority_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id=pattern.id,
                    evidence_score=evidence_score,
                    priority_score=priority_score,
                    evidence={
                        "word": word.word,
                        "expected_cluster": [
                            "s",
                            second_expected.strip().lower(),
                        ],
                        "leading_spoken_phoneme": leading_spoken.lower(),
                        "leading_spoken_phoneme_score": leading_spoken_score,
                        "vowel_candidate": vowel_phoneme,
                        "vowel_candidate_score": vowel_score,
                        "vowel_is_leading": vowel_is_leading,
                        "strong_secondary_vowel_exception": (
                            strong_secondary_vowel_exception
                        ),
                        "ultra_strong_central_vowel": (
                            ultra_strong_central_vowel
                        ),
                        "expected_consonant_accuracy": second_accuracy,
                        "word_accuracy": word.accuracy_score,
                        "syllable_accuracy": syllable_score,
                        "segment_duration_100ns": duration,
                        "support": support,
                    },
                    issue=EvaluationIssue(
                        category=(
                            IssueCategory.FOCUS
                            if focus_match
                            else IssueCategory.PRONUNCIATION
                        ),
                        description_en=(
                            f"Say '{word.word}' smoothly without adding "
                            "an extra sound between the first consonants."
                        ),
                        description_th=(
                            f"ลองพูดคำว่า '{word.word}' ให้ต่อเนื่อง "
                            "โดยไม่เพิ่มเสียงแทรกระหว่างพยัญชนะต้น"
                        ),
                    ),
                    focus_priority=focus_priority,
                    focus_order=focus_order,
                )
            )
            break
    return candidates


def _rhotic_vowel_deletion_candidates(
    azure: AzureSpeechResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None = None,
) -> list[_PronunciationCandidate]:
    assessment = azure.pronunciation
    pattern = pattern_by_id("r_l_confusion")
    if not assessment or not pattern:
        return []
    candidates: list[_PronunciationCandidate] = []
    for word_index, word in enumerate(assessment.words):
        syllable = _lowest_scored_item(word.syllables, "Syllable")
        syllable_score = syllable[1] if syllable else None
        for phoneme in word.phonemes:
            expected = phoneme.get("Phoneme")
            accuracy = _nested_accuracy_score(phoneme)
            if (
                not isinstance(expected, str)
                or not _contains_rhotic(expected)
                or accuracy is None
            ):
                continue
            leading_spoken = _leading_spoken_phoneme(phoneme)
            if (
                not leading_spoken
                or leading_spoken.lower() not in IPA_VOWELS
                or _contains_rhotic(leading_spoken)
            ):
                continue
            leading_spoken_score = _leading_spoken_phoneme_score(phoneme)
            no_rhotic_nbest_candidate = not _has_rhotic_candidate(phoneme)
            final_phoneme = bool(word.phonemes and word.phonemes[-1] is phoneme)
            strong_final_r_mismatch = (
                final_phoneme
                and no_rhotic_nbest_candidate
                and leading_spoken_score is not None
                and leading_spoken_score
                >= RHOTIC_FINAL_MISMATCH_MIN_CANDIDATE_SCORE
            )
            if (
                accuracy > RHOTIC_VOWEL_ACCURACY_THRESHOLD
                and not strong_final_r_mismatch
            ):
                continue
            support = {
                "word_accuracy": (
                    word.accuracy_score is not None
                    and word.accuracy_score <= CLUSTER_WORD_SUPPORT_THRESHOLD
                ),
                "syllable_accuracy": (
                    syllable_score is not None and syllable_score <= 60
                ),
                "no_rhotic_nbest_candidate": no_rhotic_nbest_candidate,
            }
            if sum(support.values()) < 2 and not strong_final_r_mismatch:
                continue
            base_evidence = _phoneme_evidence_score(
                expected_accuracy=accuracy,
                word_accuracy=word.accuracy_score,
                candidate_mismatch=True,
                error_type=word.error_type,
            )
            evidence_score = min(
                100,
                base_evidence
                + 3 * sum(support.values()),
            )
            if strong_final_r_mismatch:
                evidence_score = max(
                    evidence_score,
                    min(
                        100,
                        round(70 + (leading_spoken_score - 90) * 2),
                    ),
                )
            if evidence_score < RHOTIC_VOWEL_MIN_EVIDENCE_SCORE:
                continue
            focus_rank = _pronunciation_focus_rank(
                word.word,
                focus=focus,
                focus_items=focus_items,
                phonemes=(expected, leading_spoken),
            )
            focus_priority = focus_rank[0] if focus_rank else None
            focus_order = focus_rank[1] if focus_rank else None
            focus_match = focus_rank is not None
            priority_score = _priority_score(
                evidence_score,
                focus_match=focus_match,
                pattern_weight=pattern.priority_weight,
                focus_priority=focus_priority,
            )
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=priority_score,
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    pattern_id=pattern.id,
                    evidence_score=evidence_score,
                    priority_score=priority_score,
                    evidence={
                        "word": word.word,
                        "transfer_type": "post_vocalic_r_deletion",
                        "expected_phoneme": expected.strip().lower(),
                        "leading_spoken_phoneme": leading_spoken.lower(),
                        "leading_spoken_phoneme_score": leading_spoken_score,
                        "expected_accuracy": accuracy,
                        "word_accuracy": word.accuracy_score,
                        "syllable_accuracy": syllable_score,
                        "support": support,
                        "strong_final_r_mismatch": strong_final_r_mismatch,
                    },
                    issue=EvaluationIssue(
                        category=(
                            IssueCategory.FOCUS
                            if focus_match
                            else IssueCategory.PRONUNCIATION
                        ),
                        description_en=(
                            f"Say '{word.word}' again with a clear r sound."
                        ),
                        description_th=(
                            f"ลองพูดคำว่า '{word.word}' อีกครั้ง "
                            "โดยออกเสียง r ให้ชัดเจน"
                        ),
                    ),
                    focus_priority=focus_priority,
                    focus_order=focus_order,
                )
            )
            break
    return candidates


def _unscripted_pronunciation_candidates(
    azure: AzureSpeechResult,
    *,
    focus: str,
    focus_items: list[dict[str, Any]] | None = None,
    evaluation_context: dict[str, Any],
) -> list[_PronunciationCandidate]:
    assessment = azure.pronunciation
    if not assessment:
        return []
    candidates = _authorized_local_nbest_candidates(
        azure,
        focus=focus,
        focus_items=focus_items,
    )
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
            focus_rank = _pronunciation_focus_rank(
                word.word,
                focus=focus,
                focus_items=focus_items,
                phonemes=(expected, spoken),
            )
            focus_priority = focus_rank[0] if focus_rank else None
            focus_order = focus_rank[1] if focus_rank else None
            focus_match = focus_rank is not None
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
                focus_priority=focus_priority,
            )
            if final_phoneme:
                description_en = f"Say '{word.word}' again, focusing on the ending."
                description_th = f"ลองพูดคำว่า '{word.word}' อีกครั้ง โดยเน้นเสียงท้ายคำ"
            else:
                description_en = f"Say '{word.word}' again clearly."
                description_th = f"ลองพูดคำว่า '{word.word}' อีกครั้งให้ชัดเจน"
            if any(
                candidate.word_index == word_index
                and candidate.evidence.get("expected_phoneme") == expected
                for candidate in candidates
            ):
                continue
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
                    focus_priority=focus_priority,
                    focus_order=focus_order,
                )
            )
    contextual_alignment = _contextual_st_cluster_alignment(
        azure, evaluation_context=evaluation_context
    )
    contextual_target = (
        str(contextual_alignment.get("target_word") or "").lower()
        if contextual_alignment
        else ""
    )
    contextual_target_indices = {
        index
        for index, word in enumerate(assessment.words)
        if contextual_target and word.word.lower() == contextual_target
    }
    if contextual_target_indices:
        candidates = [
            candidate
            for candidate in candidates
            if candidate.word_index not in contextual_target_indices
        ]
    cluster_candidate = _cluster_epenthesis_candidate(
        azure,
        focus=focus,
        focus_items=focus_items,
        evaluation_context=evaluation_context,
    )
    if cluster_candidate:
        candidates.append(cluster_candidate)
    existing_cluster_words = {
        candidate.word_index
        for candidate in candidates
        if candidate.pattern_id == "cluster_epenthesis"
    }
    specialized_candidates = [
        candidate
        for candidate in _s_cluster_epenthesis_candidates(
            azure,
            focus=focus,
            focus_items=focus_items,
        )
        if candidate.word_index not in existing_cluster_words
        and candidate.word_index not in contextual_target_indices
    ]
    specialized_candidates.extend(
        _rhotic_vowel_deletion_candidates(
            azure,
            focus=focus,
            focus_items=focus_items,
        )
    )
    for specialized in specialized_candidates:
        candidates = [
            candidate
            for candidate in candidates
            if not (
                candidate.word_index == specialized.word_index
                and candidate.pattern_id is None
            )
        ]
        if not any(
            candidate.word_index == specialized.word_index
            and candidate.pattern_id == specialized.pattern_id
            for candidate in candidates
        ):
            candidates.append(specialized)
    return _select_display_candidates(candidates)[:2]


def _pronunciation_policy_metadata(
    candidates: list[_PronunciationCandidate],
    *,
    focus_issues: list[EvaluationIssue],
    prosody: dict[str, Any] | None = None,
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
                "focus_priority": candidate.focus_priority,
                "focus_order": candidate.focus_order,
                "evidence": candidate.evidence,
            }
            for candidate in candidates
        ],
        "focus_validation_issue_count": len(focus_issues),
        "prosody": prosody or {
            "enabled": True,
            "score": None,
            "learner_feedback_enabled": False,
            "benchmark_status": "collecting",
        },
    }


def _prosody_policy_metadata(
    azure: AzureSpeechResult, *, focus: str
) -> dict[str, Any]:
    assessment = azure.pronunciation
    words = assessment.words if assessment else []
    break_signals: list[dict[str, Any]] = []
    monotone_detected = False
    monotone_confidences: list[float] = []
    for index, word in enumerate(words):
        if (
            word.unexpected_break_confidence is not None
            and word.unexpected_break_confidence
            > PROSODY_BREAK_CONFIDENCE_THRESHOLD
        ):
            break_signals.append(
                {
                    "type": "unexpected_break",
                    "word": word.word,
                    "word_index": index,
                    "confidence": word.unexpected_break_confidence,
                    "break_length": word.break_length,
                }
            )
        if (
            word.missing_break_confidence is not None
            and word.missing_break_confidence
            > PROSODY_BREAK_CONFIDENCE_THRESHOLD
        ):
            break_signals.append(
                {
                    "type": "missing_break",
                    "word": word.word,
                    "word_index": index,
                    "confidence": word.missing_break_confidence,
                    "break_length": word.break_length,
                }
            )
        if any(
            error_type.strip().lower() == "monotone"
            for error_type in word.intonation_error_types
        ):
            monotone_detected = True
        if word.monotone_syllable_pitch_delta_confidence is not None:
            monotone_confidences.append(
                word.monotone_syllable_pitch_delta_confidence
            )

    normalized_focus = _normalized_match_text(focus)
    focus_relevant = any(
        marker in normalized_focus
        for marker in (
            "prosody",
            "stress",
            "intonation",
            "rhythm",
            "linking",
            "connected speech",
            "fluency",
        )
    )
    utterance_eligible = len(words) >= PROSODY_MIN_WORDS
    specific_signal_detected = bool(break_signals) or monotone_detected
    return {
        "enabled": True,
        "score": assessment.prosody_score if assessment else None,
        "word_count": len(words),
        "minimum_word_count": PROSODY_MIN_WORDS,
        "utterance_eligible": utterance_eligible,
        "break_confidence_threshold": PROSODY_BREAK_CONFIDENCE_THRESHOLD,
        "break_signals": break_signals,
        "monotone_detected": monotone_detected,
        "monotone_syllable_pitch_delta_confidence": (
            max(monotone_confidences) if monotone_confidences else None
        ),
        "specific_signal_detected": specific_signal_detected,
        "focus_relevant": focus_relevant,
        "future_feedback_eligible": (
            utterance_eligible and specific_signal_detected and focus_relevant
        ),
        "learner_feedback_enabled": False,
        "benchmark_status": "collecting",
    }


def _uses_present_continuous(transcript: str) -> bool:
    normalized = _normalized_match_text(transcript)
    be = r"(?:am|is|are|i'm|you're|we're|they're|he's|she's|it's)"
    return bool(re.search(rf"\b{be}\s+[a-z]+ing\b", normalized))


def _focus_validation_issues(
    azure: AzureSpeechResult,
    *,
    focus: str,
    transcript_override: str | None = None,
) -> list[EvaluationIssue]:
    normalized_focus = _normalized_match_text(focus)
    transcript = transcript_override or azure.transcript
    if "present continuous" not in normalized_focus:
        return []
    if (
        azure.confidence is None
        or azure.confidence < FOCUS_TEXT_VALIDATION_CONFIDENCE
        or not transcript
        or _uses_present_continuous(transcript)
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


def _short_gate_status(instructional_attempt_number: int) -> EvaluationStatus:
    return (
        EvaluationStatus.RETRY
        if instructional_attempt_number == 1
        else EvaluationStatus.CONTINUE_WITH_CORRECTION
    )


def _short_gate_focus_evaluation(
    azure: AzureSpeechResult,
    *,
    reference_text: str,
    targets: list[_P1FocusTarget],
    policy: dict[str, Any],
    instructional_attempt_number: int,
) -> SpeakingEvaluation:
    target_by_key = {
        (target.word_index, target.expected_segment, target.focus_order): target
        for target in targets
    }
    issues: list[EvaluationIssue] = []
    seen_words: set[str] = set()
    for evidence in policy.get("targets") or []:
        if evidence.get("result") != "diverged":
            continue
        target = target_by_key.get(
            (
                evidence.get("word_index"),
                evidence.get("expected_segment"),
                evidence.get("focus_order"),
            )
        )
        if not target or target.word in seen_words:
            continue
        seen_words.add(target.word)
        if target.position == "initial":
            issue = EvaluationIssue(
                category=IssueCategory.FOCUS,
                description_en=(
                    f"Say '{target.word}' again, focusing on the beginning."
                ),
                description_th=(
                    f"ลองพูดคำว่า '{target.word}' อีกครั้ง โดยเน้นเสียงต้นคำ"
                ),
            )
        else:
            issue = _word_issue(
                word=target.word,
                phoneme=target.expected_segment,
                focus_match=True,
                final_phoneme=target.position == "final",
            )
        issues.append(issue)
        if len(issues) >= MAX_DISPLAYED_ISSUES:
            break

    if not issues:
        issues = [
            EvaluationIssue(
                category=IssueCategory.FOCUS,
                description_en="Say the target sentence once more, slowly and clearly.",
                description_th="ลองพูดประโยคเป้าหมายอีกครั้งอย่างช้า ๆ และชัดเจน",
            )
        ]
    status = _short_gate_status(instructional_attempt_number)
    return SpeakingEvaluation(
        status=status,
        transcript=azure.transcript,
        content=ContentEvaluation(
            meaning_correct=True,
            relevant=True,
            target_usage_correct=True,
            grammar_correct=True,
        ),
        pronunciation=PronunciationEvaluation(intelligible=True, issues=issues),
        detected_issues=issues,
        displayed_issues=issues,
        corrected_answer=reference_text,
        feedback_en=(
            issues[0].description_en
            if len(issues) == 1
            else "Focus on these two parts, then try once more."
        ),
        feedback_th=(
            issues[0].description_th
            if len(issues) == 1
            else "เน้นสองจุดนี้ แล้วลองพูดอีกครั้ง"
        ),
        retry_focus=(
            [issue.description_en for issue in issues]
            if status == EvaluationStatus.RETRY
            else []
        ),
    )


def _short_gate_unrelated_evaluation(
    azure: AzureSpeechResult,
    *,
    reference_text: str,
    instructional_attempt_number: int,
) -> SpeakingEvaluation:
    issue = EvaluationIssue(
        category=IssueCategory.FOCUS,
        description_en=(
            "That didn't match the sentence. Listen, then say the whole "
            "sentence again."
        ),
        description_th=(
            "เสียงที่พูดยังไม่ตรงกับประโยค "
            "ลองฟังแล้วพูดทั้งประโยคอีกครั้ง"
        ),
    )
    status = _short_gate_status(instructional_attempt_number)
    return SpeakingEvaluation(
        status=status,
        transcript=azure.transcript,
        content=ContentEvaluation(
            meaning_correct=False,
            relevant=False,
            target_usage_correct=False,
            grammar_correct=None,
        ),
        pronunciation=PronunciationEvaluation(intelligible=True),
        detected_issues=[issue],
        displayed_issues=[issue],
        corrected_answer=reference_text,
        feedback_en=issue.description_en,
        feedback_th=issue.description_th,
        retry_focus=(
            [issue.description_en]
            if status == EvaluationStatus.RETRY
            else []
        ),
    )


def _select_display_candidates(
    candidates: list[_PronunciationCandidate],
) -> list[_PronunciationCandidate]:
    ordered = sorted(candidates, key=_candidate_sort_key, reverse=True)
    return ordered[:MAX_DISPLAYED_ISSUES]


def _candidate_comparison_key(
    candidate: _PronunciationCandidate,
) -> str | None:
    word = str(
        candidate.evidence.get("word")
        or candidate.evidence.get("target_word")
        or ""
    ).strip().lower()
    expected = str(
        candidate.evidence.get("expected_phoneme")
        or candidate.evidence.get("expected_cluster")
        or ""
    ).strip().lower()
    if not word or (not candidate.pattern_id and not expected):
        return None
    return f"{candidate.pattern_id or 'generic'}:{word}:{expected}"


def _policy_match_comparison_key(match: dict[str, Any]) -> str | None:
    evidence = match.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    word = str(
        evidence.get("word") or evidence.get("target_word") or ""
    ).strip().lower()
    expected = str(
        evidence.get("expected_phoneme")
        or evidence.get("expected_cluster")
        or ""
    ).strip().lower()
    pattern_id = match.get("pattern_id")
    if not word or (not pattern_id and not expected):
        return None
    return f"{pattern_id or 'generic'}:{word}:{expected}"


def _coaching_attempt_policy(
    candidates: list[_PronunciationCandidate],
    *,
    instructional_attempt_number: int,
    previous_evaluation: dict[str, Any] | None,
) -> dict[str, Any]:
    current: dict[str, int] = {}
    for candidate in candidates:
        key = _candidate_comparison_key(candidate)
        if (
            candidate.blocking
            or candidate.evidence_score <= 0
            or key is None
        ):
            continue
        current[key] = candidate.evidence_score
    previous_policy = (
        previous_evaluation.get("_provider_policy")
        if isinstance(previous_evaluation, dict)
        else None
    )
    previous_matches = (
        previous_policy.get("matches")
        if isinstance(previous_policy, dict)
        else None
    )
    previous: dict[str, int] = {}
    if isinstance(previous_matches, list):
        for match in previous_matches:
            if not isinstance(match, dict):
                continue
            score = match.get("evidence_score")
            key = _policy_match_comparison_key(match)
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or score <= 0
                or key is None
            ):
                continue
            previous[key] = round(score)
    resolved = sorted(set(previous) - set(current))
    new_issues = sorted(set(current) - set(previous))
    improved = sorted(
        key
        for key, score in current.items()
        if key in previous
        and previous[key] - score >= COACHING_IMPROVEMENT_EVIDENCE_DELTA
    )
    return {
        "instructional_attempt_number": instructional_attempt_number,
        "improvement_evidence_delta": COACHING_IMPROVEMENT_EVIDENCE_DELTA,
        "previous_evidence": previous,
        "current_evidence": current,
        "resolved_issue_keys": resolved,
        "new_issue_keys": new_issues,
        "improved_issue_keys": improved,
        "meaningful_improvement": bool(resolved or improved),
        "coaching_only": bool(candidates)
        and not any(candidate.blocking for candidate in candidates),
    }


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
    focus_items: list[dict[str, Any]] | None = None,
    instructional_attempt_number: int = 1,
    previous_evaluation: dict[str, Any] | None = None,
    catalog_candidates: list[_PronunciationCandidate] | None = None,
) -> SpeakingEvaluation:
    if _azure_is_unclear(azure):
        return _unclear_audio_evaluation(azure.transcript)
    assessment = azure.pronunciation
    if assessment is None:
        raise EvaluatorError(
            "azure_assessment_missing",
            "Azure returned recognition without pronunciation assessment data.",
        )

    candidates = catalog_candidates if catalog_candidates is not None else []
    has_content_miscue = False
    for word_index, word in enumerate(assessment.words):
        error_type = word.error_type.lower()
        focus_rank = _pronunciation_focus_rank(
            word.word,
            focus=focus,
            focus_items=focus_items,
        )
        focus_priority = focus_rank[0] if focus_rank else None
        focus_order = focus_rank[1] if focus_rank else None
        focus_match = focus_rank is not None
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
        leading_spoken_score = (
            _leading_spoken_phoneme_score(word.phonemes[-1])
            if final_phoneme
            else None
        )
        strong_final_consonant_problem = bool(
            final_phoneme
            and phoneme_name
            and phoneme_name.strip().lower() not in IPA_VOWELS
            and phoneme_score is not None
            and phoneme_score
            <= FINAL_CONSONANT_STRONG_MISMATCH_ACCURACY_THRESHOLD
            and _expected_phoneme_is_not_leading(
                word.phonemes, phoneme_name
            )
            and leading_spoken_score is not None
            and leading_spoken_score
            >= FINAL_CONSONANT_STRONG_MISMATCH_CANDIDATE_SCORE
        )
        local_mismatch_evidence = (
            _strong_local_phoneme_mismatch(word.phonemes, phoneme_name)
            if phoneme_score is not None
            and phoneme_score <= FOCUS_PHONEME_ACCURACY_THRESHOLD
            else None
        )
        strong_local_phoneme_problem = local_mismatch_evidence is not None
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
                    blocking=True,
                    focus_priority=focus_priority,
                    focus_order=focus_order,
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
                    blocking=True,
                    focus_priority=focus_priority,
                    focus_order=focus_order,
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
            and (
                focus_phoneme_support >= 2
                or strong_local_phoneme_problem
            )
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
        if (
            focus_phoneme_problem
            or focus_word_problem
            or severe_word_problem
            or strong_final_consonant_problem
            or strong_local_phoneme_problem
        ) and not any(
            candidate.word_index == word_index for candidate in candidates
        ):
            evidence_score = (
                _phoneme_evidence_score(
                    expected_accuracy=phoneme_score,
                    word_accuracy=word.accuracy_score,
                    candidate_mismatch=_expected_phoneme_is_not_leading(
                        word.phonemes, phoneme_name
                    ),
                    error_type=word.error_type,
                )
                if phoneme_score is not None
                else round(
                    max(
                        0,
                        100
                        - (
                            word.accuracy_score
                            if word.accuracy_score is not None
                            else 100
                        ),
                    )
                )
            )
            candidates.append(
                _PronunciationCandidate(
                    word_index=word_index,
                    focus_match=focus_match,
                    severity=(
                        90
                        if focus_phoneme_problem
                        else 85
                        if strong_final_consonant_problem and focus_match
                        else 80
                        if focus_word_problem
                        else 75
                        if (
                            strong_final_consonant_problem
                            or strong_local_phoneme_problem
                        )
                        else 70
                    ),
                    status=AssessmentTokenStatus.NEEDS_WORK,
                    evidence_score=evidence_score,
                    priority_score=min(
                        100,
                        evidence_score
                        + (
                            {1: 15, 2: 10, 3: 5}.get(
                                focus_priority,
                                10,
                            )
                            if focus_match
                            else 0
                        ),
                    ),
                    evidence={
                        "word": word.word,
                        "expected_phoneme": phoneme_name,
                        "expected_accuracy": phoneme_score,
                        "word_accuracy": word.accuracy_score,
                        "syllable_accuracy": syllable_score,
                        "error_type": word.error_type,
                        "strong_final_consonant_mismatch": (
                            strong_final_consonant_problem
                        ),
                        "leading_spoken_phoneme_score": leading_spoken_score,
                        "strong_local_phoneme_mismatch": (
                            strong_local_phoneme_problem
                        ),
                        "local_mismatch": local_mismatch_evidence,
                    },
                    issue=_word_issue(
                        word=word.word,
                        phoneme=phoneme_name,
                        focus_match=focus_match,
                        final_phoneme=final_phoneme,
                    ),
                    focus_priority=focus_priority,
                    focus_order=focus_order,
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
                blocking=True,
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
                blocking=True,
                issue=EvaluationIssue(
                    category=IssueCategory.FOCUS,
                    description_en="Say the complete target sentence once more.",
                    description_th="ลองพูดประโยคเป้าหมายให้ครบอีกครั้ง",
                ),
            )
        )

    ordered_candidates = sorted(
        candidates,
        key=_candidate_sort_key,
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

    coaching_policy = _coaching_attempt_policy(
        candidates,
        instructional_attempt_number=instructional_attempt_number,
        previous_evaluation=previous_evaluation,
    )
    if (
        instructional_attempt_number >= 2
        and coaching_policy["coaching_only"]
    ):
        if (
            coaching_policy["meaningful_improvement"]
            and not coaching_policy["new_issue_keys"]
        ):
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
                    assessment_tokens=_assessment_tokens(
                        reference_text, azure, []
                    ),
                ),
                detected_issues=detected,
                feedback_en="Nice improvement—you can move on.",
                feedback_th="ดีขึ้นแล้ว ไปข้อต่อไปได้เลย",
            )
        return SpeakingEvaluation(
            status=EvaluationStatus.CONTINUE_WITH_CORRECTION,
            transcript=azure.transcript,
            content=ContentEvaluation(
                meaning_correct=True,
                relevant=True,
                target_usage_correct=True,
                grammar_correct=True,
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
                "Keep practicing this point, but you can move on for now."
            ),
            feedback_th="ฝึกจุดนี้ต่อไป แต่ตอนนี้ไปข้อต่อไปได้เลย",
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
    focus_items: list[dict[str, Any]] | None = None,
    include_transcript: bool = True,
    instructional_attempt_number: int = 1,
    previous_evaluation: dict[str, Any] | None = None,
) -> SpeakingEvaluation:
    pronunciation_display_candidates = (pronunciation_candidates or [])[:2]
    pronunciation_issues = [
        candidate.issue for candidate in pronunciation_display_candidates
    ]
    deterministic_focus_issues = (focus_issues or [])[:1]
    normalized_focus_items = _normalized_focus_items(focus_items, focus="")

    def language_rank(
        issue: LanguageEvaluationIssue,
    ) -> tuple[int | None, int | None]:
        index = issue.focus_item_index
        if index is None or index >= len(normalized_focus_items):
            return None, None
        return normalized_focus_items[index]["priority"], index

    deterministic_rank: tuple[int | None, int | None] = (None, None)
    if deterministic_focus_issues:
        markers = ("present continuous", "am/is/are", "be + -ing", "be + ing")
        matching_items = [
            (item["priority"], index)
            for index, item in enumerate(normalized_focus_items)
            if any(
                marker in _normalized_match_text(item["instruction"])
                for marker in markers
            )
        ]
        if matching_items:
            deterministic_rank = min(matching_items)

    def prioritized_issues(
        language_issues: list[LanguageEvaluationIssue],
        *,
        limit: int,
    ) -> list[EvaluationIssue]:
        ranked: list[
            tuple[EvaluationIssue, int | None, int | None, int]
        ] = []
        sequence = 0
        for issue in deterministic_focus_issues:
            ranked.append((issue, *deterministic_rank, sequence))
            sequence += 1
        for issue in language_issues:
            ranked.append((issue.public_issue(), *language_rank(issue), sequence))
            sequence += 1
        for candidate in pronunciation_display_candidates:
            ranked.append(
                (
                    candidate.issue,
                    candidate.focus_priority,
                    candidate.focus_order,
                    sequence,
                )
            )
            sequence += 1
        ranked.sort(
            key=lambda item: (
                0 if item[1] is not None else 1,
                item[1] if item[1] is not None else 4,
                item[2] if item[2] is not None else 10_000,
                item[3],
            )
        )
        return _dedupe_language_issues([item[0] for item in ranked])[:limit]

    language_displayed = language.displayed_issues or language.detected_issues
    original_displayed = _dedupe_language_issues(
        deterministic_focus_issues
        + [issue.public_issue() for issue in language_displayed]
        + pronunciation_issues
    )[:MAX_OPEN_DISPLAYED_ISSUES]
    displayed = prioritized_issues(
        language_displayed, limit=MAX_OPEN_DISPLAYED_ISSUES
    )
    display_order_changed = [
        _language_issue_concept(issue) for issue in displayed
    ] != [
        _language_issue_concept(issue) for issue in original_displayed
    ]
    detected = prioritized_issues(language.detected_issues, limit=12)
    has_material_issue = (
        language.material_error
        or bool(deterministic_focus_issues)
        or bool(pronunciation_issues)
    )
    retry_focus: list[str] = []
    retry_concepts: set[str] = set()
    retry_candidates = [
        issue.description_en for issue in displayed
    ] + language.retry_focus
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
    elif display_order_changed and displayed:
        feedback_en = displayed[0].description_en
        feedback_th = displayed[0].description_th
    else:
        feedback_en = language.feedback_en
        feedback_th = language.feedback_th
    status = (
        EvaluationStatus.RETRY
        if has_material_issue
        else EvaluationStatus.PASS
    )
    if (
        instructional_attempt_number >= 2
        and pronunciation_issues
        and not language.material_error
        and not deterministic_focus_issues
    ):
        coaching_policy = _coaching_attempt_policy(
            pronunciation_candidates or [],
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
        )
        retry_focus = []
        if (
            coaching_policy["meaningful_improvement"]
            and not coaching_policy["new_issue_keys"]
        ):
            status = EvaluationStatus.PASS
            displayed = []
            pronunciation_issues = []
            feedback_en = "Nice improvement—you can move on."
            feedback_th = "ดีขึ้นแล้ว ไปข้อต่อไปได้เลย"
        else:
            status = EvaluationStatus.CONTINUE_WITH_CORRECTION
            feedback_en = (
                "Keep practicing this point, but you can move on for now."
            )
            feedback_th = "ฝึกจุดนี้ต่อไป แต่ตอนนี้ไปข้อต่อไปได้เลย"
    return SpeakingEvaluation(
        status=status,
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
    focus_items: list[dict[str, Any]] | None = None,
    prompt_en: str | None,
    prompt_th: str | None,
    target_answers: list[str],
    examples: list[dict[str, Any]],
    instructional_attempt_number: int,
    previous_evaluation: dict[str, Any] | None = None,
) -> EvaluatorResult:
    total_started = time.monotonic()
    uses_unscripted_acoustics = practice_type in {"open", "translation"}
    context = _evaluation_context(
        practice_type=practice_type,
        focus=focus,
        focus_items=focus_items,
        prompt_en=prompt_en,
        prompt_th=prompt_th,
        target_answers=target_answers,
        examples=examples,
        instructional_attempt_number=instructional_attempt_number,
        previous_evaluation=previous_evaluation,
    )
    normalization_started = time.monotonic()
    try:
        normalized_wav = normalize_speaking_audio(
            audio_bytes,
            audio_mime_type,
            max_duration_seconds=30 if practice_type == "pronunciation" else 60,
        )
    except AudioNormalizationError as exc:
        raise EvaluatorError(exc.code, exc.detail) from exc
    normalization_ms = round((time.monotonic() - normalization_started) * 1000)

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
    azure_started = time.monotonic()
    unbiased_azure: AzureSpeechResult | None = None
    short_gate_targets: list[_P1FocusTarget] = []
    short_gate_policy: dict[str, Any] | None = None
    if practice_type == "pronunciation" and reference_text:
        reference_word_count = len(_spoken_words(reference_text))
        short_gate_targets = _short_p1_focus_targets(
            reference_text,
            focus=focus,
            focus_items=focus_items,
        )
        try:
            unbiased_azure = assess_with_azure_speech(
                normalized_wav,
                reference_text=None,
                enable_unscripted_assessment=True,
                enable_prosody_assessment=False,
            )
        except AzureSpeechError as exc:
            raise EvaluatorError(exc.code, exc.detail) from exc
        if short_gate_targets:
            short_gate_policy = _short_p1_gate_policy(
                unbiased_azure,
                reference_text=reference_text,
                targets=short_gate_targets,
            )
        else:
            short_gate_policy = {
                "eligible": False,
                "decision": "not_run",
                "reference_word_count": reference_word_count,
                "reason": (
                    "reference_too_long"
                    if reference_word_count > SHORT_P1_GATE_MAX_WORDS
                    else "no_parseable_p1_focus"
                ),
            }

    if unbiased_azure and short_gate_policy and short_gate_policy["decision"] in {
        "diverged",
        "unrelated",
    }:
        evaluation = (
            _short_gate_focus_evaluation(
                unbiased_azure,
                reference_text=reference_text or "",
                targets=short_gate_targets,
                policy=short_gate_policy,
                instructional_attempt_number=instructional_attempt_number,
            )
            if short_gate_policy["decision"] == "diverged"
            else _short_gate_unrelated_evaluation(
                unbiased_azure,
                reference_text=reference_text or "",
                instructional_attempt_number=instructional_attempt_number,
            )
        )
        azure_stage_ms = round((time.monotonic() - azure_started) * 1000)
        timings_ms = {
            "normalization": normalization_ms,
            "azure_request": unbiased_azure.latency_ms,
            "azure_stage": azure_stage_ms,
            "policy": max(0, azure_stage_ms - unbiased_azure.latency_ms),
            "gemini_request": 0,
            "evaluator_total": round((time.monotonic() - total_started) * 1000),
        }
        azure_metadata = {
            "model": AZURE_SPEECH_MODEL,
            "region": Config.AZURE_SPEECH_REGION,
            "response": unbiased_azure.raw_payload,
        }
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=unbiased_azure.latency_ms,
            usage={
                "azure": {
                    "duration_100ns": unbiased_azure.duration_100ns,
                    "request_count": 1,
                }
            },
            provider_metadata={
                "azure": azure_metadata,
                "policy": {"short_p1_gate": short_gate_policy},
                "timings_ms": timings_ms,
            },
            provider_output_text=json.dumps(
                unbiased_azure.raw_payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            evaluation_context=context,
        )

    try:
        azure = assess_with_azure_speech(
            normalized_wav,
            reference_text=reference_text,
            enable_unscripted_assessment=uses_unscripted_acoustics,
        )
    except AzureSpeechError as exc:
        raise EvaluatorError(exc.code, exc.detail) from exc

    translation_reference = (
        _translation_alignment_reference(target_answers)
        if practice_type == "translation"
        else None
    )
    translation_reference_azure: AzureSpeechResult | None = None
    translation_target_alignment: TargetAlignmentResult | None = None
    if translation_reference and not _azure_is_unclear(azure):
        try:
            translation_reference_azure = assess_with_azure_speech(
                normalized_wav,
                reference_text=translation_reference,
                enable_prosody_assessment=False,
            )
        except AzureSpeechError as exc:
            raise EvaluatorError(exc.code, exc.detail) from exc
        expected_phonemes = _target_alignment_expected_phonemes(
            translation_reference_azure
        )
        observed_phonemes = _target_alignment_observed_phonemes(azure)
        if expected_phonemes and observed_phonemes:
            translation_target_alignment = align_phonemes_to_target(
                expected_phonemes,
                observed_phonemes,
            )
    azure_stage_ms = round((time.monotonic() - azure_started) * 1000)

    azure_request_count = (
        1
        + (1 if unbiased_azure else 0)
        + (1 if translation_reference_azure else 0)
    )
    azure_duration = sum(
        duration
        for duration in (
            unbiased_azure.duration_100ns if unbiased_azure else None,
            azure.duration_100ns,
            (
                translation_reference_azure.duration_100ns
                if translation_reference_azure
                else None
            ),
        )
        if duration is not None
    )
    azure_usage = {
        "duration_100ns": azure_duration or None,
        "request_count": azure_request_count,
    }
    azure_metadata = {
        "model": AZURE_SPEECH_MODEL,
        "region": Config.AZURE_SPEECH_REGION,
        "response": azure.raw_payload,
    }
    if practice_type == "pronunciation":
        policy_started = time.monotonic()
        target_alignment: TargetAlignmentResult | None = None
        if unbiased_azure:
            expected_phonemes = _target_alignment_expected_phonemes(azure)
            observed_phonemes = _target_alignment_observed_phonemes(unbiased_azure)
            if expected_phonemes and observed_phonemes:
                target_alignment = align_phonemes_to_target(
                    expected_phonemes,
                    observed_phonemes,
                )
        scripted_candidates = _s_cluster_epenthesis_candidates(
            azure,
            focus=focus,
            focus_items=focus_items,
        )
        scripted_candidates.extend(
            _authorized_local_nbest_candidates(
                azure,
                focus=focus,
                focus_items=focus_items,
            )
        )
        scripted_candidates.extend(
            _rhotic_vowel_deletion_candidates(
                azure,
                focus=focus,
                focus_items=focus_items,
            )
        )
        if target_alignment:
            scripted_candidates.extend(
                _target_alignment_candidates(
                    target_alignment,
                    focus=focus,
                    focus_items=focus_items,
                )
            )
        evaluation = _pronunciation_evaluation(
            azure,
            reference_text=reference_text or "",
            focus=focus,
            focus_items=focus_items,
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
            catalog_candidates=scripted_candidates,
        )
        if (
            short_gate_policy
            and short_gate_policy.get("decision") == "ambiguous"
            and evaluation.status == EvaluationStatus.PASS
        ):
            evaluation = _unclear_audio_evaluation(
                unbiased_azure.transcript if unbiased_azure else None
            )
        if (
            target_alignment
            and target_alignment.classification == "unrelated"
            and evaluation.status == EvaluationStatus.PASS
        ):
            evaluation = _short_gate_unrelated_evaluation(
                unbiased_azure,
                reference_text=reference_text or "",
                instructional_attempt_number=instructional_attempt_number,
            )
        elif (
            target_alignment
            and target_alignment.classification == "ambiguous"
            and evaluation.status == EvaluationStatus.PASS
        ):
            evaluation = _unclear_audio_evaluation(unbiased_azure.transcript)
        policy_metadata = _pronunciation_policy_metadata(
            scripted_candidates,
            focus_issues=[],
            prosody=_prosody_policy_metadata(azure, focus=focus),
        )
        policy_metadata["coaching_attempt"] = _coaching_attempt_policy(
            scripted_candidates,
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
        )
        if short_gate_policy is not None:
            policy_metadata["short_p1_gate"] = short_gate_policy
        if target_alignment is not None:
            policy_metadata["target_alignment"] = target_alignment.model_dump(
                mode="json"
            )
        policy_ms = round((time.monotonic() - policy_started) * 1000)
        timings_ms = {
            "normalization": normalization_ms,
            "azure_request": azure.latency_ms
            + (unbiased_azure.latency_ms if unbiased_azure else 0),
            "azure_stage": azure_stage_ms,
            "policy": policy_ms,
            "gemini_request": 0,
            "evaluator_total": round((time.monotonic() - total_started) * 1000),
        }
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=azure.latency_ms
            + (unbiased_azure.latency_ms if unbiased_azure else 0),
            usage={"azure": azure_usage},
            provider_metadata={
                "azure": azure_metadata,
                **(
                    {
                        "unbiased_azure": {
                            "model": AZURE_SPEECH_MODEL,
                            "region": Config.AZURE_SPEECH_REGION,
                            "response": unbiased_azure.raw_payload,
                        }
                    }
                    if unbiased_azure
                    else {}
                ),
                "policy": policy_metadata,
                "timings_ms": timings_ms,
            },
            provider_output_text=json.dumps(
                (
                    {
                        "unbiased": unbiased_azure.raw_payload,
                        "scripted": azure.raw_payload,
                    }
                    if unbiased_azure
                    else azure.raw_payload
                ),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            evaluation_context=context,
        )

    policy_started = time.monotonic()
    pronunciation_candidates = (
        _unscripted_pronunciation_candidates(
            azure,
            focus=focus,
            focus_items=focus_items,
            evaluation_context=context,
        )
        if uses_unscripted_acoustics
        else []
    )
    if translation_target_alignment:
        pronunciation_candidates.extend(
            _target_alignment_candidates(
                translation_target_alignment,
                focus=focus,
                focus_items=focus_items,
            )
        )
    contextual_alignment = (
        _contextual_st_cluster_alignment(azure, evaluation_context=context)
        if uses_unscripted_acoustics
        else None
    )
    target_alignment_transcript = (
        translation_reference
        if translation_target_alignment
        and translation_target_alignment.classification == "target_like"
        else None
    )
    language_transcript_override = target_alignment_transcript or (
        _cluster_artifact_language_transcript(azure, contextual_alignment)
        if uses_unscripted_acoustics
        else None
    )
    language_azure = (
        azure.model_copy(
            update={
                "transcript": language_transcript_override,
                "alternatives": [],
            }
        )
        if language_transcript_override
        else azure
    )
    focus_issues = (
        _focus_validation_issues(
            azure,
            focus=focus,
            transcript_override=language_transcript_override,
        )
        if uses_unscripted_acoustics
        else []
    )
    policy_metadata = (
        _pronunciation_policy_metadata(
            pronunciation_candidates,
            focus_issues=focus_issues,
            prosody=_prosody_policy_metadata(azure, focus=focus),
        )
        if uses_unscripted_acoustics
        else None
    )
    if policy_metadata is not None:
        if translation_target_alignment is not None:
            policy_metadata["target_alignment"] = {
                **translation_target_alignment.model_dump(mode="json"),
                "reference_text": translation_reference,
                "language_transcript_reconstructed": bool(
                    target_alignment_transcript
                ),
            }
        if language_transcript_override and contextual_alignment:
            artifact_index = contextual_alignment["first_word_index"]
            policy_metadata["language_transcript_artifact"] = {
                "detected": True,
                "removed_word": azure.pronunciation.words[artifact_index].word,
                "evaluation_transcript": language_transcript_override,
                "inserted_vowel_duration_100ns": contextual_alignment[
                    "inserted_vowel_duration_100ns"
                ],
            }
        policy_metadata["coaching_attempt"] = _coaching_attempt_policy(
            pronunciation_candidates,
            instructional_attempt_number=instructional_attempt_number,
            previous_evaluation=previous_evaluation,
        )
    policy_ms = round((time.monotonic() - policy_started) * 1000)
    if _azure_is_unclear(azure):
        evaluation = (
            _unscripted_pronunciation_retry(azure, pronunciation_candidates)
            if pronunciation_candidates
            else _unclear_audio_evaluation(azure.transcript)
        )
        if uses_unscripted_acoustics:
            evaluation = evaluation.model_copy(update={"transcript": None})
        timings_ms = {
            "normalization": normalization_ms,
            "azure_request": azure.latency_ms,
            "azure_stage": azure_stage_ms,
            "policy": policy_ms,
            "gemini_request": 0,
            "evaluator_total": round((time.monotonic() - total_started) * 1000),
        }
        return EvaluatorResult(
            evaluation=evaluation,
            provider="microsoft",
            model=AZURE_SPEECH_MODEL,
            latency_ms=azure.latency_ms,
            usage={"azure": azure_usage},
            provider_metadata={
                "azure": azure_metadata,
                **({"policy": policy_metadata} if policy_metadata else {}),
                "timings_ms": timings_ms,
            },
            provider_output_text=json.dumps(
                azure.raw_payload, ensure_ascii=False, separators=(",", ":")
            ),
            evaluation_context=context,
        )

    gemini = evaluate_language_with_gemini(
        azure=language_azure,
        evaluation_context=context,
        instructional_attempt_number=instructional_attempt_number,
    )
    evaluation = _compose_language_evaluation(
        azure,
        gemini.evaluation,
        pronunciation_candidates=pronunciation_candidates,
        focus_issues=focus_issues,
        focus_items=context.get("focus_items"),
        include_transcript=practice_type == "pronunciation",
        instructional_attempt_number=instructional_attempt_number,
        previous_evaluation=previous_evaluation,
    )
    timings_ms = {
        "normalization": normalization_ms,
        "azure_request": azure.latency_ms
        + (
            translation_reference_azure.latency_ms
            if translation_reference_azure
            else 0
        ),
        "azure_stage": azure_stage_ms,
        "policy": policy_ms,
        "gemini_request": gemini.latency_ms,
        "evaluator_total": round((time.monotonic() - total_started) * 1000),
    }
    return EvaluatorResult(
        evaluation=evaluation,
        provider="microsoft+google",
        model=f"{AZURE_SPEECH_MODEL}+{gemini.model}",
        latency_ms=(
            azure.latency_ms
            + (
                translation_reference_azure.latency_ms
                if translation_reference_azure
                else 0
            )
            + gemini.latency_ms
        ),
        usage={"azure": azure_usage, "gemini": gemini.usage},
        provider_metadata={
            "azure": azure_metadata,
            **(
                {
                    "target_reference_azure": {
                        "model": AZURE_SPEECH_MODEL,
                        "region": Config.AZURE_SPEECH_REGION,
                        "reference_text": translation_reference,
                        "response": translation_reference_azure.raw_payload,
                    }
                }
                if translation_reference_azure
                else {}
            ),
            "gemini": gemini.provider_metadata,
            **({"policy": policy_metadata} if policy_metadata else {}),
            "timings_ms": timings_ms,
        },
        provider_output_text=gemini.provider_output_text,
        evaluation_context=context,
    )

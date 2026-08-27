"""Typed Azure Speech short-audio REST integration."""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field

from app.config import Config
from app.speaking_coach_audio import AZURE_WAV_CONTENT_TYPE


AZURE_SPEECH_MODEL = "speech-to-text-short-v1"
_VALID_REGION = re.compile(r"^[a-z0-9-]+$")


class AzureSpeechError(RuntimeError):
    """Safe Azure provider error with a stable application failure code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


class AzureTranscriptAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=1, max_length=1000)
    lexical: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)


class AzureWordAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=120)
    accuracy_score: float | None = Field(default=None, ge=0, le=100)
    error_type: str = Field(default="None", max_length=80)
    offset: int | None = None
    duration: int | None = None
    phonemes: list[dict[str, Any]] = Field(default_factory=list, max_length=40)
    syllables: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


class AzurePronunciationAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accuracy_score: float | None = Field(default=None, ge=0, le=100)
    fluency_score: float | None = Field(default=None, ge=0, le=100)
    completeness_score: float | None = Field(default=None, ge=0, le=100)
    pronunciation_score: float | None = Field(default=None, ge=0, le=100)
    prosody_score: float | None = Field(default=None, ge=0, le=100)
    words: list[AzureWordAssessment] = Field(default_factory=list, max_length=200)


class AzureSpeechResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recognition_status: str
    transcript: str | None = Field(default=None, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    alternatives: list[AzureTranscriptAlternative] = Field(
        default_factory=list, max_length=5
    )
    pronunciation: AzurePronunciationAssessment | None = None
    duration_100ns: int | None = None
    snr: float | None = None
    latency_ms: int
    raw_payload: dict[str, Any]


def _number(source: dict[str, Any], key: str) -> float | None:
    value = source.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str | None:
    return value.strip()[:1000] if isinstance(value, str) and value.strip() else None


def _assessment_value(alternative: dict[str, Any], key: str) -> float | None:
    nested = alternative.get("PronunciationAssessment")
    if isinstance(nested, dict):
        nested_value = _number(nested, key)
        if nested_value is not None:
            return nested_value
    return _number(alternative, key)


def _parse_word(raw_word: Any) -> AzureWordAssessment | None:
    if not isinstance(raw_word, dict):
        return None
    word = _text(raw_word.get("Word"))
    if not word:
        return None
    nested = raw_word.get("PronunciationAssessment")
    assessment = nested if isinstance(nested, dict) else raw_word
    phonemes = raw_word.get("Phonemes")
    safe_phonemes = (
        [item for item in phonemes if isinstance(item, dict)][:40]
        if isinstance(phonemes, list)
        else []
    )
    syllables = raw_word.get("Syllables")
    safe_syllables = (
        [item for item in syllables if isinstance(item, dict)][:20]
        if isinstance(syllables, list)
        else []
    )
    error_type = assessment.get("ErrorType")
    return AzureWordAssessment(
        word=word[:120],
        accuracy_score=_number(assessment, "AccuracyScore"),
        error_type=error_type[:80] if isinstance(error_type, str) else "None",
        offset=_integer(raw_word.get("Offset")),
        duration=_integer(raw_word.get("Duration")),
        phonemes=safe_phonemes,
        syllables=safe_syllables,
    )


def parse_azure_speech_response(
    payload: dict[str, Any], *, latency_ms: int
) -> AzureSpeechResult:
    raw_status = payload.get("RecognitionStatus")
    if raw_status == 0:
        status = "Success"
    elif isinstance(raw_status, str) and raw_status.strip():
        status = raw_status.strip()
    else:
        raise AzureSpeechError(
            "azure_schema_invalid", "Azure omitted the recognition status."
        )

    raw_alternatives = payload.get("NBest")
    candidates = raw_alternatives if isinstance(raw_alternatives, list) else []
    alternatives: list[AzureTranscriptAlternative] = []
    for candidate in candidates[:5]:
        if not isinstance(candidate, dict):
            continue
        transcript = _text(candidate.get("Display")) or _text(candidate.get("Lexical"))
        if not transcript:
            continue
        alternatives.append(
            AzureTranscriptAlternative(
                transcript=transcript,
                lexical=_text(candidate.get("Lexical")),
                confidence=_number(candidate, "Confidence"),
            )
        )

    primary = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    transcript = (
        (alternatives[0].transcript if alternatives else None)
        or _text(payload.get("DisplayText"))
    )
    confidence = _number(primary, "Confidence")

    pronunciation = None
    has_assessment = any(
        key in primary
        for key in (
            "PronunciationAssessment",
            "AccuracyScore",
            "CompletenessScore",
            "PronScore",
            "Words",
        )
    )
    if has_assessment:
        raw_words = primary.get("Words")
        words = []
        if isinstance(raw_words, list):
            words = [word for item in raw_words if (word := _parse_word(item))]
        pronunciation = AzurePronunciationAssessment(
            accuracy_score=_assessment_value(primary, "AccuracyScore"),
            fluency_score=_assessment_value(primary, "FluencyScore"),
            completeness_score=_assessment_value(primary, "CompletenessScore"),
            pronunciation_score=_assessment_value(primary, "PronScore"),
            prosody_score=_assessment_value(primary, "ProsodyScore"),
            words=words,
        )

    return AzureSpeechResult(
        recognition_status=status,
        transcript=transcript,
        confidence=confidence,
        alternatives=alternatives,
        pronunciation=pronunciation,
        duration_100ns=_integer(payload.get("Duration")),
        snr=_number(payload, "SNR"),
        latency_ms=latency_ms,
        raw_payload=payload,
    )


def assess_with_azure_speech(
    wav_bytes: bytes,
    *,
    reference_text: str | None = None,
    enable_unscripted_assessment: bool = False,
) -> AzureSpeechResult:
    """Recognize speech and optionally assess scripted or unscripted pronunciation."""

    api_key = (Config.AZURE_API_KEY or "").strip()
    region = (Config.AZURE_SPEECH_REGION or "").strip().lower()
    if not api_key or not region:
        raise AzureSpeechError(
            "azure_not_configured",
            "AZURE_API_KEY and AZURE_SPEECH_REGION must be configured.",
        )
    if not _VALID_REGION.fullmatch(region):
        raise AzureSpeechError(
            "azure_region_invalid", "AZURE_SPEECH_REGION is invalid."
        )

    headers = {
        "Ocp-Apim-Subscription-Key": api_key,
        "Content-Type": AZURE_WAV_CONTENT_TYPE,
        "Accept": "application/json",
    }
    if reference_text or enable_unscripted_assessment:
        assessment = {
            "GradingSystem": "HundredMark",
            "Granularity": "Phoneme",
            "Dimension": "Comprehensive",
            "EnableProsodyAssessment": "True",
            "PhonemeAlphabet": "IPA",
            "NBestPhonemeCount": 5,
        }
        if reference_text:
            assessment["ReferenceText"] = reference_text
            assessment["EnableMiscue"] = "True"
        serialized = json.dumps(
            assessment, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        headers["Pronunciation-Assessment"] = base64.b64encode(serialized).decode(
            "ascii"
        )

    url = (
        f"https://{region}.stt.speech.microsoft.com/"
        "speech/recognition/conversation/cognitiveservices/v1"
    )
    started = time.monotonic()
    try:
        response = requests.post(
            url,
            headers=headers,
            params={"language": "en-US", "format": "detailed", "profanity": "raw"},
            data=wav_bytes,
            timeout=Config.SPEAKING_COACH_EVALUATION_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise AzureSpeechError("azure_timeout", "Azure Speech timed out.") from exc
    except requests.RequestException as exc:
        raise AzureSpeechError(
            "azure_unavailable", "Azure Speech request failed."
        ) from exc
    latency_ms = round((time.monotonic() - started) * 1000)

    try:
        payload = response.json()
    except ValueError as exc:
        raise AzureSpeechError(
            "azure_invalid_response", "Azure Speech returned a non-JSON response."
        ) from exc
    if not response.ok:
        raise AzureSpeechError(
            f"azure_http_{response.status_code}",
            f"Azure Speech rejected the request with status {response.status_code}.",
        )
    if not isinstance(payload, dict):
        raise AzureSpeechError(
            "azure_invalid_response", "Azure Speech returned an invalid response."
        )
    return parse_azure_speech_response(payload, latency_ms=latency_ms)

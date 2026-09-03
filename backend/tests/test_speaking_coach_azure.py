import base64
import json
from types import SimpleNamespace

import pytest

from app import speaking_coach_azure as azure


def _flat_response():
    return {
        "RecognitionStatus": "Success",
        "Duration": 12_000_000,
        "SNR": 30.5,
        "NBest": [
            {
                "Confidence": 0.94,
                "Display": "Good morning.",
                "Lexical": "good morning",
                "AccuracyScore": 87,
                "FluencyScore": 91,
                "CompletenessScore": 100,
                "PronScore": 89,
                "ProsodyScore": 84,
                "Words": [
                    {
                        "Word": "morning",
                        "AccuracyScore": 52,
                        "ErrorType": "Mispronunciation",
                        "Phonemes": [
                            {"Phoneme": "m", "AccuracyScore": 90}
                        ],
                        "Syllables": [
                            {"Syllable": "mɔrnɪŋ", "AccuracyScore": 80}
                        ],
                    }
                ],
            }
        ],
    }


def test_parse_flat_rest_pronunciation_response():
    result = azure.parse_azure_speech_response(_flat_response(), latency_ms=75)

    assert result.recognition_status == "Success"
    assert result.transcript == "Good morning."
    assert result.confidence == 0.94
    assert result.pronunciation.accuracy_score == 87
    assert result.pronunciation.prosody_score == 84
    assert result.pronunciation.words[0].word == "morning"
    assert result.pronunciation.words[0].phonemes[0]["Phoneme"] == "m"
    assert result.pronunciation.words[0].syllables[0]["Syllable"] == "mɔrnɪŋ"


def test_parse_nested_pronunciation_response_shape():
    payload = _flat_response()
    primary = payload["NBest"][0]
    primary["PronunciationAssessment"] = {
        "AccuracyScore": 93,
        "FluencyScore": 90,
        "CompletenessScore": 100,
        "PronScore": 92,
    }
    primary.pop("AccuracyScore")
    primary["Words"][0]["PronunciationAssessment"] = {
        "AccuracyScore": 77,
        "ErrorType": "None",
        "Feedback": {
            "Prosody": {
                "Break": {
                    "UnexpectedBreak": {"Confidence": 0.82},
                    "MissingBreak": {"Confidence": 0.14},
                    "BreakLength": 4200000,
                },
                "Intonation": {
                    "ErrorTypes": ["Monotone"],
                    "Monotone": {
                        "SyllablePitchDeltaConfidence": 0.91
                    },
                },
            }
        },
    }

    result = azure.parse_azure_speech_response(payload, latency_ms=75)

    assert result.pronunciation.accuracy_score == 93
    assert result.pronunciation.words[0].accuracy_score == 77
    assert result.pronunciation.words[0].error_type == "None"
    assert result.pronunciation.words[0].unexpected_break_confidence == 0.82
    assert result.pronunciation.words[0].missing_break_confidence == 0.14
    assert result.pronunciation.words[0].break_length == 4_200_000
    assert result.pronunciation.words[0].intonation_error_types == ["Monotone"]
    assert (
        result.pronunciation.words[0].monotone_syllable_pitch_delta_confidence
        == 0.91
    )


def test_out_of_range_azure_prosody_confidence_is_clamped():
    payload = _flat_response()
    payload["NBest"][0]["Words"][0]["Feedback"] = {
        "Prosody": {
            "Break": {
                "UnexpectedBreak": {"Confidence": 3.0990992},
                "MissingBreak": {"Confidence": -0.25},
            }
        }
    }

    result = azure.parse_azure_speech_response(payload, latency_ms=75)
    word = result.pronunciation.words[0]

    assert word.unexpected_break_confidence == 1
    assert word.missing_break_confidence == 0
    assert (
        result.raw_payload["NBest"][0]["Words"][0]["Feedback"]["Prosody"]
        ["Break"]["UnexpectedBreak"]["Confidence"]
        == 3.0990992
    )


def test_azure_request_uses_pcm_wav_and_scripted_header(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, params, data, timeout):
        captured.update(
            url=url, headers=headers, params=params, data=data, timeout=timeout
        )
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=_flat_response,
        )

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    result = azure.assess_with_azure_speech(
        b"RIFF normalized wav", reference_text="Good morning."
    )

    assessment = json.loads(
        base64.b64decode(captured["headers"]["Pronunciation-Assessment"])
    )
    assert captured["url"].startswith(
        "https://southeastasia.stt.speech.microsoft.com/"
    )
    assert captured["headers"]["Content-Type"] == (
        "audio/wav; codecs=audio/pcm; samplerate=16000"
    )
    assert captured["params"]["format"] == "detailed"
    assert captured["data"] == b"RIFF normalized wav"
    assert assessment == {
        "ReferenceText": "Good morning.",
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableMiscue": "True",
        "EnableProsodyAssessment": "True",
        "PhonemeAlphabet": "IPA",
        "NBestPhonemeCount": 5,
    }
    assert "azure-secret" not in json.dumps(result.raw_payload)


def test_recognition_request_omits_pronunciation_header(monkeypatch):
    captured = {}

    def fake_post(_url, *, headers, params, data, timeout):
        captured["headers"] = headers
        payload = _flat_response()
        for key in (
            "AccuracyScore",
            "FluencyScore",
            "CompletenessScore",
            "PronScore",
            "Words",
        ):
            payload["NBest"][0].pop(key, None)
        return SimpleNamespace(ok=True, status_code=200, json=lambda: payload)

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    result = azure.assess_with_azure_speech(b"wav")

    assert "Pronunciation-Assessment" not in captured["headers"]
    assert result.pronunciation is None


def test_unscripted_request_uses_pronunciation_header_without_reference(monkeypatch):
    captured = {}

    def fake_post(_url, *, headers, params, data, timeout):
        captured["headers"] = headers
        return SimpleNamespace(ok=True, status_code=200, json=_flat_response)

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    result = azure.assess_with_azure_speech(
        b"wav", enable_unscripted_assessment=True
    )

    assessment = json.loads(
        base64.b64decode(captured["headers"]["Pronunciation-Assessment"])
    )
    assert assessment == {
        "GradingSystem": "HundredMark",
        "Granularity": "Phoneme",
        "Dimension": "Comprehensive",
        "EnableProsodyAssessment": "True",
        "PhonemeAlphabet": "IPA",
        "NBestPhonemeCount": 5,
    }
    assert "ReferenceText" not in assessment
    assert result.pronunciation is not None


def test_unscripted_gate_can_disable_paid_prosody_add_on(monkeypatch):
    captured = {}

    def fake_post(_url, *, headers, params, data, timeout):
        captured["headers"] = headers
        return SimpleNamespace(ok=True, status_code=200, json=_flat_response)

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    azure.assess_with_azure_speech(
        b"wav",
        enable_unscripted_assessment=True,
        enable_prosody_assessment=False,
    )

    assessment = json.loads(
        base64.b64decode(captured["headers"]["Pronunciation-Assessment"])
    )
    assert "EnableProsodyAssessment" not in assessment


def test_azure_retries_missing_recognition_status_once(monkeypatch):
    payloads = iter(
        [
            {"error": "NBest[0] is missing PronunciationAssessment block"},
            _flat_response(),
        ]
    )
    request_count = 0

    def fake_post(_url, *, headers, params, data, timeout):
        nonlocal request_count
        request_count += 1
        payload = next(payloads)
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: payload,
        )

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    result = azure.assess_with_azure_speech(b"wav")

    assert request_count == 2
    assert result.request_count == 2
    assert result.recognition_status == "Success"
    assert result.retry_diagnostics == [
        {
            "reason": "missing_recognition_status",
            "response_keys": ["error"],
            "provider_error": (
                "NBest[0] is missing PronunciationAssessment block"
            ),
        }
    ]


def test_azure_stops_after_one_schema_retry(monkeypatch):
    request_count = 0

    def fake_post(_url, *, headers, params, data, timeout):
        nonlocal request_count
        request_count += 1
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {"error": "temporary malformed response"},
        )

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(azure.requests, "post", fake_post)

    with pytest.raises(azure.AzureSpeechError) as error:
        azure.assess_with_azure_speech(b"wav")

    assert request_count == 2
    assert error.value.code == "azure_schema_invalid"
    assert "after one automatic retry" in error.value.detail
    assert "temporary malformed response" in error.value.detail


def test_azure_requires_key_and_valid_region(monkeypatch):
    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", None)
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    with pytest.raises(azure.AzureSpeechError) as missing:
        azure.assess_with_azure_speech(b"wav")
    assert missing.value.code == "azure_not_configured"

    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "key")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "bad.example.com")
    with pytest.raises(azure.AzureSpeechError) as invalid:
        azure.assess_with_azure_speech(b"wav")
    assert invalid.value.code == "azure_region_invalid"


def test_azure_quota_error_uses_safe_stable_code(monkeypatch):
    monkeypatch.setattr(azure.Config, "AZURE_API_KEY", "azure-secret")
    monkeypatch.setattr(azure.Config, "AZURE_SPEECH_REGION", "southeastasia")
    monkeypatch.setattr(
        azure.requests,
        "post",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=False,
            status_code=429,
            json=lambda: {"error": {"message": "provider detail"}},
        ),
    )

    with pytest.raises(azure.AzureSpeechError) as error:
        azure.assess_with_azure_speech(b"wav")

    assert error.value.code == "azure_http_429"
    assert "provider detail" not in error.value.detail

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
    }

    result = azure.parse_azure_speech_response(payload, latency_ms=75)

    assert result.pronunciation.accuracy_score == 93
    assert result.pronunciation.words[0].accuracy_score == 77
    assert result.pronunciation.words[0].error_type == "None"


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

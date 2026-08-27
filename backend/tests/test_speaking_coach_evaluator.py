import json
from types import SimpleNamespace

import pytest

from app import speaking_coach_evaluator as evaluator
from app.speaking_coach_audio import AudioNormalizationError
from app.speaking_coach_azure import (
    AzurePronunciationAssessment,
    AzureSpeechResult,
    AzureTranscriptAlternative,
    AzureWordAssessment,
)


def _azure_result(
    *,
    transcript="She isn't going to work.",
    confidence=0.91,
    status="Success",
    pronunciation=True,
    words=None,
):
    assessment = None
    if pronunciation:
        assessment = AzurePronunciationAssessment(
            accuracy_score=92,
            fluency_score=88,
            completeness_score=100,
            pronunciation_score=91,
            words=words or [],
        )
    alternatives = []
    if transcript:
        alternatives = [
            AzureTranscriptAlternative(
                transcript=transcript,
                lexical=transcript.lower(),
                confidence=confidence,
            )
        ]
    return AzureSpeechResult(
        recognition_status=status,
        transcript=transcript,
        confidence=confidence,
        alternatives=alternatives,
        pronunciation=assessment,
        duration_100ns=20_000_000,
        snr=25,
        latency_ms=80,
        raw_payload={"RecognitionStatus": status},
    )


def _evaluate(monkeypatch, *, practice_type="pronunciation", azure=None):
    monkeypatch.setattr(
        evaluator,
        "normalize_speaking_audio",
        lambda *_args, **_kwargs: b"normalized wav",
    )
    monkeypatch.setattr(
        evaluator,
        "assess_with_azure_speech",
        lambda *_args, **_kwargs: azure or _azure_result(
            pronunciation=practice_type == "pronunciation"
        ),
    )
    monkeypatch.setattr(evaluator.Config, "AZURE_SPEECH_REGION", "southeastasia")
    return evaluator.evaluate_speaking_attempt(
        audio_bytes=b"m4a bytes",
        audio_mime_type="audio/mp4",
        practice_type=practice_type,
        focus="Check the contraction and final sounds.",
        prompt_en="She isn't going to work.",
        prompt_th="เธอไม่ได้กำลังไปทำงาน",
        target_answers=["She isn't going to work."],
        examples=[],
        instructional_attempt_number=1,
    )


def _language_output(*, material_error=False):
    issues = []
    retry_focus = []
    if material_error:
        issues = [
            {
                "category": "grammar",
                "description_en": "Use the -ing form after 'is'.",
                "description_th": "ใช้รูป -ing หลังคำว่า is",
            }
        ]
        retry_focus = ["present continuous -ing form"]
    return {
        "material_error": material_error,
        "content": {
            "meaning_correct": True,
            "relevant": True,
            "target_usage_correct": not material_error,
            "grammar_correct": not material_error,
        },
        "detected_issues": issues,
        "displayed_issues": issues,
        "corrected_answer": "She is going to work." if material_error else None,
        "feedback_en": "Use the -ing form." if material_error else "Good answer!",
        "feedback_th": "ใช้รูป -ing" if material_error else "ตอบได้ดี!",
        "retry_focus": retry_focus,
    }


def test_pronunciation_is_azure_only_and_transcript_mismatch_cannot_fail(monkeypatch):
    # The transcript drops "not", but acoustic assessment reports no supported issue.
    azure = _azure_result(transcript="She is going to work.")
    gemini_called = False

    def unexpected_gemini(**_kwargs):
        nonlocal gemini_called
        gemini_called = True

    monkeypatch.setattr(evaluator, "evaluate_language_with_gemini", unexpected_gemini)
    result = _evaluate(monkeypatch, azure=azure)

    assert result.evaluation.status == evaluator.EvaluationStatus.PASS
    assert result.evaluation.transcript == "She is going to work."
    assert result.provider == "microsoft"
    assert gemini_called is False


def test_pronunciation_reports_only_supported_word_issue(monkeypatch):
    azure = _azure_result(
        words=[
            AzureWordAssessment(
                word="isn't", accuracy_score=41, error_type="Mispronunciation"
            )
        ]
    )

    result = _evaluate(monkeypatch, azure=azure)

    assert result.evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(result.evaluation.displayed_issues) == 1
    assert result.evaluation.displayed_issues[0].category == "focus"
    assert "isn't" in result.evaluation.feedback_en


def test_pronunciation_preserves_azure_omission_meaning(monkeypatch):
    azure = _azure_result(
        transcript="She going to work.",
        words=[AzureWordAssessment(word="isn't", error_type="Omission")],
    )

    result = _evaluate(monkeypatch, azure=azure)

    issue = result.evaluation.displayed_issues[0]
    assert result.evaluation.status == evaluator.EvaluationStatus.RETRY
    assert "missing word" in issue.description_en
    assert "pronounced like" not in issue.description_en
    assert result.evaluation.content.target_usage_correct is False


def test_focus_phoneme_is_prioritized_before_severe_off_focus_word():
    azure = _azure_result(
        transcript="I’m eating lunch.",
        words=[
            AzureWordAssessment(
                word="i’m",
                accuracy_score=88,
                error_type="None",
                phonemes=[
                    {
                        "Phoneme": "aɪ",
                        "AccuracyScore": 33,
                        "NBestPhonemes": [
                            {"Phoneme": "aɪ", "Score": 100},
                            {"Phoneme": "ə", "Score": 20},
                        ],
                    },
                    {
                        "Phoneme": "m",
                        "AccuracyScore": 39,
                        "NBestPhonemes": [
                            {"Phoneme": "aɪ", "Score": 100},
                            {"Phoneme": "n", "Score": 41},
                        ],
                    },
                ],
                syllables=[{"Syllable": "aɪm", "AccuracyScore": 35}],
            ),
            AzureWordAssessment(
                word="eating",
                accuracy_score=97,
                error_type="None",
                phonemes=[
                    {"Phoneme": "i", "AccuracyScore": 89},
                    {"Phoneme": "t", "AccuracyScore": 94},
                    {"Phoneme": "ɪ", "AccuracyScore": 100},
                    {"Phoneme": "ŋ", "AccuracyScore": 100},
                ],
                syllables=[{"Syllable": "ɪŋ", "AccuracyScore": 100}],
            ),
            AzureWordAssessment(
                word="lunch",
                accuracy_score=41,
                error_type="Mispronunciation",
                phonemes=[
                    {"Phoneme": "l", "AccuracyScore": 100},
                    {"Phoneme": "ʌ", "AccuracyScore": 78},
                    {"Phoneme": "n", "AccuracyScore": 15},
                    {"Phoneme": "tʃ", "AccuracyScore": 0},
                ],
                syllables=[{"Syllable": "lʌntʃ", "AccuracyScore": 61}],
            ),
        ],
    )
    azure.pronunciation.completeness_score = 67

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="I’m eating lunch.",
        focus=(
            "Verify present continuous structure and clear linked contractions "
            "(I'm) and final -ing."
        ),
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 2
    assert evaluation.displayed_issues[0].category == "focus"
    assert "i’m" in evaluation.displayed_issues[0].description_en
    assert "lunch" in evaluation.displayed_issues[1].description_en
    assert "/" not in evaluation.displayed_issues[0].description_en
    assert "/" not in evaluation.displayed_issues[1].description_en
    assert evaluation.feedback_en == "Focus on these two parts, then try once more."
    problem_tokens = [
        token
        for token in evaluation.pronunciation.assessment_tokens
        if token.status != evaluator.AssessmentTokenStatus.CLEAR
    ]
    assert [(token.text, token.issue_index) for token in problem_tokens] == [
        ("I’m", 0),
        ("lunch", 1),
    ]


def test_moderately_low_focus_phoneme_requires_two_supporting_signals():
    azure = _azure_result(
        transcript="I’m eating.",
        words=[
            AzureWordAssessment(
                word="i’m",
                accuracy_score=88,
                error_type="None",
                phonemes=[
                    {"Phoneme": "aɪ", "AccuracyScore": 90},
                    {
                        "Phoneme": "m",
                        "AccuracyScore": 39,
                        "NBestPhonemes": [
                            {"Phoneme": "m", "Score": 100},
                            {"Phoneme": "n", "Score": 30},
                        ],
                    },
                ],
                syllables=[{"Syllable": "aɪm", "AccuracyScore": 80}],
            ),
            AzureWordAssessment(
                word="eating", accuracy_score=98, error_type="None"
            ),
        ],
    )
    azure.pronunciation.completeness_score = 100

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="I’m eating.",
        focus="Use the contraction I'm clearly.",
    )

    assert evaluation.status == evaluator.EvaluationStatus.PASS
    assert evaluation.displayed_issues == []


def test_low_confidence_open_answer_is_unclear_without_gemini(monkeypatch):
    azure = _azure_result(
        transcript="Maybe studying.", confidence=0.2, pronunciation=False
    )
    gemini_called = False

    def unexpected_gemini(**_kwargs):
        nonlocal gemini_called
        gemini_called = True

    monkeypatch.setattr(evaluator, "evaluate_language_with_gemini", unexpected_gemini)
    result = _evaluate(monkeypatch, practice_type="open", azure=azure)

    assert result.evaluation.status == evaluator.EvaluationStatus.UNCLEAR_AUDIO
    assert result.evaluation.transcript is None
    assert "confidently understand" in result.evaluation.feedback_en
    assert result.evaluation.detected_issues == []
    assert result.provider == "microsoft"
    assert gemini_called is False


def test_low_confidence_open_answer_can_report_supported_r_to_l_transfer(monkeypatch):
    azure = _azure_result(
        transcript="I'm Satani History.",
        confidence=0.102,
        words=[
            AzureWordAssessment(
                word="history",
                accuracy_score=48,
                error_type="Mispronunciation",
                phonemes=[
                    {
                        "Phoneme": "ɹ",
                        "PronunciationAssessment": {
                            "AccuracyScore": 28,
                            "NBestPhonemes": [
                                {"Phoneme": "l", "Score": 92},
                                {"Phoneme": "ɹ", "Score": 25},
                            ],
                        },
                    }
                ],
            )
        ],
    )
    gemini_called = False

    def unexpected_gemini(**_kwargs):
        nonlocal gemini_called
        gemini_called = True

    monkeypatch.setattr(evaluator, "evaluate_language_with_gemini", unexpected_gemini)
    result = _evaluate(monkeypatch, practice_type="open", azure=azure)

    assert result.evaluation.status == evaluator.EvaluationStatus.RETRY
    assert result.evaluation.transcript is None
    assert result.evaluation.displayed_issues[0].category == "pronunciation"
    assert "history" in result.evaluation.feedback_en
    assert "/" not in result.evaluation.feedback_en
    assert result.evaluation.pronunciation.issues
    policy = result.provider_metadata["policy"]
    assert policy["catalog_version"] == "thai-english-pronunciation-v2"
    assert policy["matches"][0]["pattern_id"] == "r_l_confusion"
    assert policy["matches"][0]["evidence_score"] >= 55
    assert gemini_called is False


def test_open_requests_unscripted_assessment_in_the_existing_azure_call(monkeypatch):
    captured = {}
    azure = _azure_result(pronunciation=True)
    azure.pronunciation.prosody_score = 78
    language = evaluator.LanguageEvaluation.model_validate(_language_output())

    monkeypatch.setattr(
        evaluator,
        "normalize_speaking_audio",
        lambda *_args, **_kwargs: b"normalized wav",
    )

    def fake_azure(*_args, **kwargs):
        captured.update(kwargs)
        return azure

    monkeypatch.setattr(evaluator, "assess_with_azure_speech", fake_azure)
    monkeypatch.setattr(
        evaluator,
        "evaluate_language_with_gemini",
        lambda **_kwargs: evaluator.GeminiLanguageResult(
            evaluation=language,
            model="gemini-3.5-flash-lite",
            latency_ms=30,
            usage={},
            provider_metadata={},
            provider_output_text=language.model_dump_json(),
        ),
    )

    result = evaluator.evaluate_speaking_attempt(
        audio_bytes=b"m4a bytes",
        audio_mime_type="audio/mp4",
        practice_type="open",
        focus="Speak clearly.",
        prompt_en="What are you studying?",
        prompt_th=None,
        target_answers=[],
        examples=[],
        instructional_attempt_number=1,
    )

    assert captured["reference_text"] is None
    assert captured["enable_unscripted_assessment"] is True
    assert result.evaluation.transcript is None
    assert result.provider_metadata["azure"]["response"] == azure.raw_payload
    assert result.provider_metadata["policy"]["prosody"] == {
        "enabled": True,
        "score": 78,
        "learner_feedback_enabled": False,
    }


def test_non_open_language_evaluation_retains_transcript():
    azure = _azure_result(transcript="She is going to work.", pronunciation=False)
    language = evaluator.LanguageEvaluation.model_validate(_language_output())

    evaluation = evaluator._compose_language_evaluation(azure, language)

    assert evaluation.transcript == "She is going to work."


def test_high_confidence_open_answer_combines_language_and_acoustic_results():
    azure = _azure_result(
        transcript="I'm studying history.",
        confidence=0.88,
        words=[
            AzureWordAssessment(
                word="history",
                accuracy_score=50,
                error_type="Mispronunciation",
                phonemes=[
                    {
                        "Phoneme": "r",
                        "AccuracyScore": 31,
                        "NBestPhonemes": [
                            {"Phoneme": "l", "Score": 90},
                            {"Phoneme": "r", "Score": 29},
                        ],
                    }
                ],
            )
        ],
    )
    language = evaluator.LanguageEvaluation.model_validate(_language_output())
    candidates = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus="Use clear /r/ and /l/ sounds.",
        evaluation_context={
            "prompt_en": "What are you studying?",
            "focus": "Use clear /r/ and /l/ sounds.",
            "target_answers": [],
            "examples": [],
        },
    )

    evaluation = evaluator._compose_language_evaluation(
        azure,
        language,
        pronunciation_candidates=candidates,
        include_transcript=False,
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert evaluation.transcript is None
    assert evaluation.content.meaning_correct is True
    assert evaluation.displayed_issues[0].category == "focus"
    assert "history" in evaluation.feedback_en
    assert "/" not in evaluation.feedback_en


def test_open_detects_final_sh_replaced_by_t_like_stop():
    azure = _azure_result(
        transcript="I caught a fish.",
        confidence=0.86,
        words=[
            AzureWordAssessment(
                word="fish",
                accuracy_score=51,
                error_type="Mispronunciation",
                phonemes=[
                    {"Phoneme": "f", "AccuracyScore": 92},
                    {"Phoneme": "ɪ", "AccuracyScore": 88},
                    {
                        "Phoneme": "ʃ",
                        "AccuracyScore": 24,
                        "NBestPhonemes": [
                            {"Phoneme": "t", "Score": 96},
                            {"Phoneme": "ʃ", "Score": 21},
                        ],
                    },
                ],
            )
        ],
    )

    candidates = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus="Answer in a complete sentence.",
        evaluation_context={
            "prompt_en": "What did you catch?",
            "focus": "Answer in a complete sentence.",
            "target_answers": [],
            "examples": [],
        },
    )

    assert candidates[0].pattern_id == "final_sh_to_stop"
    assert candidates[0].evidence["expected_phoneme"] == "ʃ"
    assert candidates[0].evidence["leading_spoken_phoneme"] == "t"
    assert "ending" in candidates[0].issue.description_en


def test_open_detects_present_continuous_cluster_epenthesis_and_final_sound():
    azure = _azure_result(
        transcript="I said buddy English.",
        confidence=0.668,
        words=[
            AzureWordAssessment(
                word="said",
                accuracy_score=97,
                error_type="None",
                phonemes=[
                    {
                        "Phoneme": "s",
                        "AccuracyScore": 84,
                        "NBestPhonemes": [{"Phoneme": "s", "Score": 100}],
                    },
                    {
                        "Phoneme": "ɛ",
                        "AccuracyScore": 80,
                        "NBestPhonemes": [{"Phoneme": "æ", "Score": 100}],
                    },
                    {
                        "Phoneme": "d",
                        "AccuracyScore": 46,
                        "NBestPhonemes": [{"Phoneme": "t", "Score": 100}],
                    },
                ],
            ),
            AzureWordAssessment(
                word="buddy", accuracy_score=88, error_type="None"
            ),
            AzureWordAssessment(
                word="english",
                accuracy_score=60,
                error_type="None",
                phonemes=[
                    {"Phoneme": "ɪ", "AccuracyScore": 100},
                    {
                        "Phoneme": "ʃ",
                        "AccuracyScore": 24,
                        "NBestPhonemes": [
                            {"Phoneme": "d", "Score": 97},
                            {"Phoneme": "t", "Score": 92},
                        ],
                    },
                ],
            ),
        ],
    )
    context = {
        "prompt_en": "What are you studying?",
        "focus": "Use present continuous tense in your answer.",
        "target_answers": [],
        "examples": [{"en": "I'm studying Thai."}],
    }
    pronunciation = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus=context["focus"],
        evaluation_context=context,
    )
    focus_issues = evaluator._focus_validation_issues(
        azure, focus=context["focus"]
    )
    language = evaluator.LanguageEvaluation.model_validate(
        _language_output(material_error=True)
    )

    evaluation = evaluator._compose_language_evaluation(
        azure,
        language,
        pronunciation_candidates=pronunciation,
        focus_issues=focus_issues,
        include_transcript=False,
    )

    descriptions = [issue.description_en for issue in evaluation.displayed_issues]
    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert evaluation.transcript is None
    assert evaluation.content.target_usage_correct is False
    assert len(descriptions) == 3
    assert sum(
        "am/is/are" in description or "present continuous" in description.lower()
        for description in descriptions
    ) == 1
    assert sum(
        "present continuous" in retry.lower() or "am/is/are" in retry
        for retry in evaluation.retry_focus
    ) == 1
    assert any("am/is/are" in description for description in descriptions)
    assert any("smoothly" in description for description in descriptions)
    assert any(
        "english" in description.lower() and "ending" in description
        for description in descriptions
    )
    assert all("/" not in description for description in descriptions[1:])
    diagnostics = evaluator._pronunciation_policy_metadata(
        pronunciation, focus_issues=focus_issues
    )
    assert [match["pattern_id"] for match in diagnostics["matches"]] == [
        "cluster_epenthesis",
        "non_native_consonant_mapping",
    ]
    assert diagnostics["prosody"] == {
        "enabled": True,
        "score": None,
        "learner_feedback_enabled": False,
    }
    assert all(match["evidence_score"] >= 55 for match in diagnostics["matches"])


def test_present_continuous_focus_accepts_recognized_be_plus_ing():
    azure = _azure_result(
        transcript="I'm studying English.", confidence=0.9, pronunciation=True
    )

    issues = evaluator._focus_validation_issues(
        azure, focus="Use present continuous tense in your answer."
    )

    assert issues == []


def test_open_answer_routes_azure_text_to_gemini_and_backend_derives_status(monkeypatch):
    azure = _azure_result(
        transcript="She go to work.", confidence=0.86, pronunciation=False
    )
    language = evaluator.LanguageEvaluation.model_validate(
        _language_output(material_error=True)
    )
    captured = {}

    def fake_language(**kwargs):
        captured.update(kwargs)
        return evaluator.GeminiLanguageResult(
            evaluation=language,
            model="gemini-3.5-flash-lite",
            latency_ms=30,
            usage={"total_tokens": 20},
            provider_metadata={"id": "interaction-1"},
            provider_output_text=language.model_dump_json(),
        )

    monkeypatch.setattr(evaluator, "evaluate_language_with_gemini", fake_language)
    result = _evaluate(monkeypatch, practice_type="open", azure=azure)

    assert captured["azure"] is azure
    assert result.evaluation.status == evaluator.EvaluationStatus.RETRY
    assert result.evaluation.pronunciation.issues == []
    assert result.provider == "microsoft+google"
    assert set(result.provider_metadata) == {"azure", "gemini", "policy"}
    assert set(result.usage) == {"azure", "gemini"}


def test_text_only_gemini_request_contains_no_audio(monkeypatch):
    captured = {}
    azure = _azure_result(pronunciation=False)

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, payload=json, timeout=timeout)
        output = json_module.dumps(_language_output())
        return SimpleNamespace(
            ok=True,
            status_code=200,
            json=lambda: {
                "id": "interaction-1",
                "steps": [
                    {"type": "model_output", "content": [{"text": output}]}
                ],
                "usage": {"total_tokens": 10},
            },
        )

    json_module = json
    monkeypatch.setattr(evaluator.Config, "GEMINI_API_KEY", "secret-key")
    monkeypatch.setattr(evaluator.requests, "post", fake_post)
    result = evaluator.evaluate_language_with_gemini(
        azure=azure,
        evaluation_context={"practice_type": "open", "focus": "private"},
        instructional_attempt_number=1,
    )

    assert result.evaluation.material_error is False
    assert len(captured["payload"]["input"]) == 1
    assert captured["payload"]["input"][0]["type"] == "text"
    assert "audio" not in json.dumps(captured["payload"]["input"]).lower()
    assert "secret-key" not in json.dumps(captured["payload"])


def test_text_evaluator_rejects_pronunciation_claims():
    payload = _language_output(material_error=True)
    payload["detected_issues"][0]["category"] = "pronunciation"
    payload["displayed_issues"][0]["category"] = "pronunciation"

    with pytest.raises(ValueError):
        evaluator.LanguageEvaluation.model_validate(payload)


def test_audio_normalization_failure_has_stable_code(monkeypatch):
    def fail_normalization(*_args, **_kwargs):
        raise AudioNormalizationError("audio_invalid", "bad input")

    monkeypatch.setattr(evaluator, "normalize_speaking_audio", fail_normalization)

    with pytest.raises(evaluator.EvaluatorError) as error:
        evaluator.evaluate_speaking_attempt(
            audio_bytes=b"bad",
            audio_mime_type="audio/mp4",
            practice_type="open",
            focus="",
            prompt_en="Question?",
            prompt_th=None,
            target_answers=[],
            examples=[],
            instructional_attempt_number=1,
        )

    assert error.value.code == "audio_invalid"


def test_follow_up_retry_is_not_forced_to_final_correction():
    evaluation = evaluator.SpeakingEvaluation(
        status="retry",
        transcript="She go.",
        content=evaluator.ContentEvaluation(grammar_correct=False),
        pronunciation=evaluator.PronunciationEvaluation(intelligible=True),
        feedback_en="Try again.",
        feedback_th="ลองอีกครั้ง",
        retry_focus=["Use goes."],
    )

    normalized = evaluator._normalize_attempt_status(evaluation, 2)

    assert normalized.status == evaluator.EvaluationStatus.RETRY
    assert normalized.retry_focus == ["Use goes."]

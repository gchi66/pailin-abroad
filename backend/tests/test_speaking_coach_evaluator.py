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


def _sleeping_cluster_result(
    *,
    consonant_accuracy: float = 34,
    word_accuracy: float = 73,
    syllable_accuracy: float = 62,
    segment_duration: int = 2_500_000,
    vowel_leads: bool = True,
    vowel_candidate_score: float = 93,
    vowel_candidate_phoneme: str = "ɑ",
    leading_consonant_score: float = 95,
    rhotic_accuracy: float = 61,
    rhotic_word_accuracy: float = 91,
    rhotic_syllable_accuracy: float = 61,
    rhotic_error_type: str = "None",
):
    return _azure_result(
        transcript="Are they sleeping now?",
        confidence=0.957,
        words=[
            AzureWordAssessment(
                word="are",
                accuracy_score=rhotic_word_accuracy,
                error_type=rhotic_error_type,
                phonemes=[
                    {
                        "Phoneme": "ɑɹ",
                        "AccuracyScore": rhotic_accuracy,
                        "NBestPhonemes": [
                            {"Phoneme": "ɑ", "Score": 98},
                            {"Phoneme": "oʊ", "Score": 57},
                        ],
                    }
                ],
                syllables=[
                    {
                        "Syllable": "ɑɹ",
                        "AccuracyScore": rhotic_syllable_accuracy,
                    }
                ],
            ),
            AzureWordAssessment(word="they", accuracy_score=97),
            AzureWordAssessment(
                word="sleeping",
                accuracy_score=word_accuracy,
                phonemes=[
                    {"Phoneme": "s", "AccuracyScore": 87},
                    {
                        "Phoneme": "l",
                        "AccuracyScore": consonant_accuracy,
                        "Duration": segment_duration,
                        "NBestPhonemes": [
                            *(
                                [
                                    {
                                        "Phoneme": "æ",
                                        "Score": vowel_candidate_score,
                                    },
                                    {"Phoneme": "l", "Score": 92},
                                ]
                                if vowel_leads
                                else [
                                    {
                                        "Phoneme": "l",
                                        "Score": leading_consonant_score,
                                    },
                                    {
                                        "Phoneme": vowel_candidate_phoneme,
                                        "Score": vowel_candidate_score,
                                    },
                                ]
                            ),
                            {"Phoneme": "ə", "Score": 46},
                        ],
                    },
                    {"Phoneme": "i", "AccuracyScore": 100},
                    {"Phoneme": "p", "AccuracyScore": 100},
                    {"Phoneme": "ɪ", "AccuracyScore": 100},
                    {"Phoneme": "ŋ", "AccuracyScore": 100},
                ],
                syllables=[
                    {
                        "Syllable": "sli",
                        "AccuracyScore": syllable_accuracy,
                    },
                    {"Syllable": "pɪŋ", "AccuracyScore": 100},
                ],
            ),
            AzureWordAssessment(word="now", accuracy_score=97),
        ],
    )


def _studying_artifact_result(*, inserted_vowel_duration: int = 500_000):
    return _azure_result(
        transcript="I'm sad studying English.",
        confidence=0.858,
        words=[
            AzureWordAssessment(word="i'm", accuracy_score=97),
            AzureWordAssessment(
                word="sad",
                accuracy_score=94,
                phonemes=[
                    {
                        "Phoneme": "s",
                        "AccuracyScore": 100,
                        "Duration": 1_100_000,
                        "NBestPhonemes": [{"Phoneme": "s", "Score": 100}],
                    },
                    {
                        "Phoneme": "æ",
                        "AccuracyScore": 65,
                        "Duration": inserted_vowel_duration,
                        "NBestPhonemes": [{"Phoneme": "æ", "Score": 100}],
                    },
                    {
                        "Phoneme": "d",
                        "AccuracyScore": 45,
                        "Duration": 400_000,
                        "NBestPhonemes": [
                            {"Phoneme": "t", "Score": 100},
                            {"Phoneme": "d", "Score": 98},
                        ],
                    },
                ],
                syllables=[{"Syllable": "sæd", "AccuracyScore": 79}],
            ),
            AzureWordAssessment(
                word="studying",
                accuracy_score=46,
                error_type="Mispronunciation",
                phonemes=[
                    {
                        "Phoneme": "s",
                        "AccuracyScore": 0,
                        "Duration": 200_000,
                        "NBestPhonemes": [{"Phoneme": "t", "Score": 100}],
                    },
                    {
                        "Phoneme": "t",
                        "AccuracyScore": 25,
                        "Duration": 700_000,
                        "NBestPhonemes": [
                            {"Phoneme": "t", "Score": 100},
                            {"Phoneme": "ə", "Score": 53},
                        ],
                    },
                ],
                syllables=[{"Syllable": "stʌd", "AccuracyScore": 55}],
            ),
            AzureWordAssessment(word="english", accuracy_score=97),
        ],
    )


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


def test_scripted_s_cluster_epenthesis_uses_catalog_evidence():
    azure = _sleeping_cluster_result()
    grammar_focus = (
        "Check that the response directly answers the question using the present "
        "continuous tense (Subject + am/is/are + verb-ing)."
    )
    candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus=grammar_focus
    )

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="Are they sleeping now?",
        focus=grammar_focus,
        catalog_candidates=candidates,
    )

    assert len(candidates) == 1
    assert candidates[0].pattern_id == "cluster_epenthesis"
    assert candidates[0].focus_match is False
    assert candidates[0].evidence["word"] == "sleeping"
    assert candidates[0].evidence["expected_cluster"] == ["s", "l"]
    assert candidates[0].evidence["leading_spoken_phoneme"] == "æ"
    assert candidates[0].evidence_score >= 80
    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 1
    assert "sleeping" in evaluation.displayed_issues[0].description_en
    assert all(
        "are" not in issue.description_en.lower()
        for issue in evaluation.detected_issues
    )


def test_second_scripted_coaching_attempt_passes_after_meaningful_improvement():
    first_azure = _sleeping_cluster_result()
    first_candidates = evaluator._s_cluster_epenthesis_candidates(
        first_azure, focus="Speak clearly."
    )
    first_policy = evaluator._pronunciation_policy_metadata(
        first_candidates, focus_issues=[]
    )
    second_azure = _sleeping_cluster_result(
        consonant_accuracy=42,
        word_accuracy=78,
        syllable_accuracy=63,
        segment_duration=1_600_000,
        vowel_leads=False,
        vowel_candidate_score=69,
    )
    second_candidates = evaluator._s_cluster_epenthesis_candidates(
        second_azure, focus="Speak clearly."
    )

    evaluation = evaluator._pronunciation_evaluation(
        second_azure,
        reference_text="Are they sleeping now?",
        focus="Speak clearly.",
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": first_policy},
        catalog_candidates=second_candidates,
    )

    assert second_candidates[0].evidence_score <= (
        first_candidates[0].evidence_score
        - evaluator.COACHING_IMPROVEMENT_EVIDENCE_DELTA
    )
    assert evaluation.status == evaluator.EvaluationStatus.PASS
    assert evaluation.displayed_issues == []
    assert "improvement" in evaluation.feedback_en


def test_second_scripted_coaching_attempt_moves_on_without_improvement():
    azure = _sleeping_cluster_result()
    first_candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Speak clearly."
    )
    first_policy = evaluator._pronunciation_policy_metadata(
        first_candidates, focus_issues=[]
    )
    second_candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Speak clearly."
    )

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="Are they sleeping now?",
        focus="Speak clearly.",
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": first_policy},
        catalog_candidates=second_candidates,
    )

    assert evaluation.status == evaluator.EvaluationStatus.CONTINUE_WITH_CORRECTION
    assert evaluation.corrected_answer == "Are they sleeping now?"
    assert "sleeping" in evaluation.displayed_issues[0].description_en
    assert evaluation.retry_focus == []


def test_strong_secondary_vowel_and_rhotic_deletion_are_both_detected():
    azure = _sleeping_cluster_result(
        consonant_accuracy=38,
        word_accuracy=88,
        syllable_accuracy=58,
        segment_duration=2_100_000,
        vowel_leads=False,
        vowel_candidate_score=69,
        rhotic_accuracy=32,
        rhotic_word_accuracy=69,
        rhotic_syllable_accuracy=32,
    )
    grammar_focus = (
        "Check the present continuous tense (Subject + am/is/are + verb-ing) "
        "and allow natural contractions."
    )
    candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus=grammar_focus
    ) + evaluator._rhotic_vowel_deletion_candidates(
        azure, focus=grammar_focus
    )

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="Are they sleeping now?",
        focus=grammar_focus,
        catalog_candidates=candidates,
    )

    assert [candidate.pattern_id for candidate in candidates] == [
        "cluster_epenthesis",
        "r_l_confusion",
    ]
    assert all(candidate.focus_match is False for candidate in candidates)
    assert candidates[0].evidence["vowel_is_leading"] is False
    assert candidates[0].evidence["vowel_candidate_score"] == 69
    assert candidates[1].evidence["transfer_type"] == (
        "post_vocalic_r_deletion"
    )
    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 2
    descriptions = [
        issue.description_en.lower() for issue in evaluation.displayed_issues
    ]
    assert any("sleeping" in description for description in descriptions)
    assert any("'are'" in description for description in descriptions)


def test_very_strong_secondary_vowel_allows_moderate_cluster_consonant_score():
    azure = _sleeping_cluster_result(
        consonant_accuracy=50,
        word_accuracy=88,
        syllable_accuracy=65,
        segment_duration=2_500_000,
        vowel_leads=False,
        vowel_candidate_score=92,
        vowel_candidate_phoneme="ə",
    )

    candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Use present continuous tense."
    )

    assert len(candidates) == 1
    assert candidates[0].pattern_id == "cluster_epenthesis"
    assert candidates[0].evidence["expected_consonant_accuracy"] == 50
    assert candidates[0].evidence["vowel_candidate_score"] == 92
    assert candidates[0].evidence["vowel_candidate"] == "ə"
    assert candidates[0].evidence["strong_secondary_vowel_exception"] is True
    assert candidates[0].evidence["support"] == {
        "word_accuracy": False,
        "syllable_accuracy": True,
        "segment_duration": True,
    }


def test_current_are_evidence_uses_specific_rhotic_catalog_finding():
    azure = _sleeping_cluster_result(
        rhotic_accuracy=34,
        rhotic_word_accuracy=79,
        rhotic_syllable_accuracy=34,
    )

    candidates = evaluator._rhotic_vowel_deletion_candidates(
        azure, focus="Use present continuous tense."
    )

    assert len(candidates) == 1
    assert candidates[0].pattern_id == "r_l_confusion"
    assert candidates[0].evidence_score >= (
        evaluator.RHOTIC_VOWEL_MIN_EVIDENCE_SCORE
    )
    assert "clear r sound" in candidates[0].issue.description_en


@pytest.mark.parametrize(
    ("word", "expected_phoneme", "spoken_phoneme"),
    [("your", "ʊɹ", "u"), ("four", "ɔɹ", "ɔ")],
)
def test_strong_final_r_mismatch_overrides_misleading_word_score(
    word, expected_phoneme, spoken_phoneme
):
    azure = _azure_result(
        transcript=word,
        words=[
            AzureWordAssessment(
                word=word,
                accuracy_score=94,
                error_type="None",
                phonemes=[
                    {
                        "Phoneme": expected_phoneme,
                        "AccuracyScore": 82,
                        "NBestPhonemes": [
                            {"Phoneme": spoken_phoneme, "Score": 100},
                            {"Phoneme": "n", "Score": 40},
                        ],
                    }
                ],
                syllables=[
                    {"Syllable": expected_phoneme, "AccuracyScore": 85}
                ],
            )
        ],
    )

    candidates = evaluator._rhotic_vowel_deletion_candidates(
        azure, focus="Check another primary pronunciation point."
    )

    assert len(candidates) == 1
    assert candidates[0].pattern_id == "r_l_confusion"
    assert candidates[0].focus_match is False
    assert candidates[0].evidence["strong_final_r_mismatch"] is True
    assert candidates[0].evidence_score >= 90


def test_scripted_evaluation_displays_focus_and_final_r_fallback_together():
    azure = _azure_result(
        transcript="What’s your name?",
        words=[
            AzureWordAssessment(
                word="what’s",
                accuracy_score=91,
                error_type="None",
                phonemes=[
                    {"Phoneme": "w", "AccuracyScore": 87},
                    {"Phoneme": "ʌ", "AccuracyScore": 100},
                    {"Phoneme": "t", "AccuracyScore": 10},
                    {
                        "Phoneme": "s",
                        "AccuracyScore": 0,
                        "NBestPhonemes": [{"Phoneme": "t", "Score": 100}],
                    },
                ],
                syllables=[{"Syllable": "wʌts", "AccuracyScore": 71}],
            ),
            AzureWordAssessment(
                word="your",
                accuracy_score=94,
                error_type="None",
                phonemes=[
                    {"Phoneme": "j", "AccuracyScore": 92},
                    {
                        "Phoneme": "ʊɹ",
                        "AccuracyScore": 82,
                        "NBestPhonemes": [
                            {"Phoneme": "u", "Score": 100},
                            {"Phoneme": "n", "Score": 56},
                        ],
                    },
                ],
                syllables=[{"Syllable": "jʊɹ", "AccuracyScore": 85}],
            ),
            AzureWordAssessment(word="name", accuracy_score=97),
        ],
    )
    focus = "Check that the final -s in ‘What’s’ is pronounced."
    catalog_candidates = evaluator._rhotic_vowel_deletion_candidates(
        azure, focus=focus
    )

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="What’s your name?",
        focus=focus,
        catalog_candidates=catalog_candidates,
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 2
    descriptions = [
        issue.description_en.lower() for issue in evaluation.displayed_issues
    ]
    assert "what’s" in descriptions[0]
    assert any("'your'" in description for description in descriptions)


def test_strong_final_consonant_mismatch_can_be_off_focus_fallback():
    azure = _azure_result(
        transcript="cat",
        words=[
            AzureWordAssessment(
                word="cat",
                accuracy_score=95,
                error_type="None",
                phonemes=[
                    {"Phoneme": "k", "AccuracyScore": 100},
                    {"Phoneme": "æ", "AccuracyScore": 100},
                    {
                        "Phoneme": "t",
                        "AccuracyScore": 0,
                        "NBestPhonemes": [
                            {"Phoneme": "k", "Score": 100},
                            {"Phoneme": "t", "Score": 0},
                        ],
                    },
                ],
                syllables=[{"Syllable": "kæt", "AccuracyScore": 90}],
            )
        ],
    )

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="cat",
        focus="Check another primary pronunciation point.",
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 1
    assert evaluation.displayed_issues[0].category == "pronunciation"
    assert "ending" in evaluation.displayed_issues[0].description_en


def _meet_to_miss_result(
    *, leading_score: float = 100, expected_candidate_score: float = 19
) -> AzureSpeechResult:
    return _azure_result(
        transcript="It’s nice to meet you.",
        words=[
            AzureWordAssessment(word="it’s", accuracy_score=98),
            AzureWordAssessment(word="nice", accuracy_score=100),
            AzureWordAssessment(word="to", accuracy_score=100),
            AzureWordAssessment(
                word="meet",
                accuracy_score=97,
                error_type="None",
                phonemes=[
                    {"Phoneme": "m", "AccuracyScore": 100},
                    {"Phoneme": "i", "AccuracyScore": 72},
                    {
                        "Phoneme": "t",
                        "AccuracyScore": 32,
                        "NBestPhonemes": [
                            {"Phoneme": "s", "Score": leading_score},
                            {
                                "Phoneme": "t",
                                "Score": expected_candidate_score,
                            },
                        ],
                    },
                ],
                syllables=[{"Syllable": "mit", "AccuracyScore": 66}],
            ),
            AzureWordAssessment(word="you", accuracy_score=97),
        ],
    )


def test_strong_local_nbest_mismatch_catches_meet_to_miss_without_focus():
    azure = _meet_to_miss_result()

    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="It’s nice to meet you!",
        focus="In ‘It’s,’ check that the final /s/ is pronounced.",
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 1
    assert evaluation.displayed_issues[0].category == "pronunciation"
    assert "meet" in evaluation.displayed_issues[0].description_en.lower()


@pytest.mark.parametrize(
    ("leading_score", "expected_candidate_score"),
    [(89, 19), (100, 75)],
)
def test_local_nbest_mismatch_requires_high_score_and_wide_margin(
    leading_score, expected_candidate_score
):
    evaluation = evaluator._pronunciation_evaluation(
        _meet_to_miss_result(
            leading_score=leading_score,
            expected_candidate_score=expected_candidate_score,
        ),
        reference_text="It’s nice to meet you!",
        focus="In ‘It’s,’ check that the final /s/ is pronounced.",
    )

    assert evaluation.status == evaluator.EvaluationStatus.PASS
    assert evaluation.displayed_issues == []


def _truncated_nice_result() -> AzureSpeechResult:
    return _azure_result(
        transcript="It’s nice to meet you.",
        words=[
            AzureWordAssessment(word="it’s", accuracy_score=94),
            AzureWordAssessment(
                word="nice",
                accuracy_score=76,
                error_type="None",
                phonemes=[
                    {"Phoneme": "n", "AccuracyScore": 100},
                    {"Phoneme": "aɪ", "AccuracyScore": 63},
                    {
                        "Phoneme": "s",
                        "AccuracyScore": 23,
                        "NBestPhonemes": [
                            {"Phoneme": "t", "Score": 100},
                            {"Phoneme": "n", "Score": 93},
                            {"Phoneme": "aɪ", "Score": 58},
                            {"Phoneme": "i", "Score": 26},
                            {"Phoneme": "eɪ", "Score": 20},
                        ],
                    },
                ],
                syllables=[{"Syllable": "naɪs", "AccuracyScore": 66}],
            ),
            AzureWordAssessment(word="to", accuracy_score=100),
            AzureWordAssessment(word="meet", accuracy_score=100),
            AzureWordAssessment(word="you", accuracy_score=97),
        ],
    )


def test_expected_phoneme_missing_from_full_nbest_is_strong_local_mismatch():
    candidates = []
    evaluation = evaluator._pronunciation_evaluation(
        _truncated_nice_result(),
        reference_text="It’s nice to meet you!",
        focus="In ‘nice,’ check that the final /s/ is pronounced.",
        catalog_candidates=candidates,
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert "nice" in evaluation.displayed_issues[0].description_en.lower()
    assert candidates[0].evidence["local_mismatch"] == {
        "leading_phoneme": "t",
        "leading_score": 100.0,
        "expected_candidate_score": None,
        "expected_candidate_missing": True,
        "score_margin": None,
    }


def test_second_attempt_does_not_hide_new_issue_after_prior_issue_resolves():
    previous_issue = evaluator.EvaluationIssue(
        category="focus",
        description_en="Say 'meet' again, focusing on the ending.",
        description_th="ลองพูดคำว่า 'meet' อีกครั้ง โดยเน้นเสียงท้ายคำ",
    )
    previous_candidate = evaluator._PronunciationCandidate(
        word_index=3,
        focus_match=True,
        severity=90,
        status=evaluator.AssessmentTokenStatus.NEEDS_WORK,
        issue=previous_issue,
        evidence_score=66,
        priority_score=81,
        evidence={"word": "meet", "expected_phoneme": "t"},
    )
    previous_policy = evaluator._pronunciation_policy_metadata(
        [previous_candidate], focus_issues=[]
    )
    current_candidates = []

    evaluation = evaluator._pronunciation_evaluation(
        _truncated_nice_result(),
        reference_text="It’s nice to meet you!",
        focus="In ‘nice,’ check that the final /s/ is pronounced.",
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": previous_policy},
        catalog_candidates=current_candidates,
    )
    policy = evaluator._coaching_attempt_policy(
        current_candidates,
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": previous_policy},
    )

    assert policy["resolved_issue_keys"] == ["generic:meet:t"]
    assert policy["new_issue_keys"] == ["generic:nice:s"]
    assert policy["meaningful_improvement"] is True
    assert evaluation.status == evaluator.EvaluationStatus.CONTINUE_WITH_CORRECTION
    assert "nice" in evaluation.displayed_issues[0].description_en.lower()
    assert "move on" in evaluation.feedback_en.lower()


def test_ultra_strong_schwa_catches_latest_sleeping_evidence_shape():
    azure = _sleeping_cluster_result(
        consonant_accuracy=60,
        word_accuracy=91,
        syllable_accuracy=72,
        segment_duration=2_100_000,
        vowel_leads=False,
        vowel_candidate_score=93,
        vowel_candidate_phoneme="ə",
        leading_consonant_score=100,
    )

    candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Use present continuous tense."
    )

    assert len(candidates) == 1
    evidence = candidates[0].evidence
    assert evidence["support"] == {
        "word_accuracy": False,
        "syllable_accuracy": False,
        "segment_duration": True,
    }
    assert evidence["leading_spoken_phoneme_score"] == 100
    assert evidence["vowel_candidate"] == "ə"
    assert evidence["vowel_candidate_score"] == 93
    assert evidence["ultra_strong_central_vowel"] is True


def test_ultra_strong_schwa_still_requires_long_segment():
    azure = _sleeping_cluster_result(
        consonant_accuracy=60,
        word_accuracy=91,
        syllable_accuracy=72,
        segment_duration=1_900_000,
        vowel_leads=False,
        vowel_candidate_score=93,
        vowel_candidate_phoneme="ə",
        leading_consonant_score=100,
    )

    assert evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Use present continuous tense."
    ) == []


def test_moderate_cluster_consonant_score_still_requires_very_strong_vowel():
    azure = _sleeping_cluster_result(
        consonant_accuracy=50,
        word_accuracy=88,
        syllable_accuracy=65,
        segment_duration=2_500_000,
        vowel_leads=False,
        vowel_candidate_score=79,
    )

    assert evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Use present continuous tense."
    ) == []


def test_catalog_specific_findings_replace_generic_findings_for_same_word():
    azure = _sleeping_cluster_result(
        consonant_accuracy=50,
        word_accuracy=88,
        syllable_accuracy=65,
        segment_duration=2_500_000,
        vowel_leads=False,
        vowel_candidate_score=92,
        rhotic_accuracy=29,
        rhotic_word_accuracy=79,
        rhotic_syllable_accuracy=34,
        rhotic_error_type="Mispronunciation",
    )

    candidates = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus="Use present continuous tense.",
        evaluation_context={
            "prompt_en": "Are they sleeping now?",
            "focus": "Use present continuous tense.",
            "target_answers": [],
            "examples": [],
        },
    )

    assert {candidate.pattern_id for candidate in candidates} == {
        "cluster_epenthesis",
        "r_l_confusion",
    }
    assert all(candidate.pattern_id is not None for candidate in candidates)


def test_invalid_empty_previous_evidence_cannot_create_false_improvement():
    azure = _sleeping_cluster_result(
        consonant_accuracy=38,
        word_accuracy=88,
        syllable_accuracy=58,
        segment_duration=2_100_000,
        vowel_leads=False,
        vowel_candidate_score=69,
    )
    candidates = evaluator._s_cluster_epenthesis_candidates(
        azure, focus="Use present continuous tense."
    )
    invalid_previous = {
        "_provider_policy": {
            "matches": [
                {
                    "pattern_id": None,
                    "evidence_score": 0,
                    "evidence": {},
                }
            ]
        }
    }

    policy = evaluator._coaching_attempt_policy(
        candidates,
        instructional_attempt_number=2,
        previous_evaluation=invalid_previous,
    )
    evaluation = evaluator._pronunciation_evaluation(
        azure,
        reference_text="Are they sleeping now?",
        focus="Use present continuous tense.",
        instructional_attempt_number=2,
        previous_evaluation=invalid_previous,
        catalog_candidates=candidates,
    )

    assert policy["previous_evidence"] == {}
    assert policy["resolved_issue_keys"] == []
    assert policy["meaningful_improvement"] is False
    assert evaluation.status == evaluator.EvaluationStatus.CONTINUE_WITH_CORRECTION


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


def _ranked_focus_result(*, whats_accuracy: float = 65) -> AzureSpeechResult:
    return _azure_result(
        transcript="What’s your name?",
        words=[
            AzureWordAssessment(
                word="what's",
                accuracy_score=whats_accuracy,
                error_type="None",
                phonemes=[
                    {"Phoneme": "w", "AccuracyScore": 92},
                    {"Phoneme": "ʌ", "AccuracyScore": 91},
                    {"Phoneme": "t", "AccuracyScore": 93},
                    {"Phoneme": "s", "AccuracyScore": 90},
                ],
                syllables=[{"Syllable": "wʌts", "AccuracyScore": 90}],
            ),
            AzureWordAssessment(
                word="your",
                accuracy_score=60,
                error_type="Mispronunciation",
                phonemes=[
                    {"Phoneme": "j", "AccuracyScore": 90},
                    {"Phoneme": "ʊ", "AccuracyScore": 80},
                    {
                        "Phoneme": "ɹ",
                        "AccuracyScore": 20,
                        "NBestPhonemes": [
                            {"Phoneme": "ə", "Score": 100},
                            {"Phoneme": "ɹ", "Score": 15},
                        ],
                    },
                ],
                syllables=[{"Syllable": "jʊɹ", "AccuracyScore": 40}],
            ),
            AzureWordAssessment(
                word="name",
                accuracy_score=98,
                error_type="None",
            ),
        ],
    )


def test_authored_priority_orders_supported_pronunciation_findings() -> None:
    focus_items = [
        {
            "priority": 1,
            "instruction": "In “What’s,” check that the final /s/ is pronounced.",
        },
        {
            "priority": 3,
            "instruction": "In “your,” check that the final /r/ is pronounced.",
        },
    ]

    evaluation = evaluator._pronunciation_evaluation(
        _ranked_focus_result(),
        reference_text="What’s your name?",
        focus="\n".join(
            f"[P{item['priority']}] {item['instruction']}"
            for item in focus_items
        ),
        focus_items=focus_items,
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert [
        issue.description_en.lower()
        for issue in evaluation.displayed_issues
    ] == [
        "say 'what's' again, focusing on the ending.",
        "say 'your' again, focusing on the ending.",
    ]


def test_authored_priority_does_not_create_unsupported_finding() -> None:
    focus_items = [
        {
            "priority": 1,
            "instruction": "In “What’s,” check that the final /s/ is pronounced.",
        },
        {
            "priority": 3,
            "instruction": "In “your,” check that the final /r/ is pronounced.",
        },
    ]

    evaluation = evaluator._pronunciation_evaluation(
        _ranked_focus_result(whats_accuracy=98),
        reference_text="What’s your name?",
        focus="\n".join(
            f"[P{item['priority']}] {item['instruction']}"
            for item in focus_items
        ),
        focus_items=focus_items,
    )

    assert evaluation.status == evaluator.EvaluationStatus.RETRY
    assert len(evaluation.displayed_issues) == 1
    assert "your" in evaluation.displayed_issues[0].description_en.lower()


def test_same_priority_preserves_authored_focus_order() -> None:
    focus_items = [
        {
            "priority": 1,
            "instruction": "In “What’s,” check that the final /s/ is pronounced.",
        },
        {
            "priority": 1,
            "instruction": "In “your,” check that the final /r/ is pronounced.",
        },
    ]

    evaluation = evaluator._pronunciation_evaluation(
        _ranked_focus_result(),
        reference_text="What’s your name?",
        focus="\n".join(
            f"[P{item['priority']}] {item['instruction']}"
            for item in focus_items
        ),
        focus_items=focus_items,
    )

    assert "what's" in evaluation.displayed_issues[0].description_en.lower()
    assert "your" in evaluation.displayed_issues[1].description_en.lower()


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
    assert policy["catalog_version"] == "thai-english-pronunciation-v3"
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
    prosody = result.provider_metadata["policy"]["prosody"]
    assert prosody["enabled"] is True
    assert prosody["score"] == 78
    assert prosody["word_count"] == 0
    assert prosody["utterance_eligible"] is False
    assert prosody["learner_feedback_enabled"] is False
    assert prosody["benchmark_status"] == "collecting"


def test_non_open_language_evaluation_retains_transcript():
    azure = _azure_result(transcript="She is going to work.", pronunciation=False)
    language = evaluator.LanguageEvaluation.model_validate(_language_output())

    evaluation = evaluator._compose_language_evaluation(azure, language)

    assert evaluation.transcript == "She is going to work."


def test_private_comparison_policy_is_not_sent_in_model_context():
    context = evaluator._evaluation_context(
        practice_type="open",
        focus="Use present continuous tense.",
        prompt_en="What are they doing?",
        prompt_th=None,
        target_answers=[],
        examples=[],
        instructional_attempt_number=2,
        previous_evaluation={
            "status": "retry",
            "_provider_policy": {"matches": [{"evidence_score": 90}]},
        },
    )

    assert context["previous_evaluation"] == {"status": "retry"}


def test_prosody_diagnostics_gate_specific_signals_without_learner_feedback():
    words = [
        AzureWordAssessment(word=word, accuracy_score=90)
        for word in ["I", "really", "want", "to", "study", "English"]
    ]
    words[2].unexpected_break_confidence = 0.88
    words[2].break_length = 5_000_000
    words[3].missing_break_confidence = 0.75
    words[0].intonation_error_types = ["Monotone"]
    words[0].monotone_syllable_pitch_delta_confidence = 0.92
    azure = _azure_result(
        transcript="I really want to study English.",
        words=words,
    )
    azure.pronunciation.prosody_score = 54

    diagnostics = evaluator._prosody_policy_metadata(
        azure, focus="Use natural sentence stress and intonation."
    )

    assert diagnostics["score"] == 54
    assert diagnostics["word_count"] == 6
    assert diagnostics["utterance_eligible"] is True
    assert diagnostics["break_confidence_threshold"] == 0.75
    assert diagnostics["break_signals"] == [
        {
            "type": "unexpected_break",
            "word": "want",
            "word_index": 2,
            "confidence": 0.88,
            "break_length": 5_000_000,
        }
    ]
    assert diagnostics["monotone_detected"] is True
    assert diagnostics["monotone_syllable_pitch_delta_confidence"] == 0.92
    assert diagnostics["focus_relevant"] is True
    assert diagnostics["future_feedback_eligible"] is True
    assert diagnostics["learner_feedback_enabled"] is False


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


def test_second_open_attempt_does_not_block_on_coaching_only_issue():
    azure = _azure_result(
        transcript="I am sleeping now.", confidence=0.9
    )
    language = evaluator.LanguageEvaluation.model_validate(_language_output())
    issue = evaluator.EvaluationIssue(
        category=evaluator.IssueCategory.PRONUNCIATION,
        description_en=(
            "Say 'sleeping' smoothly without adding an extra sound."
        ),
        description_th="พูดคำว่า sleeping ให้ต่อเนื่อง",
    )
    previous_policy = {
        "matches": [
            {
                "pattern_id": "cluster_epenthesis",
                "evidence_score": 90,
                "evidence": {
                    "word": "sleeping",
                    "expected_cluster": ["s", "l"],
                },
            }
        ]
    }

    improved_candidate = evaluator._PronunciationCandidate(
        word_index=2,
        focus_match=False,
        severity=90,
        status=evaluator.AssessmentTokenStatus.NEEDS_WORK,
        issue=issue,
        pattern_id="cluster_epenthesis",
        evidence_score=84,
        priority_score=94,
        evidence={
            "word": "sleeping",
            "expected_cluster": ["s", "l"],
        },
    )
    improved = evaluator._compose_language_evaluation(
        azure,
        language,
        pronunciation_candidates=[improved_candidate],
        include_transcript=False,
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": previous_policy},
    )

    unchanged_candidate = evaluator._PronunciationCandidate(
        word_index=2,
        focus_match=False,
        severity=90,
        status=evaluator.AssessmentTokenStatus.NEEDS_WORK,
        issue=issue,
        pattern_id="cluster_epenthesis",
        evidence_score=90,
        priority_score=100,
        evidence={
            "word": "sleeping",
            "expected_cluster": ["s", "l"],
        },
    )
    unchanged = evaluator._compose_language_evaluation(
        azure,
        language,
        pronunciation_candidates=[unchanged_candidate],
        include_transcript=False,
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": previous_policy},
    )

    new_issue_candidate = evaluator._PronunciationCandidate(
        word_index=1,
        focus_match=False,
        severity=75,
        status=evaluator.AssessmentTokenStatus.NEEDS_WORK,
        issue=evaluator.EvaluationIssue(
            category=evaluator.IssueCategory.PRONUNCIATION,
            description_en="Say 'now' again, focusing on the ending.",
            description_th="ลองพูดคำว่า now อีกครั้ง โดยเน้นเสียงท้ายคำ",
        ),
        evidence_score=80,
        priority_score=80,
        evidence={"word": "now", "expected_phoneme": "aʊ"},
    )
    newly_introduced = evaluator._compose_language_evaluation(
        azure,
        language,
        pronunciation_candidates=[new_issue_candidate],
        include_transcript=False,
        instructional_attempt_number=2,
        previous_evaluation={"_provider_policy": previous_policy},
    )

    assert improved.status == evaluator.EvaluationStatus.PASS
    assert improved.displayed_issues == []
    assert unchanged.status == evaluator.EvaluationStatus.CONTINUE_WITH_CORRECTION
    assert unchanged.corrected_answer is None
    assert unchanged.retry_focus == []
    assert newly_introduced.status == evaluator.EvaluationStatus.CONTINUE_WITH_CORRECTION
    assert "now" in newly_introduced.displayed_issues[0].description_en.lower()


def test_tiny_contextual_cluster_artifact_does_not_create_pronunciation_issue():
    azure = _studying_artifact_result(inserted_vowel_duration=500_000)
    context = {
        "prompt_en": "What are you studying?",
        "focus": "Use present continuous tense in your answer.",
        "target_answers": [],
        "examples": [{"en": "I'm studying English."}],
    }

    candidates = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus=context["focus"],
        evaluation_context=context,
    )
    alignment = evaluator._contextual_st_cluster_alignment(
        azure, evaluation_context=context
    )

    assert candidates == []
    assert alignment["inserted_vowel_duration_100ns"] == 500_000
    assert evaluator._cluster_artifact_language_transcript(
        azure, alignment
    ) == "i'm studying english"
    assert evaluator._focus_validation_issues(
        azure,
        focus=context["focus"],
        transcript_override="i'm studying english",
    ) == []


def test_longer_contextual_cluster_insertion_keeps_coaching_feedback():
    azure = _studying_artifact_result(inserted_vowel_duration=1_200_000)
    context = {
        "prompt_en": "What are you studying?",
        "focus": "Use present continuous tense in your answer.",
        "target_answers": [],
        "examples": [{"en": "I'm studying English."}],
    }

    candidates = evaluator._unscripted_pronunciation_candidates(
        azure,
        focus=context["focus"],
        evaluation_context=context,
    )

    assert len(candidates) == 1
    assert candidates[0].pattern_id == "cluster_epenthesis"
    assert candidates[0].evidence["inserted_vowel_duration_100ns"] == 1_200_000
    assert candidates[0].evidence_score == 80


def test_open_evaluation_uses_cleaned_cluster_artifact_text_for_language(
    monkeypatch,
):
    azure = _studying_artifact_result(inserted_vowel_duration=500_000)
    captured = {}
    monkeypatch.setattr(
        evaluator,
        "normalize_speaking_audio",
        lambda *_args, **_kwargs: b"normalized wav",
    )
    monkeypatch.setattr(
        evaluator,
        "assess_with_azure_speech",
        lambda *_args, **_kwargs: azure,
    )
    monkeypatch.setattr(evaluator.Config, "AZURE_SPEECH_REGION", "southeastasia")

    def fake_language(**kwargs):
        captured.update(kwargs)
        language = evaluator.LanguageEvaluation.model_validate(_language_output())
        return evaluator.GeminiLanguageResult(
            evaluation=language,
            model="gemini-3.5-flash-lite",
            latency_ms=30,
            usage={},
            provider_metadata={},
            provider_output_text=language.model_dump_json(),
        )

    monkeypatch.setattr(evaluator, "evaluate_language_with_gemini", fake_language)

    result = evaluator.evaluate_speaking_attempt(
        audio_bytes=b"m4a bytes",
        audio_mime_type="audio/mp4",
        practice_type="open",
        focus="Use present continuous tense in your answer.",
        prompt_en="What are you studying?",
        prompt_th=None,
        target_answers=[],
        examples=[{"en": "I'm studying English."}],
        instructional_attempt_number=2,
    )

    assert captured["azure"].transcript == "i'm studying english"
    assert captured["azure"].alternatives == []
    assert result.evaluation.status == evaluator.EvaluationStatus.PASS
    assert result.evaluation.displayed_issues == []
    artifact = result.provider_metadata["policy"]["language_transcript_artifact"]
    assert artifact == {
        "detected": True,
        "removed_word": "sad",
        "evaluation_transcript": "i'm studying english",
        "inserted_vowel_duration_100ns": 500_000,
    }


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
                        "Duration": 1_200_000,
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
    assert len(descriptions) == 2
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
    detected_descriptions = [
        issue.description_en for issue in evaluation.detected_issues
    ]
    assert any(
        "english" in description.lower() and "ending" in description
        for description in detected_descriptions
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
        "benchmark_status": "collecting",
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
    assert set(result.provider_metadata) == {
        "azure",
        "gemini",
        "policy",
        "timings_ms",
    }
    assert result.provider_metadata["timings_ms"]["gemini_request"] == 30
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

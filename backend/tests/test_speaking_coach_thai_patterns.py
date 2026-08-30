from app.speaking_coach_thai_patterns import (
    pattern_by_id,
    substitution_pattern,
    thai_pronunciation_catalog,
)


def test_catalog_loads_merged_reference_patterns():
    catalog = thai_pronunciation_catalog()

    assert catalog.catalog_version == "thai-english-pronunciation-v3"
    assert catalog.learner_feedback_policy == "word_level_only"
    assert len(catalog.patterns) == 24
    assert len({pattern.id for pattern in catalog.patterns}) == 24


def test_active_substitutions_are_indexed_without_becoming_evidence():
    assert substitution_pattern("ɹ", "l").id == "r_l_confusion"
    assert substitution_pattern("θ", "f").id == "th_substitution"
    assert substitution_pattern("tʃ", "ʃ").id == "ch_substitution"
    assert substitution_pattern("v", "w").id == "v_w_substitution"
    assert substitution_pattern("ʃ", "t").id == "final_sh_to_stop"
    assert substitution_pattern("ɪ", "i").id == "high_front_vowel_confusion"
    assert substitution_pattern("aɪ", "ɑ").id == "diphthong_flattening"
    assert substitution_pattern("m", "n") is None


def test_diagnostic_only_patterns_are_not_runtime_substitutions():
    assert pattern_by_id("vowel_length_quality").runtime_support == "diagnostic_only"
    assert pattern_by_id("word_final_stress").runtime_support == "diagnostic_only"
    assert pattern_by_id("flat_sentence_stress").runtime_support == "diagnostic_only"
    assert pattern_by_id("past_tense_ed_deletion").runtime_support == "diagnostic_only"
    assert pattern_by_id("connected_speech_linking").runtime_support == "diagnostic_only"

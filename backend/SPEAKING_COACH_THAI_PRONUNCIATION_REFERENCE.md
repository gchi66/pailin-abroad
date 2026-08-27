# Thai-English Pronunciation Reference

This document records background context for interpreting Azure Speech evidence and authoring useful Speaking Coach exercises. The machine-readable runtime catalog is `app/speaking_coach_thai_patterns.json`.

The catalog is a prior, not proof. A pattern being common among Thai speakers must never create a learner issue without supporting evidence from that learner's recording. It may identify which Azure signals to inspect and rank already-supported findings. Learner-facing feedback remains word-level; phoneme candidates and internal scores are diagnostic only.

## Merged reference catalog (v2)

The expanded engineering reference supplied on 2026-08-27 was compared with the original ten-pattern catalog. Overlapping rows were consolidated into their existing stable pattern IDs; distinct, independently useful checks received new IDs. This avoids counting closely related descriptions as separate evidence.

| Catalog pattern | What it covers from the expanded reference |
|---|---|
| `final_consonant_weakening` | Dropped final consonants and consonants that are present but unreleased or under-articulated |
| `grammatical_final_s_deletion` | Dropped lexical or grammatical final `-s/-es` |
| `past_tense_ed_deletion` | Dropped past-tense `-ed`, including cluster-forming endings |
| `final_cluster_simplification` | Loss of one or more consonants in endings such as *world*, *next*, *asked*, and *helped* |
| `r_l_confusion` | Final L to N, final/post-vocalic R to N or deletion, and initial R/L confusion |
| `r_cluster_reduction` | R deletion, replacement, or separation in clusters such as *brown*, *green*, *train*, and *drive* |
| `cluster_epenthesis` | General cluster breakup, vowel insertion after S in `st/sk/sp`, and excess syllables in difficult cluster words |
| `velar_nasal_cluster_simplification` | Retaining `/ŋ/` while dropping or weakening following consonants in *think*, *thanks*, *linked*, or *strength* |
| `th_substitution` | Both voiceless `/θ/` and voiced `/ð/` substitutions |
| `v_w_substitution` | `/v/` realized as `/w/` |
| `ch_substitution` | `/tʃ/` realized as `/ʃ/` or `/s/` |
| `non_native_consonant_mapping` | `/z/ → /s/`, `/ʒ/` substitutions, and other supported mappings of G, Z, SH, and ZH |
| `final_sh_to_stop` | Final `/ʃ/` realized as a T-like stop, such as *fish* approaching *fit* |
| `vowel_length_quality` | General vowel length and quality mismatch |
| `diphthong_flattening` | General English diphthong flattening, including the specific `/aɪ/` pattern |
| `high_front_vowel_confusion` | Insufficient distinction between `/ɪ/` and `/iː/`, such as *ship/sheep* |
| `unstressed_vowel_reduction` | Insufficient schwa reduction and excessive prominence or duration in unstressed syllables |
| `spelling_overpronunciation` | Pronouncing normally absent/reduced letters or introducing extra syllables based on spelling |
| `word_final_stress` | Incorrect lexical stress, including systematic final-syllable over-stressing |
| `flat_sentence_stress` | Function-word over-stress, equal stress on every word, and flat or Thai-influenced English intonation |
| `connected_speech_linking` | Words kept overly separate instead of linked in connected speech |
| `word_boundary_consonant_deletion` | Final consonants lost before a consonant at the next word boundary |
| `word_boundary_cluster_difficulty` | Vowel insertion, pausing, or consonant deletion in cross-word clusters |
| `contrast_collapse` | Multiple supported errors combining until words such as *fire/file/fine/find* lose necessary contrasts |

The catalog deliberately consolidates the supplied subcases. For example, `/aɪ/` flattening belongs to `diphthong_flattening`; final-syllable over-stress belongs to `word_final_stress`; and the several sentence-rhythm rows belong to `flat_sentence_stress`.

## Azure prosody evidence

Pronunciation-assessment requests enable `EnableProsodyAssessment` for US English. Azure can therefore return `ProsodyScore` and evidence related to stress, intonation, speaking speed, rhythm, and break errors. The score is parsed and retained as provider evidence, but catalog prevalence or a low aggregate score alone does not create learner-facing criticism. Stress and connected-speech patterns remain diagnostic-only until exercise-specific benchmark thresholds are validated.

## Runtime validation and scoring

Runtime matching is deterministic and local; it does not make another model request. Patterns with `active` or `partial` support are indexed by expected and likely spoken phoneme, cluster, or context. `diagnostic_only` patterns remain unavailable for learner judgments until Azure supplies adequate evidence and benchmark thresholds exist.

Each candidate keeps two separate values:

- **Evidence score (0–100):** strength of the current recording's Azure evidence. Inputs may include expected-phoneme deficit, mismatch with the leading spoken candidate, word/syllable corroboration, and contextual cluster alignment.
- **Priority score (0–100):** evidence score plus authored `FOCUS` and the catalog's pedagogical priority. This ranks supported findings; it does not make an unsupported pattern valid.

Pattern prevalence never adds to the evidence score. Initial learner-facing eligibility remains threshold-based and conservative. Evidence and priority scores are stored in admin diagnostics, not shown as a learner pronunciation grade or native-likeness score.

## Research notes supplied for this reference

- Pronunciation Studio — Thai speaker error patterns involving clusters, final consonants, `/tʃ/`, and stress.
- Packard Communications — Thai/English pronunciation comparison involving clusters, vowel length, and tone or intonation.
- ELT Planning — final L/R to N transfer.
- Thai-language and English-language academic articles on final consonants and consonants absent from the Thai inventory.
- Rungruang (2017), Naresuan University — vowel insertion inside `/s/ + stop` onset clusters.
- StudyCorgi — Thai/English phonetic comparison involving vowel inventory and stress timing.

These notes should be source-linked and independently reviewed before being used in public educational claims. They are sufficient as internal engineering hypotheses for benchmark design, not as proof about an individual learner.

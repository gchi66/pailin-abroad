# Thai-English Pronunciation Reference

This document records background context for interpreting Azure Speech evidence and authoring useful Speaking Coach exercises. The machine-readable runtime catalog is `app/speaking_coach_thai_patterns.json`.

The catalog is a prior, not proof. A pattern being common among Thai speakers must never create a learner issue without supporting evidence from that learner's recording. It may identify which Azure signals to inspect and rank already-supported findings. Learner-facing feedback remains word-level; phoneme candidates and internal scores are diagnostic only.

## Merged reference catalog (v3)

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

Pronunciation-assessment requests enable `EnableProsodyAssessment` for US English. Azure can therefore return `ProsodyScore` and evidence related to stress, intonation, speaking speed, rhythm, and break errors. The checker normalizes word-level `UnexpectedBreak` and `MissingBreak` confidence, break length, Azure's `Monotone` decision, and its syllable-pitch-delta confidence into admin policy diagnostics. Provider confidence values outside the application-level 0–1 range are clamped for policy use while the unmodified Azure response remains available in raw admin diagnostics; nonessential prosody metadata must never fail the pronunciation evaluation.

The provisional diagnostic gate requires at least five assessed words and uses Azure's suggested break-confidence threshold of greater than `0.75`. It also records whether the authored `FOCUS` mentions prosody, stress, intonation, rhythm, linking, connected speech, or fluency. A `future_feedback_eligible` flag makes benchmark candidates easy to locate, but `learner_feedback_enabled` remains false. Neither this flag nor a low aggregate score changes learner status, issues, or feedback until false-positive testing establishes production thresholds.

## Runtime validation and scoring

Runtime matching is deterministic and local; it does not make another model request. Patterns with `active` or `partial` support are indexed by expected and likely spoken phoneme, cluster, or context. `diagnostic_only` patterns remain unavailable for learner judgments until Azure supplies adequate evidence and benchmark thresholds exist.

Each candidate keeps two separate values:

- **Evidence score (0–100):** strength of the current recording's Azure evidence. Inputs may include expected-phoneme deficit, mismatch with the leading spoken candidate, word/syllable corroboration, and contextual cluster alignment.
- **Priority score (0–100):** evidence score plus authored `FOCUS` and the catalog's pedagogical priority. This ranks supported findings; it does not make an unsupported pattern valid.

Pattern prevalence never adds to the evidence score. Initial learner-facing eligibility remains threshold-based and conservative. Evidence and priority scores are stored in admin diagnostics, not shown as a learner pronunciation grade or native-likeness score.

Scripted and unscripted assessment both inspect expected `/s/ + consonant/` clusters for supported vowel insertion. Eligibility normally requires a weak second consonant plus corroboration from word accuracy, syllable accuracy, or segment duration. A moderately scored consonant may also qualify when Azure reports an exceptionally strong second-ranked vowel candidate and at least two timing/word/syllable signals agree. A narrower exception accepts one duration signal when a central epenthetic vowel scores at least 90, sits within 10 points of the leading consonant candidate, and occupies a segment of at least 200 ms while the expected consonant scores no higher than 60. This supports cases such as *sleeping* pronounced approximately `s-uh-leeping` without broadly relaxing the normal consonant threshold or limiting detection to the earlier `st-` special case. Grammar-only `FOCUS` text does not turn every mentioned word into a pronunciation focus.

The contextual `st-` detector scores an aligned inserted vowel by duration rather than assigning a fixed evidence score. Insertions below 80 ms remain visible only as admin alignment artifacts and do not create learner coaching; longer insertions receive progressively stronger evidence. If Azure converts a supported within-cluster sound into a spurious word immediately before the intended `st-` word (for example, recognizing *I'm sad studying* from intended *I'm studying*), the raw transcript remains unchanged in diagnostics while language validation receives the reconstructed text. This prevents a pronunciation alignment artifact from becoming a false grammar error.

Accent findings are coaching issues rather than permanently blocking failures. Attempt one may request one retry and shows at most two findings, ranked by supported pronunciation focus and catalog evidence. On attempt two, resolving the prior issue or lowering its composite evidence score by at least five points produces a pass. If a coaching issue remains without measurable improvement, the learner receives a final correction and continues anyway. Content miscues, unclear audio, and other blocking failures retain their stricter handling.

Catalog v3 supports post-vocalic rhotic-vowel deletion when Azure aligns a weak expected rhotic vowel such as `/ɑɹ/` to a leading non-rhotic vowel and at least two word, syllable, or candidate-list signals corroborate it. It also retains onset-cluster evidence when the inserted vowel is a strong second-ranked candidate, provided both timing and word/syllable evidence support the finding. A supported catalog-specific finding replaces a generic finding for the same word so learner feedback uses the more actionable description. Empty, zero-evidence, or identity-free findings are excluded from attempt-to-attempt improvement comparisons.

## Research notes supplied for this reference

- Pronunciation Studio — Thai speaker error patterns involving clusters, final consonants, `/tʃ/`, and stress.
- Packard Communications — Thai/English pronunciation comparison involving clusters, vowel length, and tone or intonation.
- ELT Planning — final L/R to N transfer.
- Thai-language and English-language academic articles on final consonants and consonants absent from the Thai inventory.
- Rungruang (2017), Naresuan University — vowel insertion inside `/s/ + stop` onset clusters.
- StudyCorgi — Thai/English phonetic comparison involving vowel inventory and stress timing.

These notes should be source-linked and independently reviewed before being used in public educational claims. They are sufficient as internal engineering hypotheses for benchmark design, not as proof about an individual learner.

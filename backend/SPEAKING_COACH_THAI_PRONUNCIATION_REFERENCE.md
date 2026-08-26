# Thai-English Pronunciation Reference

This document records background context for interpreting Azure Speech evidence and authoring useful Speaking Coach exercises. The machine-readable runtime catalog is `app/speaking_coach_thai_patterns.json`.

The catalog is a prior, not proof. A pattern being common among Thai speakers must never create a learner issue without supporting evidence from that learner's recording. It may identify which Azure signals to inspect and rank already-supported findings. Learner-facing feedback remains word-level; phoneme candidates and internal scores are diagnostic only.

## Reference patterns

1. **Dropped or unreleased final consonants.** Thai syllable endings are generally unreleased, and final consonant clusters differ from English. English final consonants—especially `/p t k b d g/`—may therefore be dropped or barely audible.
2. **Consonant-cluster breakup (epenthesis).** Learners may insert a short vowel into unfamiliar English clusters. For `/sk-/` and `/st-/`, the documented direction is after `/s/`, such as `scan` becoming approximately `sa-kan` and `study` becoming approximately `s-uh-tudy`.
3. **R/L confusion and possible final N realization.** Initial `/r/` and `/l/` may be conflated, while syllable-final R or L may be realized closer to N.
4. **TH substitutions.** `/θ/` and `/ð/` may be replaced with `/t d s f/`, depending on the word and speaker.
5. **CH substitutions.** `/tʃ/` may be realized closer to `/ʃ/` or `/s/`, especially in difficult positions.
6. **V/W substitution.** `/v/` may be realized closer to `/w/`.
7. **Mapping of non-native consonants.** `/g z ʃ ʒ/` may be systematically mapped to more familiar sounds.
8. **Vowel length and quality.** English vowel duration or quality contrasts may be flattened, shortened, or lengthened.
9. **Final-syllable word stress.** Multisyllabic English words may receive too much stress on the final syllable.
10. **Flat sentence stress or over-stressed function words.** Function and content words may receive overly equal weight, with reduced control of English sentence-level rhythm and intonation.

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

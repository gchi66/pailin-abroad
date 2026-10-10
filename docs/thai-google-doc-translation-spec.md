# English-to-Thai Google Docs Translation Specification

- Status: Draft for review before implementation
- Initial target: Level 14
- Future targets: Levels 15 and 16

## 1. Purpose

This document defines how an English Pailin Abroad lesson Google Doc should be transformed into its Thai-localized Google Doc while preserving the established lesson structure, instructional intent, and visual formatting.

This is an implementation contract for a future translation tool. It is not the translator implementation itself.

The intended result is a review-ready Thai lesson document that follows the established house style closely enough that a human reviewer corrects language and exceptional formatting rather than rebuilding the document manually.

## 2. Evidence used

The rules below were inferred from:

- Matched raw Google Docs API responses for Level 5 English and Thai.
- Matched raw Google Docs API responses for Level 12 English and Thai.
- Parsed English and Thai lesson JSON for Levels 1 through 13.
- Parsed English lesson JSON for Levels 14 through 16.

Primary raw references:

- `backend/data/level_5.raw.json`
- `backend/data/level_5_th.raw.json`
- `backend/data/level_12.raw.json`
- `backend/data/level_12_th.raw.json`

Primary parsed references:

- `backend/data/level_1.json` through `backend/data/level_13.json`
- `backend/data/level_1_th.json` through `backend/data/level_13_th.json`
- `backend/data/level_14.json` through `backend/data/level_16.json`

Observed structural evidence:

| Document | Body elements | Tables | Linked text runs | Text runs |
| --- | ---: | ---: | ---: | ---: |
| Level 5 English | 6,771 | 14 | 30 | 8,927 |
| Level 5 Thai | 6,809 | 14 | 30 | 10,050 |
| Level 12 English | 7,098 | 34 | 16 | 9,731 |
| Level 12 Thai | 7,270 | 34 | 16 | 11,636 |

The matched pairs also have identical table geometry and identical link-target inventories. Together with increased Thai body elements and text runs, this shows that localization preserves the document skeleton while adding bilingual content in selected places.

Across Levels 1 through 13:

- English and Thai files have the same lesson count at every level.
- The Thai files retain the same core section order.
- Every English level has `PREPARE`; every corresponding Thai level omits it.
- Dialogue, examples, and exercises commonly retain English and add Thai rather than replacing English.

## 3. Normative language

The terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe requirements for the future tool.

- **MUST** rules are validation requirements. A violation stops automatic writing.
- **SHOULD** rules are the default house style. Deviations require an explicit exception or review flag.
- **MAY** rules are optional and should not affect structural validity.

## 4. Core transformation model

The destination document MUST begin as a copy of the English source document.

The tool MUST modify only the explicitly allowlisted destination copy. It MUST NOT modify the English source document.

The tool MUST treat the destination as a structural and formatting template. It MUST NOT attempt to recreate the document from the `documents.get` JSON response.

Localization is not a global search-and-replace operation. Each content block must be classified as one of the following:

| Classification | Result |
| --- | --- |
| Preserve | Keep the English text unchanged. |
| Translate | Replace English prose with Thai. |
| Bilingual | Retain English and add the corresponding Thai immediately after it. |
| Localize | Preserve a protected English term while translating its surrounding explanation. |
| Remove | Delete a section that is intentionally absent from Thai documents. |
| Structural | Preserve exactly; do not send it to the language model. |

Classification MUST be based on the lesson section and the block's instructional role, not on language detection alone.

## 5. Global content rules

### 5.1 Source-authority rule

The source document MUST be presumed intentional in every detail. The tool MUST NOT decide that text or formatting is an accidental typo, grammar mistake, punctuation error, capitalization error, duplicated word, unusual spacing choice, or inconsistent style.

This rule applies even when the source differs from conventional English or from earlier lessons. Such differences may be the teaching object, a deliberate distractor, a correct/incorrect contrast, a representation of natural speech, or part of an importer convention.

The tool therefore MUST:

- Preserve unusual English exactly wherever English is retained.
- Translate the intended meaning without silently repairing the source.
- Preserve intentional errors and their relationship to corrections.
- Preserve punctuation, capitalization, repetition, spacing, and formatting when they affect the example or exercise.
- Treat previous lessons as localization and layout guides, not as authority to overwrite current source content.
- Flag a genuine ambiguity for human review instead of normalizing it.

Only an explicit human-approved exception may correct source content.

### 5.2 Material that must remain structurally unchanged

The following MUST remain unchanged unless a section rule explicitly says otherwise:

- Lesson number and external ID, such as `14.1`.
- Lesson ordering.
- Section ordering, apart from removal of `PREPARE`.
- Table count, table placement, row count, and column count.
- URLs and link targets.
- Named ranges and bookmarks, if present.
- Images, drawings, and embedded objects, if present.
- Headers, footers, page breaks, margins, and page settings.
- Audio markers such as `[audio:12.1_prepare_1]`.
- Image keys and other importer tokens.
- Exercise answer keys.
- Multiple-choice labels such as `A`, `B`, `C`, and `D`.
- Blank markers such as `______` and their blank IDs.
- Stable delimiters or parser labels required by the importer.
- Intentional numbers, currency values, mathematical notation, and punctuation that affect an answer.

### 5.3 Protected English

English that is the object of instruction MUST remain visible in English. This includes:

- Target vocabulary and phrases.
- Grammar forms and sentence structures.
- Model sentences.
- Fill-in-the-blank sentences.
- Multiple-choice English answer content when the exercise tests comprehension of English.
- Words being defined, contrasted, conjugated, corrected, or pronounced.
- Literal placeholders such as `[verb]`, `[noun]`, and bracketed construction patterns when their English form is instructionally important.

Protected English MAY receive an adjacent Thai gloss or Thai translation according to the applicable section rule.

The tool MUST NOT transliterate an English target into Thai in place of the original target. Thai transliteration or explanation may be added alongside it.

### 5.4 Thai-only prose

The following SHOULD normally become Thai-only:

- Lesson backstory prose.
- Explanatory prose addressed to the learner.
- General instructions that do not themselves test English comprehension.
- Comprehension-question prompts.
- Culture-note explanations.
- Grammar explanations outside quoted English examples.
- Pinned discussion questions.

### 5.5 Bilingual prose

The following SHOULD normally be bilingual, English first and Thai second:

- Conversation transcript lines.
- Quoted conversation lines inside `APPLY`.
- Model responses in `APPLY`.
- Example sentences in teaching sections.
- Phrase-and-verb example sentences.
- Exercise stems when retaining the English is necessary to complete the exercise.
- Comprehension answer choices.

Unless the existing layout clearly establishes a different form, use:

```text
English text
ข้อความภาษาไทย
```

Speaker labels MUST appear in both languages on their respective lines when a speaker is named.

## 6. Lesson and section rules

### 6.1 Lesson heading and metadata

In the Google Doc lesson heading, retain the English title and append the Thai title, following the established pattern:

```text
LESSON 14.1: English title ชื่อบทเรียนภาษาไทย
```

`LESSON` and the lesson number remain English and appear exactly once. Only
the authored title after the English prefix is translated; the tool MUST NOT
append a Thai equivalent such as `บทเรียน 14.1:`.

The source-only lesson banner marker immediately following the heading, such
as `[header_img:pailin_chloe]`, MUST be removed from the Thai document. Regular
`[img:...]` content markers are unaffected by this rule.

In parsed/localized metadata:

- `external_id`, `level`, `lesson_order`, and stage classification MUST remain unchanged.
- `title`, `focus`, `backstory`, tags, and pinned-comment content SHOULD be localized into Thai.
- Internal asset fields such as `header_img` MUST remain unchanged even if a parser omits them from one localized export.
- `focus_short` and similar machine-used fields MUST be preserved unless the importer explicitly derives them elsewhere.

Names in Thai prose SHOULD use the established Thai spellings from previous levels. English lines retain English names.

### 6.2 PREPARE

`PREPARE` MUST be omitted from the Thai document by default.

Evidence: all 13 existing English levels contain `PREPARE`, and all 13 corresponding Thai levels omit it.

Removal must include the section heading and the section's content, but MUST NOT remove the next lesson or next section boundary.

If a future lesson contains unique required material in `PREPARE` that appears nowhere else, the dry-run report SHOULD flag it for a manual decision instead of silently deleting it.

### 6.3 Transcript or conversation

Each English transcript line MUST remain, followed immediately by its Thai translation.

Format:

```text
Tyler: English dialogue.
ไทเลอร์: บทสนทนาภาษาไทย
```

Rules:

- Preserve speaker order and line order.
- Preserve the English speaker name on the English line.
- Use the glossary-approved Thai speaker name on the Thai line.
- Preserve stage directions while translating them appropriately, for example `*laughs*` to a Thai stage direction.
- Preserve highlighted or underlined target phrases on the English line.
- Apply equivalent emphasis to the semantic Thai counterpart only when it can be mapped confidently.
- Do not add or remove dialogue turns.

### 6.4 APPLY

General scenario instructions SHOULD be translated into Thai.

Quoted dialogue from the lesson MUST remain in English and receive a Thai line directly beneath it.

The model response MUST remain in English and receive a Thai line directly beneath it.

Formatting applied to an English quoted line, such as cyan highlighting, MUST be retained on that English line. The Thai companion line SHOULD inherit the paragraph-level treatment seen in the established Thai documents.

The target English construction MUST remain unchanged. A Thai translation must not accidentally reveal, remove, or replace an answer-bearing English phrase.

### 6.5 UNDERSTAND

Section labels SHOULD follow the existing bilingual-heading convention where applicable, for example:

```text
LESSON FOCUS ประเด็นหลักของบทเรียนนี้
```

Rules:

- Explanatory prose becomes Thai.
- English terms being taught remain English inside the Thai explanation.
- English sentence structures remain English.
- Example sentences remain English and receive Thai companion lines.
- Labels such as `Sentence structures` SHOULD be translated into Thai unless their bilingual form is part of the established visual design.
- Grammatical annotations may be translated, but they MUST continue pointing to the same semantic part of the example.
- Contrasts such as correct/incorrect, singular/plural, formal/informal, or intentional/accidental MUST remain explicit.

### 6.6 EXTRA TIP

Use the same basic policy as `UNDERSTAND`:

- Translate the explanation.
- Preserve English target expressions and construction patterns.
- Make instructional examples bilingual.
- Preserve emphasis that identifies the feature being taught.

### 6.7 COMMON MISTAKE

The incorrect and corrected English forms MUST both remain exactly identifiable.

Rules:

- Translate the explanation of why a form is incorrect.
- Preserve correctness markers, contrast formatting, strikethrough, color, and emphasis.
- Add Thai explanation or glosses without rewriting the English error into a different error.
- Never allow the language model to “fix” intentionally incorrect English before the contrast is recorded.

### 6.8 PHRASES & VERBS

This section is instructionally important and MUST be retained in full.

For each entry:

- Preserve the English phrase heading.
- Add or retain a concise Thai meaning or functional gloss.
- Translate the usage explanation into Thai while preserving referenced English expressions.
- Keep every English example sentence.
- Add its Thai translation directly after it.
- Preserve speaker identities and use Thai speaker names on Thai lines.
- Preserve all audio markers exactly and keep each marker associated with its original English example.
- Preserve list indentation and grouping so examples remain attached to the correct phrase.

The first audio item for an entry uses a single bullet and a single line:

```text
English phrase Thai gloss [audio:phrases_verbs_key_1]
```

The Thai gloss appears after the English phrase and before the audio marker. It
MUST NOT be placed in a second bullet. For subsequent `_2`, `_3`, and similar
English examples, keep the English and audio marker on the bullet's first line,
then add the Thai companion with a soft line break inside that same list item.
The Thai companion MUST NOT create another bullet or repeat the audio marker.

The localized content should follow the established pattern:

```text
Gotcha เข้าใจละ [audio:...]
คำอธิบายการใช้ภาษาไทย โดยคงคำว่า Got you และ I understand ไว้เมื่อจำเป็น
Luke: English example. [audio:...]
ลูค: ตัวอย่างภาษาไทย
```

Phrase headings that function as category labels may be bilingual on one line. Examples and dialogue should remain English-first/Thai-second.

### 6.9 CULTURE NOTE

Culture-note explanatory prose SHOULD be Thai-only.

English cultural terms or phrases under discussion MAY remain in English with a Thai explanation, especially when the learner may encounter the English term in real life.

Headings SHOULD be Thai or bilingual according to the dominant precedent for that heading level.

The translation SHOULD explain the intended cultural point naturally rather than reproduce English syntax literally.

### 6.10 Comprehension questions

For each question:

- Translate the prompt into Thai.
- Preserve question order.
- Preserve each option label on the English option only.
- Preserve the answer key exactly.
- Retain each English option and add its Thai translation on the next line.
- Preserve associated image keys and image placement.
- Do not change the relative plausibility of distractors.
- Do not add hints that make the correct answer more obvious in Thai than in English.

Expected option form:

```text
A. Because he enjoys watching movie trailers.
เพราะว่าเขาชอบดูตัวอย่างภาพยนตร์
```

The Thai companion MUST NOT repeat `A.`, `B.`, `C.`, or `D.`. The label belongs
to the choice as a whole and is already present on its English line.

### 6.11 Practice exercises

The corpus contains four principal kinds: `fill_blank`, `multiple_choice`, `open`, and `sentence_transform`.

Rules common to all exercise kinds:

- Preserve kind, ordering, item numbering, answer keys, and scoring-relevant data.
- Translate general directions into Thai.
- Preserve target English phrases and answer banks.
- Keep answer-bearing English text visible.
- Add Thai support beneath corresponding English text where established.
- Preserve blanks exactly in English lines.
- A Thai companion line SHOULD represent a blank with a non-answer-revealing placeholder such as an em dash when that matches existing practice.
- Do not translate a correct English answer into the actual answer field.
- Preserve audio and image markers.

Additional rules by kind:

#### Fill blank

- Preserve every blank's position in its English sentence.
- Preserve accepted answers exactly.
- The Thai line must communicate the surrounding meaning without filling in or strongly disclosing the missing expression.

#### Multiple choice

- Keep every English choice when English comprehension is being tested.
- When the options are English words or forms intended to fill an English
  blank, keep the options English-only. Translating them would disclose or
  alter the language choice being tested.
- When the choices describe meanings or interpretations, a Thai companion MAY
  be added beneath each English choice.
- A Thai choice companion MUST NOT repeat its `A.`, `B.`, `C.`, or `D.` label.
- Thai companions for practice dialogue or stem lines MUST omit structural
  prefixes such as `TEXT:`, `A:`, and `B:`. Those prefixes remain on the
  corresponding English line.
- Preserve labels, choice order, and answer key.

#### Sentence transform

- Preserve the source English, transformation cue, and expected English form.
- Translate only explanatory directions and supporting meaning.
- Do not normalize away tense, person, punctuation, or capitalization that the exercise tests.

#### Open response

- Translate the prompt into Thai.
- Retain model English where supplied and add Thai support below it.
- Preserve any rubric or required target expression.

## 7. Formatting rules

### 7.1 Structural formatting

The tool MUST preserve:

- Paragraph order and section boundaries, except intentional `PREPARE` removal and required bilingual insertions.
- Tables and their geometry.
- Paragraph named styles.
- Heading levels.
- Bullets, numbering, nesting levels, and indentation.
- Alignment, line spacing, and paragraph spacing.
- Page breaks and section breaks.
- Font family and base font size unless Thai glyph support requires an explicit approved fallback.
- Links and their target URLs.
- Images and embedded objects.

Thai companion content must be inserted within the same logical container as its English source. Text originating in a table cell MUST remain in that table cell.

### 7.2 Inline formatting

The tool MUST recognize at least:

- Bold
- Italic
- Underline
- Strikethrough
- Foreground color
- Background highlight
- Link styling
- Baseline offset or superscript/subscript when present
- Font family and size changes

Formatting is semantic, not positional. Thai text usually differs in length and word order, so character offsets from the English text MUST NOT be copied blindly.

Inline styles should be represented as semantic spans during translation, for example:

```json
{
  "unit_id": "14.1-understand-para-12",
  "segments": [
    {"style_id": "normal", "text": "Explanation before "},
    {"style_id": "target-blue-underline", "text": "target phrase"},
    {"style_id": "normal", "text": "."}
  ]
}
```

The translation response must preserve the segment identities or explicitly map each styled source segment to its Thai counterpart.

The implementation represents mapped exceptions in a translation part as
`translated_style_spans`. Each span records character-based `start` and `end`
offsets, the expected Thai `text` at that range, and the Google Docs `style` to
apply. The expected text is a write-time guard against stale or incorrect
offsets. Links must include their unchanged target in the span style; the
writer converts character offsets to Google Docs UTF-16 indexes.

If a semantic style cannot be mapped confidently, the tool SHOULD preserve the complete English styled line and insert an unstyled Thai companion line, then flag the unit for review. Guessing at a highlight boundary is worse than an explicit review flag.

### 7.3 Do not treat API text-run boundaries as meaning

Google Docs may split text runs at arbitrary points, including in the middle of a Thai word or character sequence. A raw `textRun` boundary is not necessarily a semantic or formatting boundary.

Adjacent runs with equivalent effective style SHOULD be normalized into a single semantic segment before translation. The original document indexes still need to be recorded for later updates.

### 7.4 Soft breaks and new paragraphs

Google Docs vertical-tab soft breaks (`\u000b`) and paragraph breaks (`\n`) are not interchangeable.

- Preserve the distinction when it affects layout, lists, or table cells.
- Use the established English-first/Thai-second break type from the corresponding section pattern.
- Do not convert a sequence of separate list items into soft-broken text or vice versa.

## 8. Translation style

### 8.1 Audience and voice

Thai should be natural, accessible teaching language for Thai learners of English.

- Prefer natural Thai over word-for-word English syntax.
- Preserve the meaning and teaching point before stylistic literalness.
- Address the learner consistently, normally with `คุณ` where direct address is needed.
- Use a clear, friendly, conversational teaching voice.
- Avoid unnecessarily academic Thai when a common expression is accurate.
- Do not add facts, examples, warnings, or cultural claims absent from the source.

### 8.2 Dialogue voice and gender

Dialogue must preserve character identity, relationship, tone, and gendered particles.

- Female speakers should use appropriate female first-person forms and particles where natural.
- Male speakers should use appropriate male first-person forms and particles where natural.
- Do not mechanically add `ค่ะ` or `ครับ` to every sentence; use them naturally according to context.
- Preserve informality, surprise, hesitation, laughter, and emphasis.
- Maintain continuity within a conversation.

### 8.3 Terminology consistency

No separate glossary-building phase or glossary artifact is required. Existing Levels 1 through 13 MAY be consulted directly for established character-name spellings, recurring instructional labels, grammar terminology, and app-specific wording when useful.

Previously approved terminology SHOULD be reused when it fits the current context. Where previous documents disagree, the tool MUST NOT silently normalize the current source or assume that the difference is accidental. It should preserve source-specific content and flag any material translation ambiguity.

### 8.4 Proper nouns and numbers

- English lines retain English proper nouns.
- Thai lines may transliterate well-known names using the established corpus spelling.
- Preserve numbers when their exact form matters to the exercise or example.
- Natural Thai time or quantity wording may be used in translated prose when it does not affect the learning task.
- Preserve currencies and measurements; add Thai clarification only when useful and non-disruptive.

## 9. Translation-unit contract

The future extractor SHOULD create stable, reviewable translation units. Each unit should contain at least:

- Stable unit ID.
- Lesson ID.
- Section type.
- Structural role.
- Source English text.
- Effective paragraph and inline styles.
- Protected spans.
- Audio, link, blank, answer, and image tokens.
- Speaker identity, when applicable.
- Surrounding context sufficient for translation.
- Original Google Docs range information.
- Required output mode: translate, bilingual, localize, preserve, or remove.

Translation should occur at the paragraph, dialogue turn, exercise item, or similarly coherent level. Individual text runs SHOULD NOT be translated independently because that destroys linguistic context.

When one Google Docs paragraph contains both an example and an explanation separated by an authored soft break, the manifest MUST retain them as ordered parts with independent actions. The English example is bilingual; the explanatory part is localized. The tool MUST NOT duplicate the entire English explanation merely because it shares a paragraph with an example.

The language-model response MUST be structured data keyed by unit ID. It MUST NOT be free-form prose intended for manual copy/paste.

## 10. Safety and write model

Before any Google Doc write:

1. Confirm the destination document ID against an explicit allowlist.
2. Fetch and record the destination revision ID.
3. Confirm that the destination is not the known English source document.
4. Create a complete local raw snapshot.
5. Produce the translated unit manifest.
6. Validate every unit and protected token.
7. Produce a dry-run report.
8. Require an explicit command option to perform writes.

The writing phase SHOULD:

- Apply updates from later document indexes to earlier indexes so insertions do not invalidate pending ranges.
- Use revision preconditions when the API supports them.
- Stop if the document revision changes between planning and writing.
- Be restartable without duplicating Thai lines.
- Record every request and affected unit ID in a machine-readable operation log.

The service account SHOULD receive editor access only to the destination copy, not to the English source or an entire Drive folder.

## 11. Validation requirements

### 11.1 Pre-write validation

The planned translation MUST pass all of these checks:

- Every source unit has exactly one classified result.
- Every required translation unit has non-empty Thai output.
- Every protected English span is present exactly where required.
- Every audio marker is preserved exactly and appears the expected number of times.
- Every blank marker and answer-bearing token is preserved.
- Every URL and link target is unchanged.
- Every table maps to the same table, row, column, and cell structure.
- Every lesson and section boundary is accounted for.
- `PREPARE` is the only section removed by the default policy.
- No internal unit markers or model instructions appear in final text.
- Thai output does not contain accidental Markdown or JSON escaping.

### 11.2 Post-write validation

After writing, the tool MUST refetch and reparse the destination document, then verify:

- Lesson count and ordering match the source.
- Required section count and ordering match the policy.
- Table count and geometry match the source.
- Link count and targets match the source.
- Audio-marker inventory matches expectations.
- Exercise answer keys and blanks match the source.
- English target expressions remain present.
- Expected Thai companion content is present.
- No duplicated translation lines were introduced.
- No untranslated explanatory block remains unless explicitly allowed or flagged.
- No unexpected deletion occurred outside planned ranges.

A visual audit report SHOULD list:

- Units containing highlights or colored text.
- Units with ambiguous style mapping.
- Tables whose cell content changed significantly in length.
- Page-break movement risks.
- Very long Thai translations.
- Unrecognized structures or content types.

## 12. Failure policy

The tool MUST fail closed. It must not write a partial document when:

- A structural boundary cannot be identified reliably.
- The document revision changed after extraction.
- A translation unit is missing or duplicated.
- Protected content changed.
- A required style mapping is structurally unsafe.
- A table, list, link, or embedded object cannot be mapped.

Individual linguistic uncertainties may be written only when they are clearly flagged in the review report and do not threaten document structure or exercise correctness.

## 13. Dry-run deliverables

Before the first Level 14 write, the tool should produce:

1. A raw destination snapshot.
2. A translation-unit manifest containing source text, translated text, action, and style mapping.
3. A protected-token validation report.
4. A structural diff summary.
5. A human-readable list of warnings and ambiguous cases.
6. The planned Google Docs operations without executing them.

The first dry run SHOULD be reviewed on at least one complete lesson containing:

- Dialogue.
- `APPLY`.
- A grammar explanation.
- A highlighted target phrase.
- A comprehension question.
- Each exercise type used by that lesson.
- A `PHRASES & VERBS` entry.
- At least one table, if present.

## 14. Defaults adopted for Levels 14 through 16

Unless review changes these decisions, use the following defaults:

- Use Levels 1 through 13 as localization and layout precedent while treating the current source document as authoritative.
- Presume every source spelling, grammar choice, punctuation mark, repetition, and formatting choice is intentional; never silently correct or normalize it.
- Remove `PREPARE` from Thai documents.
- Preserve English targets and examples; add Thai support according to section rules.
- Translate instructional and explanatory prose naturally into Thai.
- Preserve structure by modifying a duplicate of the English document.
- Treat semantic formatting as more important than matching character offsets.
- Flag uncertainty instead of silently guessing.
- Require a dry run before enabling writes.

## 15. Items to confirm during Level 14 dry run

These do not block specification work but must be checked against the actual Level 14 template:

- Whether Level 14 introduces any new section labels or structures not present in Levels 1 through 13.
- Whether any image or embedded-object types require special handling.
- Whether all target phrases can be mapped cleanly to Thai semantic spans.
- Whether any `PREPARE` content is uniquely required elsewhere in the localized lesson.
- Whether Thai text expansion causes problematic table overflow or page-break movement.
- Whether differing historical heading forms represent context-specific conventions that must remain distinct.

## 16. Definition of success

The process is successful when:

- The generated Thai document parses correctly with the existing importer.
- All lessons and required content are present.
- English learning material remains usable.
- Thai explanatory content is complete and coherent enough for launch review.
- Formatting, tables, links, highlights, and indentation require only exceptional manual correction.
- A human reviewer can focus on Thai quality and nuanced teaching choices rather than document reconstruction.

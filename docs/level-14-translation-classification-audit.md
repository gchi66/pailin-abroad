# Level 14 Thai Translation Classification Audit

- Status: Phase 1 complete
- Pilot lesson: 14.1
- Scope: content classification only; no translations and no Google Docs writes

## Sources compared

- Level 5 English raw Google Docs JSON
- Level 5 Thai raw Google Docs JSON
- Level 12 English raw Google Docs JSON
- Level 12 Thai raw Google Docs JSON
- Level 14 destination raw Google Docs JSON
- Parsed English/Thai lesson JSON for Levels 1–13
- Parsed English Level 14 JSON

## Audit method

The Level 5 and 12 English documents were classified with the same rules used for Level 14. Their source text was then checked against the corresponding Thai raw documents.

Exact retention is a deliberately strict signal. It understates successful bilingual localization when an older Thai document changed punctuation, broke one source paragraph into several paragraphs, or made small edits to its retained English. Nevertheless, it clearly distinguishes the major content policies.

## Evidence from the paired documents

| Content type | Level 5 result | Level 12 result | Final rule |
| --- | ---: | ---: | --- |
| Conversation English retained | 180/181 | 216/219 | Bilingual |
| Comprehension English choices retained | 134/134 | 241/241 | Bilingual |
| Comprehension prompts retained in English | 0/44 | 0/59 | Thai replacement |
| Comprehension labels/answers retained | 136/136 | 191/191 | Preserve |
| APPLY English examples/responses retained | 36/37 | 29/29 | Bilingual |
| APPLY instructions retained in English | 1/30 | 0/28 | Thai replacement |
| Backstories retained in English | 0/16 | 0/15 | Thai replacement |
| Focus text retained verbatim | 0/30 | 0/30 | Localize while retaining target English terms |
| PREPARE body retained | 0/173 | 0/158 | Remove entire section |

Practice content also strongly supports preserving answer-bearing English: 90% of Level 5 and 94% of Level 12 units classified as bilingual were retained exactly. Most exceptions are historical punctuation, segmentation, or authoring differences—not evidence that the English should be discarded.

## Corrections made during the audit

### 1. False lesson boundary fixed

A normal paragraph in Lesson 14.1 says:

```text
Lesson 14.11 will go more in-depth with this.
```

Text-only detection initially treated this as a lesson boundary. Lesson boundaries now require a Google Docs heading style, matching the established parser. The detected order now matches the parsed document exactly:

```text
14.1 through 14.12, followed by 14.chp
```

### 2. Comprehension table labels fixed

Structural cells containing `Prompt` and `Options` are now preserved instead of translated. Actual numbered prompts are translated, choices are bilingual, and answer keys remain unchanged.

### 3. PREPARE heading fixed

The `PREPARE` heading and its body are both classified for removal. The L14.1 removal range is recorded as Google Docs indexes 2,041–2,352.

### 4. Mixed example/explanation paragraphs modeled explicitly

Google Docs sometimes stores an English example and its explanation in one paragraph separated by a vertical-tab soft break. A single action for the whole paragraph was too coarse.

These paragraphs now contain ordered translation parts. For example:

```text
Chloe: You were there for a while. But, you know, maybe this is a good thing? [audio:...]
```

is `bilingual`, while:

```text
‘But’ signals a contrasting idea.
```

is `localize`.

L14.1 contains 27 such mixed paragraphs. This preserves the exact teaching example without unnecessarily duplicating the English explanation.

### 5. Exercise warnings resolved into hard rules

Answer-bearing practice text no longer produces a generic classification warning. It has a deterministic bilingual classification with `preserve_source_in_output: true`. Blanks, directives, answers, and option labels remain protected separately.

## Final L14.1 classification

| Action | Units |
| --- | ---: |
| Bilingual | 177 |
| Localize | 82 |
| Mixed | 27 |
| Preserve | 76 |
| Remove | 10 |
| Translate | 11 |
| **Total** | **383** |

Additional results:

- Raw and parsed lesson inventories match.
- Classification warnings: 0.
- Validation issues: 0.
- Planned PREPARE removal ranges: 1.
- Every unit retains the original source text in the manifest.
- Every mixed unit records its parts and whether the source part must remain in the output.

## Settled L14.1 rules

- Lesson heading: retain English and append Thai.
- Asset marker: preserve.
- Main parser section headings: preserve, except `PREPARE`.
- Focus: localize while retaining instructional English terms.
- Backstory: replace with Thai.
- Conversation: English followed by Thai.
- PREPARE: remove completely.
- Comprehension prompt: replace with Thai.
- Comprehension choice: English followed by Thai.
- Comprehension labels and answer keys: preserve.
- APPLY instructions: replace with Thai.
- APPLY quotation and response: English followed by Thai.
- Teaching explanations: localize.
- Teaching examples: English followed by Thai.
- Combined teaching example/explanation: mixed parts.
- Phrase headings and examples: bilingual.
- Phrase explanations: localize.
- Practice titles: bilingual.
- Practice instructions: localize.
- Practice stems, text, and choices: bilingual with exact English retained.
- Practice control directives and answers: preserve.
- Pinned comment and tags: translate.

## Phase 1 conclusion

The L14.1 manifest is ready to serve as the classification input for translation validation and translation generation. No unresolved classification requires user input before proceeding.

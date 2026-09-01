"""Target-aware phoneme alignment over Azure's provisional recognition output."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.speaking_coach_thai_patterns import substitution_pattern


POLICY_PATH = Path(__file__).with_name("speaking_coach_alignment_policy.json")
IPA_VOWELS = {
    "a",
    "ɑ",
    "ɐ",
    "æ",
    "e",
    "ɛ",
    "ɜ",
    "ɚ",
    "ɝ",
    "i",
    "ɪ",
    "o",
    "ɔ",
    "u",
    "ʊ",
    "ʌ",
    "ə",
    "ɒ",
    "aɪ",
    "aʊ",
    "eɪ",
    "oʊ",
    "ɔɪ",
}


def normalize_phoneme(value: str) -> str:
    return (
        re.sub(r"[\s.ˈˌ-]+", "", value.lower())
        .replace("r", "ɹ")
        .replace("ɻ", "ɹ")
        .replace("ɫ", "l")
    )


class AlignmentCosts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exact_match: float = Field(ge=0, le=2)
    catalog_substitution: float = Field(ge=0, le=2)
    candidate_supported_substitution: float = Field(ge=0, le=2)
    cluster_epenthesis: float = Field(ge=0, le=2)
    ordinary_substitution: float = Field(gt=0, le=4)
    insertion: float = Field(gt=0, le=4)
    deletion: float = Field(gt=0, le=4)


class AlignmentThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_like_score: float = Field(ge=0, le=1)
    ambiguous_score: float = Field(ge=0, le=1)
    minimum_target_coverage: float = Field(ge=0, le=1)
    maximum_unsupported_changes: int = Field(ge=0, le=20)
    candidate_support_score: float = Field(ge=0, le=100)
    candidate_support_max_gap: float = Field(ge=0, le=100)


class TargetAlignmentPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^[a-z0-9-]+$")
    costs: AlignmentCosts
    thresholds: AlignmentThresholds

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "TargetAlignmentPolicy":
        if self.thresholds.ambiguous_score >= self.thresholds.target_like_score:
            raise ValueError("ambiguous_score must be below target_like_score")
        if max(
            self.costs.catalog_substitution,
            self.costs.candidate_supported_substitution,
            self.costs.cluster_epenthesis,
        ) >= self.costs.ordinary_substitution:
            raise ValueError("supported transformations must cost less than ordinary substitution")
        return self


@lru_cache(maxsize=1)
def target_alignment_policy() -> TargetAlignmentPolicy:
    return TargetAlignmentPolicy.model_validate_json(
        POLICY_PATH.read_text(encoding="utf-8")
    )


class PhonemeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phoneme: str = Field(min_length=1, max_length=20)
    score: float = Field(ge=0, le=100)


class ObservedPhoneme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phoneme: str = Field(min_length=1, max_length=20)
    word: str = Field(min_length=1, max_length=120)
    word_index: int = Field(ge=0)
    phoneme_index: int = Field(ge=0)
    duration_100ns: int | None = Field(default=None, ge=0)
    candidates: list[PhonemeCandidate] = Field(default_factory=list, max_length=10)


class ExpectedPhoneme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phoneme: str = Field(min_length=1, max_length=20)
    word: str = Field(min_length=1, max_length=120)
    word_index: int = Field(ge=0)
    phoneme_index: int = Field(ge=0)
    word_final: bool = False


class AlignmentOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "exact",
        "catalog_substitution",
        "candidate_supported_substitution",
        "cluster_epenthesis",
        "substitution",
        "insertion",
        "deletion",
    ]
    cost: float = Field(ge=0)
    expected: list[str] = Field(default_factory=list, max_length=4)
    observed: list[str] = Field(default_factory=list, max_length=4)
    expected_word: str | None = Field(default=None, max_length=120)
    expected_word_index: int | None = Field(default=None, ge=0)
    expected_word_final: bool = False
    observed_words: list[str] = Field(default_factory=list, max_length=4)
    pattern_id: str | None = Field(default=None, max_length=100)
    evidence: dict = Field(default_factory=dict)


class TargetAlignmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version: str
    classification: Literal["target_like", "ambiguous", "unrelated"]
    score: float = Field(ge=0, le=1)
    target_coverage: float = Field(ge=0, le=1)
    total_cost: float = Field(ge=0)
    unsupported_changes: int = Field(ge=0)
    expected_count: int = Field(ge=0)
    observed_count: int = Field(ge=0)
    operations: list[AlignmentOperation]


def _candidate_support(
    expected: str,
    observed: ObservedPhoneme,
    policy: TargetAlignmentPolicy,
) -> dict | None:
    candidates = sorted(observed.candidates, key=lambda item: item.score, reverse=True)
    if not candidates:
        return None
    leader = candidates[0]
    expected_candidate = next(
        (item for item in candidates if normalize_phoneme(item.phoneme) == expected),
        None,
    )
    if (
        expected_candidate is None
        or expected_candidate.score < policy.thresholds.candidate_support_score
        or leader.score - expected_candidate.score
        > policy.thresholds.candidate_support_max_gap
    ):
        return None
    return {
        "leading_phoneme": normalize_phoneme(leader.phoneme),
        "leading_score": leader.score,
        "expected_candidate_score": expected_candidate.score,
        "score_gap": leader.score - expected_candidate.score,
    }


def _substitution_operation(
    expected: ExpectedPhoneme,
    observed: ObservedPhoneme,
    policy: TargetAlignmentPolicy,
) -> AlignmentOperation:
    expected_sound = normalize_phoneme(expected.phoneme)
    observed_sound = normalize_phoneme(observed.phoneme)
    shared = {
        "expected": [expected_sound],
        "observed": [observed_sound],
        "expected_word": expected.word,
        "expected_word_index": expected.word_index,
        "expected_word_final": expected.word_final,
        "observed_words": [observed.word],
    }
    if expected_sound == observed_sound:
        return AlignmentOperation(
            kind="exact", cost=policy.costs.exact_match, **shared
        )
    pattern = substitution_pattern(expected_sound, observed_sound)
    if pattern:
        return AlignmentOperation(
            kind="catalog_substitution",
            cost=policy.costs.catalog_substitution,
            pattern_id=pattern.id,
            **shared,
        )
    candidate_evidence = _candidate_support(expected_sound, observed, policy)
    if candidate_evidence:
        return AlignmentOperation(
            kind="candidate_supported_substitution",
            cost=policy.costs.candidate_supported_substitution,
            pattern_id=("final_consonant_weakening" if expected.word_final else None),
            evidence=candidate_evidence,
            **shared,
        )
    return AlignmentOperation(
        kind="substitution", cost=policy.costs.ordinary_substitution, **shared
    )


def _cluster_operation(
    expected: list[ExpectedPhoneme],
    observed: list[ObservedPhoneme],
    i: int,
    j: int,
    policy: TargetAlignmentPolicy,
) -> AlignmentOperation | None:
    if i + 1 >= len(expected) or j + 2 >= len(observed):
        return None
    first_expected = normalize_phoneme(expected[i].phoneme)
    second_expected = normalize_phoneme(expected[i + 1].phoneme)
    first_observed = normalize_phoneme(observed[j].phoneme)
    inserted = normalize_phoneme(observed[j + 1].phoneme)
    final_observed = normalize_phoneme(observed[j + 2].phoneme)
    if (
        first_expected != "s"
        or first_observed != "s"
        or second_expected in IPA_VOWELS
        or inserted not in IPA_VOWELS
        or final_observed != second_expected
        or expected[i].word_index != expected[i + 1].word_index
    ):
        return None
    return AlignmentOperation(
        kind="cluster_epenthesis",
        cost=policy.costs.cluster_epenthesis,
        expected=[first_expected, second_expected],
        observed=[first_observed, inserted, final_observed],
        expected_word=expected[i].word,
        expected_word_index=expected[i].word_index,
        expected_word_final=expected[i + 1].word_final,
        observed_words=list(
            dict.fromkeys(item.word for item in observed[j : j + 3])
        ),
        pattern_id="cluster_epenthesis",
        evidence={
            "inserted_vowel": inserted,
            "inserted_vowel_duration_100ns": observed[j + 1].duration_100ns,
            "cross_word": (
                len({item.word_index for item in observed[j : j + 3]}) > 1
            ),
        },
    )


def align_phonemes_to_target(
    expected: list[ExpectedPhoneme],
    observed: list[ObservedPhoneme],
    *,
    policy: TargetAlignmentPolicy | None = None,
) -> TargetAlignmentResult:
    active_policy = policy or target_alignment_policy()
    n, m = len(expected), len(observed)
    costs = [[float("inf")] * (m + 1) for _ in range(n + 1)]
    steps: list[list[tuple[int, int, AlignmentOperation] | None]] = [
        [None] * (m + 1) for _ in range(n + 1)
    ]
    costs[0][0] = 0.0
    for i in range(1, n + 1):
        operation = AlignmentOperation(
            kind="deletion",
            cost=active_policy.costs.deletion,
            expected=[normalize_phoneme(expected[i - 1].phoneme)],
            expected_word=expected[i - 1].word,
            expected_word_index=expected[i - 1].word_index,
            expected_word_final=expected[i - 1].word_final,
        )
        costs[i][0] = costs[i - 1][0] + operation.cost
        steps[i][0] = (i - 1, 0, operation)
    for j in range(1, m + 1):
        operation = AlignmentOperation(
            kind="insertion",
            cost=active_policy.costs.insertion,
            observed=[normalize_phoneme(observed[j - 1].phoneme)],
            observed_words=[observed[j - 1].word],
        )
        costs[0][j] = costs[0][j - 1] + operation.cost
        steps[0][j] = (0, j - 1, operation)

    for i in range(n + 1):
        for j in range(m + 1):
            if i == 0 and j == 0:
                continue
            options: list[tuple[float, int, int, AlignmentOperation]] = []
            if i and j:
                operation = _substitution_operation(
                    expected[i - 1], observed[j - 1], active_policy
                )
                options.append(
                    (
                        costs[i - 1][j - 1] + operation.cost,
                        i - 1,
                        j - 1,
                        operation,
                    )
                )
            if i:
                operation = AlignmentOperation(
                    kind="deletion",
                    cost=active_policy.costs.deletion,
                    expected=[normalize_phoneme(expected[i - 1].phoneme)],
                    expected_word=expected[i - 1].word,
                    expected_word_index=expected[i - 1].word_index,
                    expected_word_final=expected[i - 1].word_final,
                )
                options.append((costs[i - 1][j] + operation.cost, i - 1, j, operation))
            if j:
                operation = AlignmentOperation(
                    kind="insertion",
                    cost=active_policy.costs.insertion,
                    observed=[normalize_phoneme(observed[j - 1].phoneme)],
                    observed_words=[observed[j - 1].word],
                )
                options.append((costs[i][j - 1] + operation.cost, i, j - 1, operation))
            if i >= 2 and j >= 3:
                operation = _cluster_operation(
                    expected, observed, i - 2, j - 3, active_policy
                )
                if operation:
                    options.append(
                        (
                            costs[i - 2][j - 3] + operation.cost,
                            i - 2,
                            j - 3,
                            operation,
                        )
                    )
            if options:
                best_cost, previous_i, previous_j, operation = min(
                    options, key=lambda item: item[0]
                )
                costs[i][j] = best_cost
                steps[i][j] = (previous_i, previous_j, operation)

    operations: list[AlignmentOperation] = []
    i, j = n, m
    while i or j:
        step = steps[i][j]
        if step is None:
            break
        previous_i, previous_j, operation = step
        operations.append(operation)
        i, j = previous_i, previous_j
    operations.reverse()

    supported_kinds = {
        "exact",
        "catalog_substitution",
        "candidate_supported_substitution",
        "cluster_epenthesis",
    }
    covered = sum(
        len(operation.expected)
        for operation in operations
        if operation.kind in supported_kinds
    )
    unsupported = sum(
        1
        for operation in operations
        if operation.kind in {"substitution", "insertion", "deletion"}
    )
    denominator = max(1, n, m)
    total_cost = costs[n][m] if n or m else 0.0
    score = max(0.0, min(1.0, 1.0 - total_cost / denominator))
    coverage = covered / max(1, n)
    thresholds = active_policy.thresholds
    if (
        score >= thresholds.target_like_score
        and coverage >= thresholds.minimum_target_coverage
        and unsupported <= thresholds.maximum_unsupported_changes
    ):
        classification = "target_like"
    elif (
        score >= thresholds.ambiguous_score
        or coverage >= thresholds.minimum_target_coverage * 0.75
    ):
        classification = "ambiguous"
    else:
        classification = "unrelated"
    return TargetAlignmentResult(
        policy_version=active_policy.version,
        classification=classification,
        score=round(score, 4),
        target_coverage=round(coverage, 4),
        total_cost=round(total_cost, 4),
        unsupported_changes=unsupported,
        expected_count=n,
        observed_count=m,
        operations=operations,
    )

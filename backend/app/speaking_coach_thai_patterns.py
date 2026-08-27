"""Typed runtime access to the Thai-English pronunciation reference catalog."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CATALOG_PATH = Path(__file__).with_name("speaking_coach_thai_patterns.json")


class ThaiPronunciationPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=160)
    category: Literal[
        "final_consonant", "cluster", "substitution", "vowel", "stress", "prosody"
    ]
    contexts: list[str] = Field(min_length=1, max_length=12)
    expected_phonemes: list[str] = Field(default_factory=list, max_length=20)
    likely_substitutions: dict[str, list[str]] = Field(default_factory=dict)
    grapheme_clusters: list[str] = Field(default_factory=list, max_length=20)
    azure_signals: list[str] = Field(min_length=1, max_length=12)
    runtime_support: Literal["active", "partial", "diagnostic_only"]
    priority_weight: int = Field(ge=0, le=20)


class ThaiPronunciationCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_version: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=1, max_length=500)
    learner_feedback_policy: Literal["word_level_only"]
    patterns: list[ThaiPronunciationPattern] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def unique_pattern_ids(self) -> "ThaiPronunciationCatalog":
        ids = [pattern.id for pattern in self.patterns]
        if len(ids) != len(set(ids)):
            raise ValueError("Thai pronunciation pattern IDs must be unique")
        return self


@lru_cache(maxsize=1)
def thai_pronunciation_catalog() -> ThaiPronunciationCatalog:
    return ThaiPronunciationCatalog.model_validate_json(
        CATALOG_PATH.read_text(encoding="utf-8")
    )


@lru_cache(maxsize=1)
def _substitution_index() -> dict[tuple[str, str], ThaiPronunciationPattern]:
    index: dict[tuple[str, str], ThaiPronunciationPattern] = {}
    for pattern in thai_pronunciation_catalog().patterns:
        if pattern.runtime_support not in ("active", "partial"):
            continue
        for expected, spoken_values in pattern.likely_substitutions.items():
            for spoken in spoken_values:
                index.setdefault((expected.lower(), spoken.lower()), pattern)
    return index


def substitution_pattern(
    expected_phoneme: str, spoken_phoneme: str
) -> ThaiPronunciationPattern | None:
    return _substitution_index().get(
        (expected_phoneme.strip().lower(), spoken_phoneme.strip().lower())
    )


def pattern_by_id(pattern_id: str) -> ThaiPronunciationPattern | None:
    return next(
        (
            pattern
            for pattern in thai_pronunciation_catalog().patterns
            if pattern.id == pattern_id
        ),
        None,
    )

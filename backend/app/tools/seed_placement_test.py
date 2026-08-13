#!/usr/bin/env python3
"""Validate and seed placement-test content.

Usage:
  python -m app.tools.seed_placement_test --validate-only
  python -m app.tools.seed_placement_test
  python -m app.tools.seed_placement_test path/to/placement-test.json
"""

import argparse
import json
from pathlib import Path


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "placement-test.json"
VALID_LEVELS = {1, 2, 5, 9, 13}


def load_placement_test(path):
    with Path(path).open("r", encoding="utf-8") as source:
        return json.load(source)


def validate_placement_test(conversations):
    errors = []

    if not isinstance(conversations, list):
        return ["Root must be an array of conversations."]
    if len(conversations) != 3:
        errors.append(f"Expected 3 conversations; found {len(conversations)}.")

    expected_orders = {1, 2, 3}
    actual_orders = set()
    question_ids = set()

    for row_index, conversation in enumerate(conversations):
        label = f"conversations[{row_index}]"
        if not isinstance(conversation, dict):
            errors.append(f"{label} must be an object.")
            continue

        order = conversation.get("conversation_order")
        if not isinstance(order, int):
            errors.append(f"{label}.conversation_order must be an integer.")
        elif order in actual_orders:
            errors.append(f"Duplicate conversation_order: {order}.")
        else:
            actual_orders.add(order)

        expected_audio_path = f"placement_test_{order}.mp3"
        if conversation.get("audio_path") != expected_audio_path:
            errors.append(f"{label}.audio_path must be {expected_audio_path!r}.")

        questions = conversation.get("questions")
        if not isinstance(questions, list) or not questions:
            errors.append(f"{label}.questions must be a non-empty array.")
            questions = []

        for question_index, question in enumerate(questions):
            question_label = f"{label}.questions[{question_index}]"
            if not isinstance(question, dict):
                errors.append(f"{question_label} must be an object.")
                continue

            question_id = question.get("id")
            if not isinstance(question_id, str) or not question_id.strip():
                errors.append(f"{question_label}.id must be a non-empty string.")
            elif question_id in question_ids:
                errors.append(f"Duplicate question id: {question_id!r}.")
            else:
                question_ids.add(question_id)

            if not isinstance(question.get("prompt"), str) or not question["prompt"].strip():
                errors.append(f"{question_label}.prompt must be a non-empty string.")
            if not isinstance(question.get("promptTh"), str) or not question["promptTh"].strip():
                errors.append(f"{question_label}.promptTh must be a non-empty string.")

            choices = question.get("choices")
            if not isinstance(choices, list) or len(choices) != 5:
                errors.append(f"{question_label}.choices must contain exactly 5 choices.")
                choices = []
            elif not all(isinstance(choice, str) and choice.strip() for choice in choices):
                errors.append(f"{question_label}.choices must contain non-empty strings.")

            choices_th = question.get("choicesTh")
            if not isinstance(choices_th, list) or len(choices_th) != 5:
                errors.append(f"{question_label}.choicesTh must contain exactly 5 choices.")
            elif not all(isinstance(choice, str) and choice.strip() for choice in choices_th):
                errors.append(f"{question_label}.choicesTh must contain non-empty strings.")

            correct_choice = question.get("correctChoice")
            if not isinstance(correct_choice, int) or not 0 <= correct_choice < len(choices):
                errors.append(f"{question_label}.correctChoice must be a valid zero-based choice index.")

        rules = conversation.get("scoring_rules")
        if not isinstance(rules, list) or not rules:
            errors.append(f"{label}.scoring_rules must be a non-empty array.")
            rules = []

        covered_scores = set()
        for rule_index, rule in enumerate(rules):
            rule_label = f"{label}.scoring_rules[{rule_index}]"
            if not isinstance(rule, dict):
                errors.append(f"{rule_label} must be an object.")
                continue

            minimum = rule.get("minCorrect")
            maximum = rule.get("maxCorrect")
            if not isinstance(minimum, int) or not isinstance(maximum, int) or minimum > maximum:
                errors.append(f"{rule_label} must have a valid integer score range.")
                continue
            if minimum < 0 or maximum > len(questions):
                errors.append(f"{rule_label} score range is outside 0..{len(questions)}.")

            scores = set(range(minimum, maximum + 1))
            if covered_scores.intersection(scores):
                errors.append(f"{rule_label} overlaps another scoring rule.")
            covered_scores.update(scores)

            has_level = "level" in rule
            has_next = "nextConversation" in rule
            if has_level == has_next:
                errors.append(f"{rule_label} must define exactly one of level or nextConversation.")
            elif has_level and rule["level"] not in VALID_LEVELS:
                errors.append(f"{rule_label}.level is not a valid placement level.")
            elif has_next and rule["nextConversation"] != order + 1:
                errors.append(f"{rule_label}.nextConversation must be {order + 1}.")

        expected_scores = set(range(len(questions) + 1))
        if covered_scores != expected_scores:
            errors.append(f"{label}.scoring_rules must cover every score from 0 to {len(questions)} exactly once.")

    if actual_orders != expected_orders:
        errors.append("conversation_order values must be exactly 1, 2, and 3.")

    return errors


def seed_placement_test(conversations):
    from app.supabase_client import supabase_admin

    payload = [
        {
            "conversation_order": conversation["conversation_order"],
            "audio_path": conversation["audio_path"],
            "questions": conversation["questions"],
            "scoring_rules": conversation["scoring_rules"],
        }
        for conversation in conversations
    ]
    result = (
        supabase_admin.table("placement_conversations")
        .upsert(payload, on_conflict="conversation_order")
        .execute()
    )
    return result.data or []


def main():
    parser = argparse.ArgumentParser(description="Seed placement-test content into Supabase.")
    parser.add_argument("path", nargs="?", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    conversations = load_placement_test(args.path)
    errors = validate_placement_test(conversations)
    if errors:
        print("Placement-test validation failed:")
        for error in errors:
            print(f"  - {error}")
        raise SystemExit(1)

    question_count = sum(len(row["questions"]) for row in conversations)
    print(f"Validated {len(conversations)} conversations and {question_count} questions.")
    if args.validate_only:
        return

    rows = seed_placement_test(conversations)
    print(f"Upserted {len(rows)} placement conversation rows.")


if __name__ == "__main__":
    main()

from pathlib import Path

from app.tools.seed_placement_test import load_placement_test, validate_placement_test


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "placement-test.json"


def test_placement_test_seed_data_is_valid():
    conversations = load_placement_test(DATA_PATH)

    assert validate_placement_test(conversations) == []
    assert [row["conversation_order"] for row in conversations] == [1, 2, 3]
    assert sum(len(row["questions"]) for row in conversations) == 10
    for conversation in conversations:
        for question in conversation["questions"]:
            assert question["choices"][-1] == "I don't know."
            assert question["choicesTh"][-1] == "ไม่รู้"
            assert question["correctChoice"] < 4


def test_validation_rejects_incomplete_score_coverage():
    conversations = load_placement_test(DATA_PATH)
    conversations[0]["scoring_rules"] = [
        {"minCorrect": 0, "maxCorrect": 1, "level": 1}
    ]

    errors = validate_placement_test(conversations)

    assert any("cover every score" in error for error in errors)

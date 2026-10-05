import unittest
from unittest.mock import patch

from app.tools import import_lessons
from app.tools.parser import (
    GoogleDocsParser,
    extract_sections,
    pair_transcript_bilingual,
    split_lessons_by_header,
)


def _paragraph(text=None, *, style="NORMAL_TEXT", runs=None):
    elements = runs or [{"textRun": {"content": f"{text}\n"}}]
    return {
        "paragraph": {
            "elements": elements,
            "paragraphStyle": {"namedStyleType": style},
        }
    }


def _run(text, *, color=None):
    text_style = {}
    if color is not None:
        text_style["foregroundColor"] = {"color": {"rgbColor": color}}
    return {"textRun": {"content": text, "textStyle": text_style}}


def _parse_document(*content, lang="en"):
    document = {"body": {"content": list(content)}, "lists": {}}
    lessons = split_lessons_by_header(extract_sections(document))
    return GoogleDocsParser().build_lesson_from_sections(
        lessons[0], "Beginner", document, lang=lang
    )


class _FakeLessonsQuery:
    def __init__(self):
        self.record = None

    def table(self, name):
        assert name == "lessons"
        return self

    def upsert(self, record, **_kwargs):
        self.record = record
        return self

    def execute(self):
        return type("Response", (), {"data": [{"id": "lesson-id"}]})()


class TranscriptParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = GoogleDocsParser()

    def test_leading_stage_direction_becomes_standalone_row(self):
        rows = self.parser.parse_conversation_from_lines(
            ["*knock knock*", "Pailin: Come in!"]
        )

        self.assertEqual(rows[0]["speaker"], "")
        self.assertEqual(rows[0]["line_text"], "*knock knock*")
        self.assertTrue(rows[0]["_standalone"])
        self.assertEqual(rows[1]["speaker"], "Pailin")
        self.assertEqual(rows[1]["sort_order"], 2)

    def test_ellipsis_between_speakers_becomes_standalone_row(self):
        rows = self.parser.parse_conversation_from_lines(
            ["Pailin: Wait here.", "...", "Luke: Okay."]
        )

        self.assertEqual([row["line_text"] for row in rows], ["Wait here.", "...", "Okay."])
        self.assertEqual(rows[1]["speaker"], "")
        self.assertTrue(rows[1]["_standalone"])

    def test_regular_non_speaker_line_remains_a_continuation(self):
        rows = self.parser.parse_conversation_from_lines(
            ["Pailin: This sentence", "continues here."]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["line_text"], "This sentence continues here.")

    def test_thai_stage_direction_does_not_shift_dialogue_pairing(self):
        parsed = self.parser.parse_conversation_from_lines(
            [
                "*ก็อก ก็อก*",
                "Pailin: Come in!",
                "ไพลิน: เข้ามาเลยค่ะ!",
            ]
        )

        rows = pair_transcript_bilingual(parsed)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["speaker"], "")
        self.assertEqual(rows[0]["line_text"], "")
        self.assertEqual(rows[0]["line_text_th"], "*ก็อก ก็อก*")
        self.assertEqual(rows[1]["speaker"], "Pailin")
        self.assertEqual(rows[1]["speaker_th"], "ไพลิน")
        self.assertEqual(rows[1]["line_text"], "Come in!")
        self.assertEqual(rows[1]["line_text_th"], "เข้ามาเลยค่ะ!")

    def test_standalone_english_and_thai_rows_pair_together(self):
        parsed = self.parser.parse_conversation_from_lines(
            ["*knock knock*", "*ก็อก ก็อก*"]
        )

        [row] = pair_transcript_bilingual(parsed)

        self.assertEqual(row["line_text"], "*knock knock*")
        self.assertEqual(row["line_text_th"], "*ก็อก ก็อก*")

    def test_neutral_ellipsis_does_not_consume_following_speaker(self):
        parsed = self.parser.parse_conversation_from_lines(
            ["…", "Luke: Okay.", "ลูค: โอเคครับ"]
        )

        rows = pair_transcript_bilingual(parsed)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["line_text_th"], "…")
        self.assertEqual(rows[1]["speaker"], "Luke")
        self.assertEqual(rows[1]["speaker_th"], "ลูค")

    def test_short_focus_is_authored_separately_and_imported(self):
        parsed = _parse_document(
            _paragraph("LESSON 1.1: Greetings", style="HEADING_3"),
            _paragraph("FOCUS", style="HEADING_3"),
            _paragraph("How to greet someone"),
            _paragraph("SHORT_FOCUS: greetings"),
        )

        self.assertEqual(parsed["lesson"]["focus"], "How to greet someone")
        self.assertEqual(parsed["lesson"]["focus_short"], "greetings")

        fake = _FakeLessonsQuery()
        with patch.object(import_lessons, "supabase", fake):
            import_lessons.upsert_lesson(parsed, lang="en")
        self.assertEqual(fake.record["focus_short"], "greetings")

    def test_authored_blue_is_normalized_only_in_apply_and_phrases_verbs(self):
        blue = {"blue": 1}
        parsed = _parse_document(
            _paragraph("LESSON 1.1: Greetings", style="HEADING_3"),
            _paragraph("APPLY", style="HEADING_3"),
            _paragraph(runs=[
                _run("Pailin: I’m "),
                _run("not", color=blue),
                _run(" cold.\n"),
            ]),
            _paragraph(runs=[
                _run("RESPONSE: I’m "),
                _run("not", color=blue),
                _run(" tired.\n"),
            ]),
            _paragraph("UNDERSTAND", style="HEADING_3"),
            _paragraph(runs=[_run("Unchanged blue\n", color=blue)]),
            _paragraph("PHRASES & VERBS", style="HEADING_3"),
            _paragraph("LOOK FOR"),
            _paragraph(runs=[
                _run("I’m "),
                _run("looking for", color=blue),
                _run(" my keys.\n"),
            ]),
        )

        sections = {section["type"]: section for section in parsed["sections"]}
        apply_colors = [
            span.get("color")
            for node in sections["apply"]["content_jsonb"]["prompt_nodes"]
            for span in node.get("inlines", [])
        ]
        apply_response_colors = [
            span.get("color")
            for node in sections["apply"]["content_jsonb"]["response_nodes"]
            for span in node.get("inlines", [])
        ]
        phrases_colors = [
            span.get("color")
            for node in sections["phrases_verbs"]["items"][0]["content_jsonb"]
            for span in node.get("inlines", [])
        ]
        understand_colors = [
            span.get("color")
            for node in sections["understand"]["content_jsonb"]
            for span in node.get("inlines", [])
        ]

        self.assertIn("#2563EB", apply_colors)
        self.assertIn("#2563EB", apply_response_colors)
        self.assertIn("#2563EB", phrases_colors)
        self.assertIn("#0000ff", understand_colors)

    def test_thai_phrase_keeps_blue_on_only_the_authored_words(self):
        blue = {"blue": 1}
        parsed = _parse_document(
            _paragraph("LESSON 1.11: I’m from Thailand ฉันมาจากประเทศไทย", style="HEADING_3"),
            _paragraph("PHRASES & VERBS", style="HEADING_3"),
            _paragraph("WOW ว้าว"),
            _paragraph(runs=[
                _run("Wow!", color=blue),
                _run(" This cake is beautiful.\n"),
                _run("ว้าว!", color=blue),
                _run(" เค้กก้อนนี้สวยมากเลย\n"),
            ]),
            lang="th",
        )

        phrase = parsed["sections"][0]["items"][0]
        inlines = phrase["content_jsonb_th"][0]["inlines"]
        colored_text = [span["text"] for span in inlines if span.get("color") == "#2563EB"]
        uncolored_text = [span["text"] for span in inlines if not span.get("color")]

        self.assertEqual(colored_text, ["Wow!", "ว้าว!"])
        self.assertIn(" This cake is beautiful.\n", uncolored_text)
        self.assertIn(" เค้กก้อนนี้สวยมากเลย", uncolored_text)

    def test_practice_priority_preserves_document_order_and_defaults_to_core(self):
        exercises = self.parser.parse_practice([
            "TYPE: multiple_choice",
            "PRACTICE_PRIORITY: core",
            "TITLE: First core exercise",
            "QUESTION: 99",
            "TEXT: First",
            "OPTIONS:",
            "A. Yes",
            "B. No",
            "ANSWER: A",
            "TYPE: multiple_choice",
            "PRACTICE_PRIORITY: extra",
            "TITLE: Extra exercise",
            "QUESTION: 1",
            "TEXT: Second",
            "OPTIONS:",
            "A. Yes",
            "B. No",
            "ANSWER: B",
            "TYPE: open",
            "TITLE: Legacy core exercise",
            "QUESTION: 2",
            "TEXT: Third",
        ])

        self.assertEqual(
            [(exercise["sort_order"], exercise["practice_priority"]) for exercise in exercises],
            [(1, "core"), (2, "extra"), (3, "core")],
        )
        self.assertEqual(exercises[0]["title"], "First core exercise")
        self.assertEqual(exercises[1]["title"], "Extra exercise")


if __name__ == "__main__":
    unittest.main()

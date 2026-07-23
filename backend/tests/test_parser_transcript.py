import unittest

from app.tools.parser import GoogleDocsParser, pair_transcript_bilingual


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


if __name__ == "__main__":
    unittest.main()

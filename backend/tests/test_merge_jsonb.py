import unittest

from app.merge_jsonb import merge_content_nodes


class MergeContentNodesTests(unittest.TestCase):
    def test_thai_bullet_preserves_english_numbered_item_structure(self):
        english = [
            {
                "kind": "paragraph",
                "indent": 0,
                "inlines": [{"text": "Earlier English paragraph"}],
            },
            {
                "kind": "numbered_item",
                "indent": 1,
                "inlines": [{"text": "the US / the USA"}],
            }
        ]
        thai = [
            {
                "kind": "paragraph",
                "indent": 0,
                "inlines": [{"text": "ย่อหน้าภาษาไทยก่อนหน้า"}],
            },
            {
                "kind": "spacer",
                "indent": 0,
                "inlines": [],
            },
            {
                "kind": "list_item",
                "indent": 1,
                "inlines": [{"text": "the U.S. / the U.S.A."}],
                "audio_seq": 1,
                "audio_section": "culture_note",
            }
        ]

        merged = merge_content_nodes(english, thai)

        numbered = next(node for node in merged if node["kind"] == "numbered_item")
        self.assertEqual(numbered["inlines"], thai[2]["inlines"])
        self.assertNotIn("audio_seq", numbered)
        self.assertNotIn("audio_section", numbered)


if __name__ == "__main__":
    unittest.main()

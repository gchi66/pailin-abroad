import unittest

from app.tools.docwalker import paragraph_nodes


def _document_with_list_glyph(*, glyph_type=None, glyph_symbol=None, start_number=None):
    nesting_level = {
        "indentFirstLine": {"magnitude": 18, "unit": "PT"},
        "indentStart": {"magnitude": 36, "unit": "PT"},
    }
    if glyph_type is not None:
        nesting_level["glyphType"] = glyph_type
    if glyph_symbol is not None:
        nesting_level["glyphSymbol"] = glyph_symbol
    if start_number is not None:
        nesting_level["startNumber"] = start_number

    return {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "bullet": {
                            "listId": "test-list",
                            "nestingLevel": 0,
                        },
                        "elements": [
                            {"textRun": {"content": "the U.S. / the U.S.A.\n"}}
                        ],
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    }
                }
            ]
        },
        "lists": {
            "test-list": {
                "listProperties": {"nestingLevels": [nesting_level]}
            }
        },
    }


class ParagraphNodesTests(unittest.TestCase):
    def test_unspecified_glyph_type_without_symbol_is_numbered(self):
        document = _document_with_list_glyph(
            glyph_type="GLYPH_TYPE_UNSPECIFIED"
        )

        [node] = paragraph_nodes(document)

        self.assertEqual(node.kind, "numbered_item")

    def test_glyph_symbol_remains_a_bullet(self):
        document = _document_with_list_glyph(glyph_symbol="●")

        [node] = paragraph_nodes(document)

        self.assertEqual(node.kind, "list_item")

    def test_native_list_metadata_is_preserved(self):
        document = _document_with_list_glyph(
            glyph_type="DECIMAL", start_number=3
        )

        [node] = paragraph_nodes(document)

        self.assertEqual(node.list_id, "test-list")
        self.assertEqual(node.list_nesting_level, 0)
        self.assertEqual(node.list_start_number, 3)


if __name__ == "__main__":
    unittest.main()

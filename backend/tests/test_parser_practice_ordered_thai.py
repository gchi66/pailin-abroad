from app.tools.parser import GoogleDocsParser


def _tokens(item):
    return item["content"]["blocks"][0]["tokens"]


def test_non_quick_thai_sentence_transform_preserves_authored_bilingual_order():
    parser = GoogleDocsParser()
    exercises = parser.parse_practice(
        [
            "TYPE: sentence_transform",
            "TITLE: GIVING SUGGESTIONS",
            "ITEM: 1",
            "STEM: How about we see a movie tonight?\u000bพวกเราไปดูหนังกันคืนนี้ดีไหมล่ะ?",
            "ANSWER: We could see a movie tonight.",
        ],
        lang="th",
    )

    [exercise] = exercises
    [item] = exercise["items_th"]
    assert exercise["thai_document_content_version"] == 1
    assert _tokens(item) == [
        {"type": "text", "text": "How about we see a movie tonight?"},
        {"type": "line_break"},
        {"type": "text", "text": "พวกเราไปดูหนังกันคืนนี้ดีไหมล่ะ?"},
    ]


def test_ordered_fill_blank_uses_underscores_but_does_not_treat_em_dash_as_blank():
    parser = GoogleDocsParser()
    exercises = parser.parse_practice(
        [
            "TYPE: fill_blank",
            "TITLE: I HEARD",
            "ITEM: 1",
            "TEXT: The news said prices will rise.\u000bYou tell your coworker: _________",
            "ข่าวบอกว่าราคาจะสูงขึ้น\u000bคุณบอกเพื่อนร่วมงานของคุณว่า: —",
            "ANSWER: I heard prices will rise.",
        ],
        lang="th",
    )

    [item] = exercises[0]["items_th"]
    tokens = _tokens(item)
    assert [token["type"] for token in tokens].count("blank") == 1
    assert {"type": "blank", "id": "b1", "min_len": 9} in tokens
    assert any(token.get("text", "").endswith(": —") for token in tokens)


def test_ordered_content_is_not_added_to_quick_or_image_practices():
    parser = GoogleDocsParser()
    quick = parser.parse_practice(
        [
            "TYPE: open",
            "TITLE: QUICK PRACTICE - QUESTIONS",
            "ITEM: 1",
            "TEXT: What happened?\u000bเกิดอะไรขึ้น?",
        ],
        lang="th",
    )[0]
    image = parser.parse_practice(
        [
            "TYPE: open",
            "TITLE: IMAGE PRACTICE",
            "ITEM: 1",
            "TEXT: What do you see? [img:practice-1]\u000bคุณเห็นอะไร?",
        ],
        lang="th",
    )[0]

    assert "thai_document_content_version" not in quick
    assert all("content" not in item for item in quick["items_th"])
    assert "thai_document_content_version" not in image
    assert all("content" not in item for item in image["items_th"])


def test_ordered_content_keeps_all_source_items_when_legacy_items_th_would_drop_one():
    parser = GoogleDocsParser()
    exercise = parser.parse_practice(
        [
            "TYPE: sentence_transform",
            "TITLE: TRANSFORM THESE",
            "ITEM: 1",
            "TEXT: English-only source item",
            "ANSWER: First answer",
            "ITEM: 2",
            "TEXT: English second\u000bไทยลำดับที่สอง",
            "ANSWER: Second answer",
        ],
        lang="th",
    )[0]

    assert len(exercise["items"]) == 2
    assert len(exercise["items_th"]) == 2
    assert _tokens(exercise["items_th"][0]) == [
        {"type": "text", "text": "English-only source item"}
    ]


def test_ordered_content_preserves_full_inline_style_payload():
    parser = GoogleDocsParser()
    style = {
        "bold": True,
        "italic": True,
        "underline": True,
        "link": "https://example.com",
        "highlight": "#d9ead3",
        "color": "#123456",
    }
    text = "English\nไทย"
    exercise = parser.parse_practice(
        [
            "TYPE: open",
            "TITLE: STYLED",
            "ITEM: 1",
            f"TEXT: {text}",
        ],
        lang="th",
        node_lookup={
            "English ไทย": [{"inlines": [{"text": text, **style}]}],
            "English": [{"inlines": [{"text": "English", **style}]}],
            "ไทย": [{"inlines": [{"text": "ไทย", **style}]}],
        },
    )[0]

    tokens = _tokens(exercise["items_th"][0])
    styled_tokens = [token for token in tokens if token["type"] == "text"]
    assert styled_tokens
    assert all(token.get("style") == style for token in styled_tokens)

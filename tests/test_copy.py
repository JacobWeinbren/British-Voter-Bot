"""House-style checks on every piece of fixed copy: UK spelling, plain hyphens, sentences."""

import re

import pytest

from voterbot import codes, items

US_SPELLINGS = re.compile(
    r"\b(color|favorite|center|organization|neighbor|labor|defense|realize|analyze|honor|gray|traveled|fulfill|skeptic|mom)\b",
    re.IGNORECASE,
)


def every_phrase():
    """Yield every sentence the item library can produce."""
    for item in items.ITEMS:
        if item.phrase is None:
            continue
        for code in list(range(0, 11)) + [25, 40, 60, 75, 100]:
            text = item.phrase(code)
            for option in (text if isinstance(text, tuple) else (text,)):
                if option:
                    yield item.key, option


@pytest.mark.parametrize("key,text", list(every_phrase()))
def test_item_sentence_style(key, text):
    assert "—" not in text and "–" not in text, f"{key}: use a plain hyphen"
    assert not US_SPELLINGS.search(text), f"{key}: US spelling"
    assert text[0].isupper(), f"{key}: sentence should start with a capital"
    assert text.endswith((".", "?", "!")), f"{key}: sentence should end with a full stop"
    assert len(text) <= 110, f"{key}: too long for a bubble ({len(text)} chars)"
    assert "  " not in text


def test_topics_are_varied():
    topics = {item.topic for item in items.ITEMS}
    assert len(topics) >= 60


def test_every_item_has_a_source_column_or_custom_logic():
    for item in items.ITEMS:
        assert item.cols or item.custom, item.key
        if item.cols:
            assert all(re.search(r"W\d+", c) or c.startswith("p_") for c in item.cols), item.key


def test_top_issue_phrases_read_after_my_top_issue_is():
    for code, phrase in codes.TOP_ISSUE.items():
        assert phrase[0].islower() or phrase.startswith(("Britain", "Brexit", "Scottish", "Covid")), (code, phrase)
        assert "—" not in phrase


def test_nssec_covers_every_working_category():
    for code in (10, 20, 31, 32, 33, 34, 41, 42, 43, 44, 50, 60, 71, 72, 73, 74, 81, 82, 91, 92, 100,
                 111, 112, 121, 122, 123, 124, 125, 126, 127, 131, 132, 133, 134, 135):
        assert code in codes.NSSEC_JOB

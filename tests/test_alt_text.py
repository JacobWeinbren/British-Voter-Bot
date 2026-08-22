"""Alt text follows WCAG 1.1.1: complete, not duplicating the post text, within Bluesky's limit."""

from voterbot.profile import ALT_TEXT_LIMIT, alt_text, post_text, scale_description

PROFILE = {
    "nation": "Scotland",
    "constituency": "Glasgow North",
    "constituency_code": "S14000085",
    "headline": {"template": "I'm a {ethnicity} {religion} {gender} from {place}, aged {age}.",
                 "bold": {"ethnicity": "White Scottish", "religion": "non-religious", "gender": "woman",
                          "place": "Glasgow North", "age": "34"}},
    "life": {"template": "I rent privately. I work full-time and have a semi-routine service job (care work etc.). I'd call myself {class_id}.",
             "bold": {"class_id": "working class"}},
    "media": {"template": "I mostly follow politics on TV, a few minutes a day. I use {platform0}.", "bold": {"platform0": "Facebook"}},
    "top_issue": "the cost of living",
    "bubbles": [
        {"template": "My favourite leader is {best}. My least favourite is {worst}.", "bold": {"best": "John Swinney", "worst": "Nigel Farage"}},
        {"template": "Ordinary working people don't get their fair share of the nation's wealth.", "bold": {}},
        {"template": "Cuts to NHS spending have gone too far.", "bold": {}},
        {"template": "I feel more Scottish than British.", "bold": {}},
    ],
    "econ_pct": 20.0, "cultural_pct": 50.0, "econ_score10": 2.0, "cultural_score10": 5.0,
    "econ_iqr": [15.0, 42.0], "cultural_iqr": [50.0, 80.0],
    "band_text": "In 2024 I voted Labour. Today I'd vote SNP*", "intention_party": "SNP",
}


def test_alt_text_is_within_the_platform_limit_and_reads_as_a_description():
    text = alt_text(PROFILE)
    assert len(text) <= ALT_TEXT_LIMIT
    assert text.startswith("Voter card.")
    assert not text.lower().startswith(("image of", "picture of", "graphic of"))


def test_alt_text_does_not_repeat_the_post_text():
    alt = alt_text(PROFILE)
    for sentence in post_text(PROFILE).split(". "):
        assert sentence.rstrip(".") not in alt, sentence


def test_alt_text_carries_what_only_the_image_shows():
    alt = alt_text(PROFILE)
    assert "map of Scotland with a dot on Glasgow North" in alt
    assert "John Swinney" in alt and "care work etc." in alt and "Facebook" in alt
    assert "economic, left to right, 2 out of 10, within the middle half of voters" in alt
    assert "cultural, liberal to authoritarian, 5 out of 10, within the middle half of voters" in alt


def test_scale_description_reads_the_marker_against_median_and_band():
    assert scale_description(8.0, 80.0, [40.0, 60.0], "further left than", "further right than") == "8 out of 10, further right than the middle half of voters"
    assert scale_description(5.2, 52.0, [40.0, 60.0], "further left than", "further right than") == "5.2 out of 10, within the middle half of voters"


def test_alt_text_never_exceeds_limit_even_with_long_copy():
    long_profile = dict(PROFILE)
    long_profile["life"] = {"template": "x" * 1500, "bold": {}}
    long_profile["media"] = {"template": "y" * 400, "bold": {}}
    assert len(alt_text(long_profile)) <= ALT_TEXT_LIMIT

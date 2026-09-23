"""What the card does with the space it is given.

A respondent who skipped the value batteries has no scales to draw. The section stays - it
says why it is empty - and the map grows into the height the scales would have taken, so the
card reads as finished rather than as one with a hole in it.
"""

import copy

from voterbot import config
from voterbot.render import build_html, map_box

from test_alt_text import PROFILE

CARD = dict(PROFILE, country=2, possessive="her", footnote="Voting intention", alt_text="Voter card.",
            no_single_issue=False)
NO_SCALES = dict(copy.deepcopy(CARD), econ_pct=None, cultural_pct=None, econ_score10=None, cultural_score10=None)


def test_a_card_with_scales_keeps_the_handoff_map():
    assert map_box(CARD) == (config.MAP_WIDTH, config.MAP_HEIGHTS[2])


def test_a_card_without_scales_grows_its_map_into_the_space():
    width, height = map_box(NO_SCALES)
    assert width == round(config.MAP_WIDTH * config.MAP_SCALE_WITHOUT_SCALES)
    assert height == round(config.MAP_HEIGHTS[2] * config.MAP_SCALE_WITHOUT_SCALES)


def test_a_card_without_scales_says_why_rather_than_leaving_a_gap():
    page = build_html(NO_SCALES)
    assert "Where I sit" in page
    assert "enough of the questions that place people on the economic and social scales" in page
    assert "middle half of voters" not in page  # no legend for scales that are not there


def test_a_card_with_scales_draws_them_and_no_apology():
    page = build_html(CARD)
    assert "middle half of voters" in page
    assert "enough of the questions" not in page

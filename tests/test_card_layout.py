"""What the card does with the space it is given.

A respondent who skipped the value batteries has no scales to draw. The section stays - it
says why it is empty - and the map grows into the height the scales would have taken, so the
card reads as finished rather than as one with a hole in it.

The card is also only the design it was drawn as if its typeface actually loads: for months
every card went out in the system sans-serif because Chromium would not read the fonts from
file:// links, and nothing said so. The checks at the end render in Chromium to catch that.
"""

import copy
import re

import pytest

from voterbot import config, geo
from voterbot.brand import intro_html
from voterbot.render import CHROMIUM_ARGS, build_html, map_box, vote_steps
from voterbot.sample import load_profiles

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


# ---------------------------------------------------------------------------
# The map: the nation fills its box, and every seat's dot lands on it


@pytest.mark.parametrize("country", [1, 2, 3])
def test_the_nation_is_drawn_to_the_edge_of_its_box(country):
    """Fitted to the islands it draws, not to rocks it then drops: one side reaches the inset."""
    width, height = config.MAP_WIDTH, config.MAP_HEIGHTS[country]
    path, _ = geo.nation_path(country, width, height)
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", path)]
    xs, ys = numbers[0::2], numbers[1::2]
    inset, slack = 8, 3  # Projection's inset; simplification may drop an extreme point or two
    assert max(xs) - min(xs) >= width - 2 * inset - slack or max(ys) - min(ys) >= height - 2 * inset - slack


@pytest.mark.parametrize("country", [1, 2, 3])
def test_every_seat_dot_lands_inside_its_nation_box(country):
    width, height = config.MAP_WIDTH, config.MAP_HEIGHTS[country]
    _, proj = geo.nation_path(country, width, height)
    prefix = geo.NATION_CODES[country][0]
    for code, seat in geo.constituencies().items():
        if code.startswith(prefix):
            x, y = proj(seat.lon, seat.lat)
            assert 0 <= x <= width and 0 <= y <= height, seat.name


def test_a_dot_on_the_coast_draws_past_the_edge_rather_than_being_cut_off():
    """Great Yarmouth's dot sits within its own radius of the box edge."""
    code = next(c for c, seat in geo.constituencies().items() if seat.name == "Great Yarmouth")
    assert 'overflow="visible"' in geo.nation_svg(1, code)


# ---------------------------------------------------------------------------
# The typeface


def test_the_card_carries_its_fonts_inside_the_page():
    page = build_html(CARD)
    assert "file://" not in page
    assert page.count("data:font/ttf;base64,") == len(config.FONT_WEIGHTS)


@pytest.fixture(scope="module")
def chromium():
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        pw = sync_api.sync_playwright().start()
        browser = pw.chromium.launch(args=CHROMIUM_ARGS)
    except Exception as error:  # no browser installed here
        pytest.skip(f"Chromium unavailable: {error}")
    yield browser
    browser.close()
    pw.stop()


def settled(browser, html: str):
    page = browser.new_page(viewport={"width": config.CARD_WIDTH, "height": config.CARD_HEIGHT})
    page.set_content(html, wait_until="load")
    page.evaluate("document.fonts.ready")
    page.wait_for_function("document.body.dataset.fit !== 'pending'")  # the card's fit script has run
    return page


@pytest.mark.parametrize("make", [lambda: build_html(CARD), lambda: intro_html(31392)], ids=["card", "intro poster"])
def test_every_archivo_weight_loads_in_chromium(chromium, make):
    page = settled(chromium, make())
    assert page.evaluate("[...document.fonts].map(f => f.status)") == ["loaded"] * len(config.FONT_WEIGHTS)
    assert page.evaluate("document.fonts.check('800 32px Archivo')")
    page.close()


# ---------------------------------------------------------------------------
# The vote band: 2024 on the left, today on the right, each in its own colour


def steps(band_text, party=None):
    return vote_steps({"band_text": band_text, "intention_party": party})


def test_a_switch_shows_both_sides_in_their_own_colours():
    vote = steps("In 2024 I didn't vote. Today I'd vote Labour*", "Labour")
    assert (vote["then"], vote["now"], vote["note"]) == ("Didn't vote", "Labour", "")
    assert (vote["then_bg"], vote["then_ink"]) == config.NO_VOTE_COLOURS
    assert (vote["now_bg"], vote["now_ink"]) == config.PARTY_COLOURS["Labour"]


def test_staying_put_says_still():
    assert steps("In 2024 I voted Conservative. Today I still would*", "Conservative")["now"] == "Still Conservative"
    assert steps("In 2024 I voted for a smaller party. Today I still would*")["now"] == "Still a smaller party"


@pytest.mark.parametrize("band_text,then,now,note", [
    ("I can't remember how I voted in 2024. Today I'd vote Green (if pushed)*", "Can't remember", "Green", "if pushed"),
    ("I'm not sure whether I voted in 2024. Today I'd vote for a smaller party*", "Not sure I voted", "A smaller party", ""),
    ("In 2024 I voted for an independent. Today I don't know who I'd vote for*", "An independent", "Don't know", ""),
    ("In 2024 I voted Reform UK. Today I wouldn't vote*", "Reform UK", "Wouldn't vote", ""),
    ("In 2024 I didn't vote. Today I wouldn't either*", "Didn't vote", "Still wouldn't vote", ""),
    ("In 2024 I didn't vote. Today I wouldn't either, but I'm an SNP supporter*", "Didn't vote", "Still wouldn't vote", "an SNP supporter"),
    ("In 2024 I didn't vote. Today I wouldn't either - at a push, I'm closest to Green*", "Didn't vote", "Still wouldn't vote", "closest to Green"),
])
def test_every_kind_of_vote_line_becomes_two_short_steps(band_text, then, now, note):
    vote = steps(band_text)
    assert (vote["then"], vote["now"], vote["note"]) == (then, now, note)


def test_a_vote_line_it_does_not_recognise_stops_the_render():
    with pytest.raises(ValueError):
        steps("In 2024 I voted by carrier pigeon. Today I'd vote Labour*")


@pytest.mark.skipif(not config.PROFILES_PATH.exists(), reason="no queue built")
def test_every_queued_vote_line_can_be_drawn():
    for card in load_profiles():
        vote_steps(card)  # raises on anything it would have to guess at


def test_the_longest_vote_labels_fit_their_half_of_the_band(chromium):
    card = dict(CARD, band_text="I'm not sure whether I voted in 2024. Today I wouldn't vote*", intention_party=None)
    page = settled(chromium, build_html(card))
    clipped = page.evaluate("[...document.querySelectorAll('.journey .who')].filter(el => el.scrollWidth > el.clientWidth).length")
    assert clipped == 0
    page.close()

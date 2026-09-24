"""The card never shrinks its text: every card is composed to fit at its design sizes instead.

Small type on a phone is the one thing a card cannot afford. The page's fit script only ever grows
the views into spare room, and the build lays every card out in Chromium at the design sizes and
leaves optional copy off any that would run past its canvas (voterbot/fit.py, profile.TRIMS).
These tests hold both halves to that: the page never makes text smaller, the renderer refuses a card
that does not fit rather than post it clipped, and the queue is made of cards that fit.
"""

import copy
import random

import pytest

from voterbot import config, fit
from voterbot.profile import TRIMS, ProfileBuilder
from voterbot.render import build_html, render_png
from voterbot.sample import build_profiles, load_profiles, read_position

from synthetic_panel import synthetic_panel
from test_card_layout import CARD, settled

DESIGN = {".bubble": 22, ".life": 22, ".media": 19, ".headline": 40}
SIZES = "sel => Object.fromEntries(sel.map(s => [s, parseFloat(getComputedStyle(document.querySelector(s)).fontSize)]))"


def with_life(sentences: int) -> dict:
    card = copy.deepcopy(CARD)
    card["life"]["template"] += " I've lived in the same street for most of my life." * sentences
    return card


OVERLONG = with_life(12)


@pytest.fixture
def measure():
    """A measuring page, per test: a sync Playwright session left open would stop the renderer starting its own."""
    try:
        measurer = fit.Measurer().__enter__()
    except Exception as error:  # no browser installed here
        pytest.skip(f"Chromium unavailable: {error}")
    yield measurer
    measurer.__exit__(None, None, None)


@pytest.fixture
def chromium_installed():
    try:
        with fit.Measurer():
            pass
    except Exception as error:
        pytest.skip(f"Chromium unavailable: {error}")


def test_a_card_that_fits_keeps_every_line_at_its_design_size_or_larger(measure):
    page = settled(measure.browser, build_html(CARD))
    assert page.evaluate("document.body.dataset.fit") == "done"
    sizes = page.evaluate(SIZES, list(DESIGN))
    assert all(sizes[s] >= px for s, px in DESIGN.items()), sizes
    page.close()


def test_a_card_that_runs_over_keeps_its_text_at_design_size_and_says_so(measure):
    page = settled(measure.browser, build_html(OVERLONG))
    assert page.evaluate("document.body.dataset.fit") == "overflow"
    assert page.evaluate(SIZES, list(DESIGN)) == DESIGN
    page.close()


def test_a_card_a_little_over_closes_up_its_gaps_rather_than_its_text(measure):
    """The allowance for a machine that lays a line out a hair wider than the one that built the queue."""
    n = 0
    while measure.room(with_life(n)) >= 0:
        n += 1
    assert -36 < measure.room(with_life(n)) < 0  # one line more than fits, within what closing the gaps gives back
    page = settled(measure.browser, build_html(with_life(n)))
    assert page.evaluate("document.body.dataset.fit") == "done"
    assert page.evaluate(SIZES, list(DESIGN)) == DESIGN
    page.close()


def test_the_fullest_card_that_fits_still_keeps_clear_of_the_vote_band(measure):
    """The blocks may run into the padding above the band, never nearer it than BAND_CLEARANCE, so
    the scale labels do not sit on the band - growing views included."""
    n = 0
    while measure.fits(with_life(n + 1)):
        n += 1
    page = settled(measure.browser, build_html(with_life(n)))
    gap = page.evaluate("document.querySelector('.journey').getBoundingClientRect().top"
                        " - document.getElementById('content').lastElementChild.getBoundingClientRect().bottom")
    assert gap >= config.BAND_CLEARANCE - 0.5
    page.close()


def test_the_renderer_refuses_a_card_that_runs_over(chromium_installed, tmp_path):
    with pytest.raises(RuntimeError, match="runs past its canvas"):
        render_png(OVERLONG, tmp_path / "card.png")
    assert not (tmp_path / "card.png").exists()


def test_the_measure_agrees_with_the_card(measure):
    for card, verdict in ((CARD, "done"), (OVERLONG, "overflow")):
        page = settled(measure.browser, build_html(card))
        assert page.evaluate("document.body.dataset.fit") == ("done" if measure.fits(card) else "overflow") == verdict
        page.close()


# ---------------------------------------------------------------------------
# The build


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel()


def plain(span):
    return span["template"].format(**span["bold"]) if span else ""


def test_leaving_copy_off_changes_nothing_else_on_the_card(panel):
    """Each level leaves off more of what the level before showed - never a line it had no room for -
    and the bubbles, headline and vote stay as drawn. Row 381 with seed 2670 once swapped a detail in."""
    builder = ProfileBuilder(panel)
    compared = shortened = shared_dropped = 0
    for k, seed in [(k, k) for k in range(300)] + [(k, 7 * k + 3) for k in range(300, 1000)] + [(381, 2670)]:
        full = builder.build(panel.iloc[k], seed=seed)
        if full is None:
            continue
        compared += 1
        before = full
        for trim in range(1, len(TRIMS)):
            cut = builder.build(panel.iloc[k], seed=seed, trim=trim)
            assert (cut["bubbles"], cut["headline"], cut["band_text"]) == (full["bubbles"], full["headline"], full["band_text"])
            assert all(s.lower() in plain(before["life"]).lower() for s in plain(cut["life"]).split(". "))
            assert plain(before["media"]).startswith(plain(cut["media"]))
            before = cut
        without_shared = builder.build(panel.iloc[k], seed=seed, trim=1)
        if plain(without_shared["media"]) != plain(full["media"]):
            shared_dropped += 1
            assert "political" in plain(full["media"])[len(plain(without_shared["media"])):]  # that line and no other
        shortened += plain(cut["life"]) != plain(full["life"])
    assert compared > 700 and shortened > 0 and shared_dropped > 0


class Fussy:
    """A stand-in measure: a card fits only once it has left off `need` levels of copy."""

    def __init__(self, need: int):
        self.need = need

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def room(self, card):
        return 1.0 if card.get("trim", 0) >= self.need else -5.0

    def fits(self, card):
        return self.room(card) >= 0


def test_a_card_that_does_not_fit_is_composed_again_with_less(panel, monkeypatch, tmp_path):
    drawn = build_profiles(panel, count=30, position=0, verbose=False, out_path=tmp_path / "a.jsonl.gz", fit=False)
    monkeypatch.setattr(fit, "Measurer", lambda: Fussy(2))
    fitted = build_profiles(panel, count=30, position=0, verbose=False, out_path=tmp_path / "b.jsonl.gz")
    assert {c["trim"] for c in fitted} == {2}
    assert [c["seq"] for c in fitted] == list(range(30))
    assert [(c["id"], c["bubbles"]) for c in fitted] == [(c["id"], c["bubbles"]) for c in drawn]


def test_the_build_stops_rather_than_queue_a_card_that_cannot_fit(panel, monkeypatch, tmp_path):
    monkeypatch.setattr(fit, "Measurer", lambda: Fussy(len(TRIMS)))
    with pytest.raises(RuntimeError, match="do not fit"):
        build_profiles(panel, count=5, position=0, verbose=False, out_path=tmp_path / "q.jsonl.gz")
    assert not (tmp_path / "q.jsonl.gz").exists()


def test_a_built_queue_fits_at_design_size(chromium_installed, panel, tmp_path):
    cards = build_profiles(panel, count=200, position=0, verbose=False, out_path=tmp_path / "q.jsonl.gz")
    with fit.Measurer() as measure:
        assert all(measure.fits(c) for c in cards)


@pytest.mark.skipif(not config.PROFILES_PATH.exists(), reason="no queue built")
def test_the_cards_still_to_post_fit_at_design_size(measure):
    """The next thousand cards, every card the build had to trim, and a sample of the rest."""
    cards = load_profiles()
    if any(c.get("generator") != config.GENERATOR for c in cards):
        pytest.skip("the queue predates this generator: rebuild it to measure")
    ahead = cards[read_position():]
    check = ahead[:1000] + [c for c in ahead if c.get("trim")] + random.Random(0).sample(ahead, min(500, len(ahead)))
    assert [c["seq"] for c in check if not measure.fits(c)] == []


# ---------------------------------------------------------------------------
# Posting: a card that would not fit is passed over, never posted shrunk or clipped


def post_with(monkeypatch, tmp_path, refused: set[str]):
    import types

    from voterbot import bluesky, cli, render, sample, schedule

    cards = [{"post_text": f"card {i}", "alt_text": "Voter card.", "constituency": f"Seat {i}"} for i in range(6)]
    posted, positions = [], []

    def fake_render(profile, out):
        if profile["post_text"] in refused:
            raise render.CardOverflow("runs past its canvas")
        return out, out.with_suffix(".webp")

    monkeypatch.setattr(sample, "load_profiles", lambda: cards)
    monkeypatch.setattr(sample, "read_position", lambda: 1)
    monkeypatch.setattr(sample, "write_position", positions.append)
    monkeypatch.setattr(schedule, "write_last_post", lambda when: None)
    monkeypatch.setattr(render, "render_card", fake_render)
    monkeypatch.setattr(bluesky, "post_card", lambda text, webp, alt, fallback_path: posted.append(text) or "at://post")
    monkeypatch.setattr(config, "CARDS_DIR", tmp_path)
    cli.cmd_post(types.SimpleNamespace(dry_run=False))
    return posted, positions


def test_a_card_that_will_not_fit_is_passed_over_and_the_next_one_posted(monkeypatch, tmp_path):
    assert post_with(monkeypatch, tmp_path, {"card 1"}) == (["card 2"], [3])


def test_posting_stops_when_card_after_card_will_not_fit(monkeypatch, tmp_path):
    with pytest.raises(SystemExit):
        post_with(monkeypatch, tmp_path, {"card 1", "card 2", "card 3"})

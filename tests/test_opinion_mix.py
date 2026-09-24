"""What decides which views and details reach a card, beyond what the respondent answered.

A card draws from the questions its respondent was asked, so left flat the feed fills up with
whatever the BES puts to everyone, and with whatever subject the library happens to split into the
most questions. The build solves the draw weights instead (voterbot/balance.py): each theme gets a
target share - half by what voters in that nation say matters most, half evenly - and the weights
are fitted per nation over the whole panel, within a cap on how often any one answer appears.
These tests run a whole build on a made-up panel (tests/synthetic_panel.py) and check what reaches
the cards, not just the arithmetic.
"""

import collections
import random

import numpy as np
import pytest

from voterbot import balance, config, items, persona
from voterbot.profile import DRAWS, ProfileBuilder, strengths, tail_cut
from voterbot.sample import build_profiles

from synthetic_panel import synthetic_panel


@pytest.fixture(scope="module")
def panel():
    return synthetic_panel()


@pytest.fixture(scope="module")
def builder(panel):
    return ProfileBuilder(panel)


def theme_totals(solved, which):
    totals = collections.Counter()
    for key, share in zip(solved["keys"], solved[which]):
        totals[items.theme_of(items.ITEMS[[i.key for i in items.ITEMS].index(key)].topic)] += share
    return totals


# ---------------------------------------------------------------------------
# The opinion draw


def test_the_general_draw_hits_its_targets_in_every_nation(builder):
    for country in (1, 2, 3):
        solved = builder.solved[(country, "general")]
        assert np.abs(solved["shares"] - solved["targets"]).max() < 1e-4, country


def test_a_subject_split_into_many_questions_no_longer_outweighs_the_rest(builder):
    """Five value-battery items put to nearly everyone would take a third of a flat draw; now their theme takes its target."""
    solved = builder.solved[(1, "general")]
    flat, share = theme_totals(solved, "flat")["inequality"], theme_totals(solved, "shares")["inequality"]
    assert flat > 0.3
    assert share < flat / 2


def test_a_question_few_were_asked_is_lifted_but_only_to_the_cap(builder):
    solved = builder.solved[(1, "general")]
    shares, flat = theme_totals(solved, "shares"), theme_totals(solved, "flat")
    assert shares["monarchy"] > flat["monarchy"]  # asked of 15%: lifted
    rate = balance.per_draw_rate(config.MAX_APPEARANCE, DRAWS["general"])
    offered = np.array([solved["offered"][k] for k in solved["keys"]])
    assert (solved["shares"] / offered).max() <= rate + 1e-6  # and nothing past the cap


def test_what_voters_name_as_most_important_gets_more_airtime(builder):
    """The synthetic panel names immigration twice as often as anything else."""
    targets = theme_totals(builder.solved[(1, "general")], "targets")
    assert targets["immigration"] == max(targets.values())
    assert builder.salience[1]["immigration"] > builder.salience[1]["environment"]


def test_a_nation_only_question_is_measured_among_that_nation_alone(builder):
    """Asked of 95% of Scots, it must count as 95% available in Scotland - not 11%, its share of all of Britain."""
    scottish = builder.solved[(2, "nation")]["offered"]
    assert scottish["scotIndy"] == pytest.approx(0.95, abs=0.05)
    assert (1, "nation", "scotIndy") not in builder.weights  # never measured, never weighted, in England


def test_a_middling_answer_is_still_held_back(builder):
    """The fence-sitting penalty survives the solved weights: within one person's pool it still counts a fifth."""
    fence, view = items.middling("Taxes should stay about where they are."), "Taxes should come down a lot."
    item = items.ITEMS[[i.key for i in items.ITEMS].index("taxSpend")]
    picks = collections.Counter()
    stub = ProfileBuilder.__new__(ProfileBuilder)
    stub.weights = {}
    original = items.candidate_statements
    try:
        for seed, text in enumerate([fence, view] * 400):
            items.candidate_statements = lambda row, country, rng=None, text=text: [
                (item, text), (items.ITEMS[[i.key for i in items.ITEMS].index("immigSelf")], "Fewer immigrants, please.")]
            spans, _ = stub.pick_opinions(None, 1, random.Random(seed), None, count=1)
            picks[(text is fence, spans[0].template == str(text))] += 1
    finally:
        items.candidate_statements = original
    middling_rate = picks[(True, True)] / (picks[(True, True)] + picks[(True, False)])
    view_rate = picks[(False, True)] / (picks[(False, True)] + picks[(False, False)])
    assert middling_rate < view_rate / 2


def test_each_middle_answer_is_marked_where_it_is_written():
    """A phrase list used to decide this, and missed two of the three Israel-Palestine middles among others."""
    for key, code in (("israelPalestine", 3), ("nationaliseUtilities", 3), ("taxSpend", 5), ("welfare", 3), ("devoPrefWales", 3)):
        item = items.ITEMS[[i.key for i in items.ITEMS].index(key)]
        wordings = item.phrase(code)
        assert all(items.is_neutral(t) for t in (wordings if isinstance(wordings, tuple) else (wordings,))), key


def test_a_rare_answer_appears_on_no_more_than_about_half_its_cards(panel, builder):
    """Simulated: the zero-hours question (3% of the panel) is lifted, but not onto every card of those who answered it."""
    rows = [row for _, row in panel.iterrows() if not np.isnan(row["zeroHourContractW27"]) and row["countryW31"] == 1][:40]
    shown = 0
    for n, row in enumerate(rows * 10):
        spans, _ = builder.pick_opinions(row, 1, random.Random(n), None, count=config.MAX_OPINIONS)
        shown += any("zero-hours" in s.template for s in spans)
    assert shown / (len(rows) * 10) <= config.MAX_APPEARANCE + 0.1


# ---------------------------------------------------------------------------
# The life paragraph


def test_traits_start_at_the_outer_tenth_of_the_panel(builder):
    """Agreeableness in the made-up panel runs 12-20, so "not agreeable" starts at 12, not at a fixed 7 nobody reaches."""
    assert builder.cuts["agreeableness"][0] == 12
    low, high = builder.cuts["extraversion"]
    assert low < 8 and high > 16


def test_tail_cut_keeps_within_the_share_but_never_less_than_the_extreme():
    scores = np.array([1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 10, dtype=float)
    weights = np.ones(len(scores))
    assert tail_cut(scores, weights, 0.10, low=False) == 10  # the top value alone is a tenth
    assert tail_cut(scores, weights, 0.10, low=True) == 1    # the bottom value is 18%: still the one kept


def test_a_trait_is_only_said_beyond_its_cut(monkeypatch):
    answers = {"big_five_extraversion": 15}
    monkeypatch.setattr(persona, "value", lambda row, col, max_valid=9000: answers.get(col))
    monkeypatch.setattr(persona, "lv", lambda row, stem: None)
    monkeypatch.setattr(persona, "raw_code", lambda row, col: None)
    said = lambda cuts: {k for k, *_ in persona.circumstance_details(None, 1, random.Random(0), cuts)}  # noqa: E731
    assert "extraversion-high" not in said(None)                              # 15 is short of the old fixed 17
    assert "extraversion-high" in said({"extraversion": (6, 15)})             # but the panel's own top tenth starts at 15


def test_money_being_much_the_same_is_held_back_not_dropped(monkeypatch):
    """It used to vanish on a coin flip; now it is a middling answer like any other."""
    monkeypatch.setattr(persona, "value", lambda row, col, max_valid=9000: {"econPersonalRetroW31": 3}.get(col))
    said = {persona.money_clause(None, random.Random(seed)) for seed in range(40)}
    assert None not in said


def test_weighted_counts_a_middling_option_at_the_neutral_weight():
    options = [("a", persona.Middling("a middling thing")), ("b", "a plain thing")]
    picks = collections.Counter(persona.weighted(options, random.Random(seed))[0] for seed in range(3000))
    assert picks["a"] / 3000 == pytest.approx(config.NEUTRAL_WEIGHT / (1 + config.NEUTRAL_WEIGHT), abs=0.03)


def test_the_life_paragraph_keeps_to_its_line_budget(panel):
    cards = build_profiles(panel, count=150, position=0, verbose=False, out_path=_tmp(), fit=False)
    budget = config.LIFE_MAX_LINES * config.LIFE_CHARS_PER_LINE
    longest = max(len(c["life"]["template"].format(**c["life"]["bold"])) for c in cards)
    assert longest <= budget + 60  # home, money and work always stand; only the extra details answer to the budget


def test_every_built_card_carries_the_generator_that_drew_it(panel):
    cards = build_profiles(panel, count=40, position=0, verbose=False, out_path=_tmp(), fit=False)
    assert {c["generator"] for c in cards} == {config.GENERATOR}
    assert all(len(c["bubbles"]) == 4 for c in cards)


def test_the_pools_are_always_lists_even_with_nothing_to_say(monkeypatch):
    """A respondent who answered none of it must give an empty pool, not None: the build reads these pools directly."""
    monkeypatch.setattr(persona, "value", lambda row, col, max_valid=9000: None)
    monkeypatch.setattr(persona, "lv", lambda row, stem: None)
    monkeypatch.setattr(persona, "latest", lambda row, cols, max_valid=9000: (None, None))
    monkeypatch.setattr(persona, "raw_code", lambda row, col: None)
    rng = random.Random(0)
    assert persona.money_options(None, rng) == []
    assert persona.extra_options(None, 1, rng) == []
    assert persona.circumstance_details(None, 1, rng) == []
    assert persona.extra_clauses(None, 1, rng, None, None, count=2) == []
    assert persona.money_clause(None, rng) is None


def _tmp():
    import tempfile
    from pathlib import Path
    return Path(tempfile.mkdtemp()) / "queue.jsonl.gz"


# ---------------------------------------------------------------------------
# The draw the solver models is the draw the cards make


def test_a_middling_answer_goes_into_the_solve_at_the_weight_it_is_drawn_at():
    offer = strengths([("a", items.Middling("about the same")), ("b", "a lot tighter"), ("c", "on a credit card"), ("c", "with a loan")])
    assert offer == {"a": config.NEUTRAL_WEIGHT, "b": 1.0, "c": 2.0}


def test_the_shares_the_solver_reports_are_the_shares_the_draw_gives():
    """Draw for real - each option's weight times its strength on the card - with the solved weights."""
    rng = np.random.default_rng(3)
    presence = (rng.random((4000, 5)) < 0.5).astype(float)
    presence[:, 0] *= config.NEUTRAL_WEIGHT  # option 0 is a middling answer wherever it is offered
    presence[presence.sum(axis=1) == 0, 1] = 1.0
    result = balance.solve(presence, np.full(5, 0.2), max_rate=1.0)
    draw, picks = random.Random(4), np.zeros(5)
    for row in presence:
        picks[draw.choices(range(5), weights=row * result["weights"])[0]] += 1
    assert np.abs(picks / len(presence) - result["shares"]).max() < 0.02
    assert np.abs(result["shares"] - result["targets"]).max() < 1e-4


def test_every_money_fact_is_filed_under_its_bes_question(panel):
    import inspect
    import re
    written = set(re.findall(r'add\("([a-z0-9-]+)"', inspect.getsource(persona.money_options)))
    drawn = {key for _, row in panel.iterrows() for key, _ in persona.money_options(row, random.Random(0))}
    assert written and drawn <= written <= set(persona.MONEY_QUESTION)


def test_the_money_sentence_follows_the_solved_weights_hardship_included(monkeypatch):
    """A shortcut once said a hardship fact whenever one came first, whatever the weights: the solve decides now."""
    answers = {"borrowEssentialsW31": 1, "savingsAmtbW31": 5}
    monkeypatch.setattr(persona, "value", lambda row, col, max_valid=9000: answers.get(col))
    weigh = lambda key: 1e6 if key == "savings-band" else 1.0  # noqa: E731
    said = [persona.money_clause(None, random.Random(seed), weigh) for seed in range(50)]
    assert sum("borrow" in s for s in said) <= 2


def test_where_they_stand_in_society_is_said_once_as_a_bubble_not_again_in_the_life_paragraph(panel):
    for answer in (1, 10):  # right at the bottom, right at the top
        row = panel.iloc[0].copy()
        row["statusTopBottomW30"] = answer
        assert persona.lv(row, "statusTopBottom") == answer
        keys = {key for key, *_ in persona.extra_options(row, 1, random.Random(0))}
        assert not keys & {"social-ladder-top", "social-ladder-bottom"}
        assert [text for _, text in items.candidate_statements(row, 1) if _.key == "statusLadder"]


def test_the_news_line_and_the_talk_line_never_disagree_about_conversation(monkeypatch):
    """'I get most of my politics from talking to people, one to two hours a day' then 'politics comes up
    a few days a week' contradicted itself: when talking is their main source, the talk line goes."""
    answers = {"infoSourcePeopleW29": 4, "discussPolDaysW28": 3}
    monkeypatch.setattr(persona, "value", lambda row, col, max_valid=9000: answers.get(col))
    for seed in range(20):
        text = persona.media_paragraph(None, 1, random.Random(seed)).template
        assert "talking to people" in text and "week" not in text


def test_every_opinion_item_has_a_key_of_its_own():
    """Two questions under one key were filed by the solver under whichever came last."""
    keys = [item.key for item in items.ITEMS]
    assert len(keys) == len(set(keys))


def test_rows_of_one_frame_share_one_entry_in_the_question_cache(panel):
    """A row taken with .iloc carries a fresh Index each time; caching by that object kept one entry per
    card and filled the memory of a full build."""
    from voterbot import data
    data._FIELDINGS.clear()
    for i in range(200):
        persona.lv(panel.iloc[i], "statusTopBottom")
    for _, row in panel.head(50).iterrows():
        persona.lv(row, "statusTopBottom")
    assert len(data._FIELDINGS) == 1

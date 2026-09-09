"""What decides which views reach a card, beyond what the respondent happens to have answered.

A card draws from the questions its respondent was asked, so left flat the feed fills up with
whatever the BES puts to everyone. Three corrections shape the draw, and each is checked here:
a middling answer is held back, a topic's items share one topic's worth of weight, and an item
is lifted for being one few people can answer at all.
"""

import random

import pytest

from voterbot import config, items
from voterbot.profile import ProfileBuilder


def builder(availability: dict[str, float]) -> ProfileBuilder:
    """A builder with no panel behind it - only the item availability the draw consults."""
    made = ProfileBuilder.__new__(ProfileBuilder)
    made.availability = availability
    return made


def pool(*specs: tuple[str, str, str]) -> list[tuple[items.Item, str]]:
    """A candidate list of (key, topic, sentence) triples, as candidate_statements would return."""
    return [(items.Item(key=key, topic=topic, cols=(f"{key}W31",)), text) for key, topic, text in specs]


def first_picks(candidates, availability, runs: int = 600) -> dict[str, int]:
    """How often each topic supplies the first bubble, across many seeds."""
    counts: dict[str, int] = {}
    made = builder(availability)
    by_text = {text: item.topic for item, text in candidates}
    for seed in range(runs):
        rng = random.Random(seed)
        spans, _ = made.pick_opinions(None, 1, rng, None, count=2)
        topic = by_text[spans[0].template]
        counts[topic] = counts.get(topic, 0) + 1
    return counts


@pytest.fixture(autouse=True)
def _fixed_candidates(monkeypatch):
    """pick_opinions asks items.candidate_statements for the pool; these tests supply it."""
    def use(candidates):
        monkeypatch.setattr(items, "candidate_statements", lambda row, country, rng=None: list(candidates))
    return use


def test_a_topic_phrased_many_ways_does_not_get_many_times_the_chances(_fixed_candidates):
    """Nine items on immigration should not out-draw one item on zero-hours nine to one."""
    candidates = pool(*[(f"m{i}", "many", f"A view about one thing, number {i}.") for i in range(4)],
                      ("s1", "single", "A view about another thing."))
    _fixed_candidates(candidates)
    counts = first_picks(candidates, {k.key: 0.5 for k, _ in candidates})
    single = counts.get("single", 0) / sum(counts.values())
    assert 0.4 < single < 0.6, counts  # even between the two topics, not one in five


def test_a_question_few_people_were_asked_is_lifted_against_one_everybody_answers(_fixed_candidates):
    candidates = pool(("common", "common", "A view everyone was asked for."),
                      ("rare", "rare", "A view hardly anyone was asked for."))
    _fixed_candidates(candidates)
    counts = first_picks(candidates, {"common": 0.9, "rare": 0.02})
    assert counts.get("rare", 0) > counts.get("common", 0), counts


def test_the_lift_can_be_turned_off_and_the_draw_goes_back_to_even(monkeypatch, _fixed_candidates):
    monkeypatch.setattr(config, "QUESTION_RARITY", 0.0)
    candidates = pool(("common", "common", "A view everyone was asked for."),
                      ("rare", "rare", "A view hardly anyone was asked for."))
    _fixed_candidates(candidates)
    counts = first_picks(candidates, {"common": 0.9, "rare": 0.02})
    share = counts.get("rare", 0) / sum(counts.values())
    assert 0.4 < share < 0.6, counts


def test_a_middling_answer_is_still_held_back(_fixed_candidates):
    """The neutral penalty survives the reweighting: a fence-sitting answer says less."""
    fence = "My local area gets more or less its fair share of government spending."
    assert items.is_neutral(fence)
    candidates = pool(("neutral", "neutral", fence), ("view", "view", "My local area gets nowhere near its fair share."))
    _fixed_candidates(candidates)
    counts = first_picks(candidates, {"neutral": 0.5, "view": 0.5})
    assert counts.get("neutral", 0) < counts.get("view", 0) / 3, counts


def test_rarity_is_the_tempered_inverse_of_how_often_an_item_can_be_said():
    made = builder({"common": 0.64, "rare": 0.04})
    assert made.rarity("common") == pytest.approx(1.25)  # (1/0.64) ** 0.5
    assert made.rarity("rare") == pytest.approx(5.0)     # (1/0.04) ** 0.5
    assert made.rarity("never measured") == 1.0          # nothing known, nothing changed


def test_every_item_in_the_library_can_be_weighed():
    """rarity() is asked for a key on every draw, so an unmeasured item must not blow up."""
    made = builder({})
    assert all(made.rarity(item.key) == 1.0 for item in items.ITEMS)

"""The solver behind every draw: weights found so the feed hits stated targets, within stated limits."""

import numpy as np
import pytest

from voterbot import balance


def pools(availability, cards=20000, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.random((cards, len(availability))) < np.asarray(availability)).astype(float)


TIERS = np.concatenate([np.full(20, 0.9), np.full(20, 0.3), np.full(15, 0.08), np.full(5, 0.01)])


def test_the_weights_hit_the_targets_whatever_the_availability():
    """Sixty options, asked of 90% down to 1%: each gets its target, not its availability's worth."""
    presence = pools(TIERS)
    result = balance.solve(presence, np.full(60, 1 / 60), max_rate=0.5)  # any cap short of certainty keeps every target reachable
    assert np.abs(result["shares"] - result["targets"]).max() < 1e-5
    common, rare = result["shares"][:20].mean(), result["shares"][40:55].mean()
    assert common == pytest.approx(rare, rel=0.01)                      # equal targets, equal airtime
    assert result["flat"][:20].mean() > 10 * result["flat"][40:55].mean()  # a flat draw is nothing like it


def test_no_option_is_picked_more_than_the_cap_where_it_is_offered():
    presence = pools(TIERS)
    rate = balance.per_draw_rate(0.5, 3)
    result = balance.solve(presence, np.full(60, 1 / 60), max_rate=rate)
    picked_where_offered = result["shares"] / presence.mean(axis=0)
    assert picked_where_offered.max() <= rate + 1e-6
    assert result["held"][55:].all()  # the 1% tier cannot reach an even share without breaking the cap


def test_what_a_capped_option_cannot_use_goes_to_the_rest_in_proportion():
    presence = pools(TIERS)
    targets = np.full(60, 1 / 60)
    result = balance.solve(presence, targets, max_rate=balance.per_draw_rate(0.5, 3))
    free = ~result["held"]
    assert result["targets"].sum() == pytest.approx(1.0)
    assert np.allclose(result["targets"][free] / targets[free], (result["targets"][free] / targets[free])[0])


def test_an_option_alone_on_a_card_wins_it_whatever_its_target():
    presence = np.array([[1, 0], [1, 0], [1, 1], [1, 1]], dtype=float)  # option 0 is all there is on half the cards
    result = balance.solve(presence, np.array([0.1, 0.9]), max_rate=1.0)
    assert result["shares"][0] >= 0.5 - 1e-9


def test_small_pools_still_come_out_whole():
    """A money sentence chooses among a handful of options; the shares must still add up and meet the cap as far as it can hold."""
    presence = pools([0.95, 0.6, 0.3, 0.1, 0.05, 0.02], cards=5000)
    result = balance.solve(presence, np.full(6, 1 / 6), max_rate=0.5)
    assert result["shares"].sum() == pytest.approx(1.0)
    assert np.abs(result["shares"] - result["targets"]).max() < 1e-4


@pytest.mark.parametrize("appearance,draws", [(0.5, 1), (0.5, 2), (0.5, 3), (0.25, 3)])
def test_the_per_draw_rate_gives_the_stated_appearance_over_every_draw(appearance, draws):
    rate = balance.per_draw_rate(appearance, draws)
    assert 1 - (1 - rate) ** draws == pytest.approx(appearance)


def test_tree_targets_split_evenly_at_every_level():
    """Two themes: one with two topics (the first holding two items), one with a single item."""
    paths = [("T1", "x"), ("T1", "x"), ("T1", "y"), ("T2", "z")]
    assert list(balance.tree_targets(list("abcd"), paths, [1, 1, 1, 1])) == [0.125, 0.125, 0.25, 0.5]


def test_tree_targets_take_the_top_shares_given_and_leaf_weights_within_a_topic():
    paths = [("T1", "x"), ("T1", "x"), ("T1", "y"), ("T2", "z")]
    shares = balance.tree_targets(list("abcd"), paths, [1, 3, 1, 1], {"T1": 0.8, "T2": 0.2})
    assert list(np.round(shares, 6)) == [0.1, 0.3, 0.4, 0.2]


def test_a_theme_split_into_many_topics_gets_no_more_than_one_split_into_few():
    """The old draw evened out per topic, so a theme the library split nine ways got nine times the airtime."""
    paths = [("elections", f"t{i}") for i in range(9)] + [("monarchy", "monarchy")]
    shares = balance.tree_targets([str(i) for i in range(10)], paths, [1.0] * 10)
    assert shares[:9].sum() == pytest.approx(shares[9])

"""Solving for draw weights, so a card's contents follow a stated target rather than the questionnaire.

A card can only say what its respondent was asked. Left alone, a draw from each person's answers
hands the feed to whatever the BES put to the most people, and within that to whatever the library
happens to phrase the most ways. So each draw is given a target instead - the share of all draws
each option (an opinion item, a life fact) should win across the feed - and its weights are solved
for once per build, per nation, so that the draws hit those targets as far as the answers allow.

The model is the draw itself. On a card, an option on offer is picked with probability
weight / (sum of the weights on offer), so across the panel each option's expected share of picks
is weight x sum over its cards of 1 / (that card's total). The weights that give each option its
target share are found by the multiplicative update w <- w * target / share: the
minorisation-maximisation fixed point for Luce choice strengths, which converges from any start.

One limit, set before solving. An answer held by a handful of people could only reach its share
of the feed by being shown on nearly every one of their cards, and then everyone who gave it would
say it every time they came round. So no option may be picked more often than `max_rate` of the
draws on the cards that offer it (`per_draw_rate` turns "appears on at most half the cards that
could carry it" into that, for however many draws a card makes); an option whose target would need
more is held there, and the share it cannot use goes to the rest in proportion to their targets.
Nor can an option win less than the cards on which it is the only thing on offer.
"""

from __future__ import annotations

import numpy as np


def per_draw_rate(appearance: float, draws: int) -> float:
    """The per-draw pick rate at which an option on offer ends up on `appearance` of cards making `draws` draws."""
    return 1.0 - (1.0 - appearance) ** (1.0 / max(draws, 1))


def flat_shares(presence: np.ndarray) -> np.ndarray:
    """Each option's share of picks if every option on a card were equally likely."""
    sizes = presence.sum(axis=1, keepdims=True)
    return (presence / np.where(sizes == 0, np.inf, sizes)).sum(axis=0) / max(int((sizes > 0).sum()), 1)


def feasible_targets(targets: np.ndarray, ceiling: np.ndarray, floor: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """The targets scaled by one common factor, each held between its floor and ceiling, with the factor
    chosen so they sum to one - so whatever a capped option cannot use goes to the rest in proportion
    to their own targets. Returns (targets, which options sit at their ceiling).

    If even every option at its ceiling falls short of one, the ceilings cannot all hold; they are
    stretched evenly until they do.
    """
    ceiling = np.asarray(ceiling, dtype=float)
    floor = np.zeros(len(ceiling)) if floor is None else np.minimum(np.asarray(floor, dtype=float), ceiling)
    wanted = np.where(ceiling > 0, np.asarray(targets, dtype=float), 0.0)
    if wanted.sum() <= 0:
        return wanted, np.zeros(len(wanted), bool)
    reachable = np.where(wanted > 0, ceiling, floor)
    if reachable.sum() < 1.0:
        ceiling = ceiling * (1.0 / reachable.sum())
    fill = lambda scale: np.clip(scale * wanted, floor, ceiling)  # noqa: E731
    low, high = 0.0, 1.0
    while fill(high).sum() < 1.0:
        high *= 2.0
    for _ in range(200):  # the total rises steadily with the scale: bisect for the scale that makes it one
        middle = (low + high) / 2
        low, high = (middle, high) if fill(middle).sum() < 1.0 else (low, middle)
    result = fill(high)
    return result / result.sum(), (wanted > 0) & (high * wanted >= ceiling * (1 - 1e-9))


def solve(presence: np.ndarray, targets: np.ndarray, max_rate: float, iterations: int = 3000, tolerance: float = 1e-5) -> dict:
    """Weights for the columns of `presence` (cards x options, 1 where the card offers the option).

    Returns the weights, the shares they achieve, the flat-draw shares, the (feasible) targets they
    were solved for, and which options are held at their ceiling. Rows offering nothing are ignored.
    """
    presence = np.asarray(presence, dtype=np.float64)
    presence = presence[presence.sum(axis=1) > 0]
    cards, options = presence.shape
    if cards == 0:
        empty = np.zeros(options)
        return {"weights": np.ones(options), "shares": empty, "flat": empty, "targets": empty, "held": np.zeros(options, bool)}
    flat = flat_shares(presence)
    offered = presence.sum(axis=0) / cards
    solo = presence[presence.sum(axis=1) == 1].sum(axis=0) / cards  # the cards where an option is all there is
    goal, held = feasible_targets(targets, np.maximum(max_rate * offered, solo), solo)
    live = goal > 0
    weights = np.where(live, 1.0, 0.0)
    shares = np.zeros(options)
    for _ in range(iterations):
        totals = presence @ weights
        totals[totals == 0] = np.inf  # a card offering only options with no target contributes nothing
        shares = weights * (presence.T @ (1.0 / totals)) / cards
        ratio = np.where(live, goal / np.maximum(shares, 1e-300), 0.0)
        weights = weights * ratio
        weights /= np.exp(np.log(weights[live]).mean())  # the scale is free; keep it near 1
        weights = np.where(live, np.clip(weights, 1e-12, 1e12), 0.0)  # a target no weight can reach must not run off to infinity
        if np.all(np.abs(ratio[live] - 1) < tolerance):
            break
    return {"weights": weights, "shares": shares, "flat": flat, "targets": goal, "held": held}


def tree_targets(options: list[str], parents: list[tuple[str, ...]], leaf_weight: list[float],
                 top_share: dict[str, float] | None = None) -> np.ndarray:
    """Targets that split evenly down a tree: each top-level group its share, each branch below it an
    equal part of that, and the options on a branch in proportion to `leaf_weight`.

    `parents[i]` is option i's path from the top (for an opinion item: its theme, then its topic).
    `top_share` gives the top-level groups their shares; without it they share equally.
    """
    tops = sorted({path[0] for path in parents})
    top = {name: (top_share or {}).get(name, 0.0 if top_share else 1.0) for name in tops}
    total = sum(top.values()) or 1.0
    shares = np.zeros(len(options))
    for i, path in enumerate(parents):
        share = top[path[0]] / total
        for depth in range(1, len(path)):  # each level below the top splits its parent's share equally
            siblings = {p[depth] for p in parents if p[:depth] == path[:depth]}
            share /= len(siblings)
        mates = [j for j, p in enumerate(parents) if p == path]
        shares[i] = share * leaf_weight[i] / sum(leaf_weight[j] for j in mates)
    return shares

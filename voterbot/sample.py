"""Weighted sampling of respondents and the profiles.jsonl queue.

Respondents are drawn without replacement with probability proportional to
the wave 31 survey weight, so the run of posts looks like Britain rather than
like the panel. The draw order is the posting order, so it is already random.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .profile import ProfileBuilder


def eligible_rows(panel: pd.DataFrame) -> pd.DataFrame:
    """Cheap pre-filter before the full build: must carry a survey weight."""
    has_weight = panel[config.WEIGHT_COLUMN].notna() & (panel[config.WEIGHT_COLUMN] > 0)
    return panel[has_weight]


def weighted_order(panel: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Every row, in weighted-draw order without replacement (heavier weights tend to come first)."""
    rng = np.random.default_rng(seed)
    weights = panel[config.WEIGHT_COLUMN].to_numpy(dtype=float)
    order = rng.choice(len(panel), size=len(panel), replace=False, p=weights / weights.sum())
    return panel.iloc[order]


def build_profiles(panel: pd.DataFrame, count: int | None = config.PROFILE_COUNT, seed: int = config.RANDOM_SEED,
                   out_path: Path = config.PROFILES_PATH, verbose: bool = True) -> list[dict]:
    """Build the posting queue as a run of yearly cycles, each a weighted draw from everyone.

    A single weighted draw without replacement starts representative and drifts
    towards the over-represented groups as the heavier weights are used up. So
    the queue is built a year at a time: each cycle draws afresh from the whole
    eligible pool in proportion to the survey weights, leaving out anyone shown
    in the last few cycles. Every stretch of the feed then matches the weights,
    nobody is capped out, and a returning voter gets a fresh set of bubbles.
    """
    pool = eligible_rows(panel).reset_index(drop=True)
    builder = ProfileBuilder(pool)
    weights = card_weights(pool, builder, seed, verbose)
    usable = weights > 0
    cycle_size = config.POSTS_PER_DAY * 365
    cycles = int(np.ceil(len(pool) / cycle_size))
    last_shown = np.full(len(pool), -10**6)
    profiles: list[dict] = []
    rng = np.random.default_rng(seed)
    for cycle in range(cycles):
        idx = np.flatnonzero(usable & (cycle - last_shown > config.REPEAT_GAP_CYCLES))
        take = min(cycle_size, len(idx)) if count is None else min(cycle_size, len(idx), count - len(profiles))
        chosen = rng.choice(idx, size=take, replace=False, p=weights[idx] / weights[idx].sum())
        for i in chosen:
            row = pool.iloc[i]
            profile = builder.build(row, seed=seed * 100_003 + int(row["id"]) * 31 + cycle)
            profile["seq"] = len(profiles)
            profile["cycle"] = cycle
            profiles.append(profile)
            last_shown[i] = cycle
        if verbose:
            print(f"  cycle {cycle + 1}/{cycles}: {take} cards ({len(profiles)} in total)")
        if count is not None and len(profiles) >= count:
            break
    write_profiles(profiles, out_path)
    if verbose:
        print(f"Wrote {len(profiles)} profiles to {out_path} "
              f"({int((~usable).sum())} of {len(pool)} respondents could not make a full card)")
    return profiles


def card_weights(pool: pd.DataFrame, builder: ProfileBuilder, seed: int, verbose: bool) -> np.ndarray:
    """Survey weights adjusted for who can actually make a full card.

    Some groups (younger and non-white respondents especially) more often skip
    the leader ratings, value items or most-important-issue question and so
    cannot be carded. Left alone, that would quietly whiten and age the feed.
    So each person's weight is divided by the card-completion rate of their
    age-by-ethnicity-by-nation cell - the usual non-response adjustment - and
    people who cannot be carded get weight zero.
    """
    can_build = np.array([builder.build(row, seed=seed) is not None for _, row in pool.iterrows()])
    weights = pool[config.WEIGHT_COLUMN].to_numpy(dtype=float)
    age = pd.to_numeric(pool["ageW31"], errors="coerce").fillna(0)
    ethnicity = pd.to_numeric(pool["p_ethnicity2W31"], errors="coerce")
    cells = pd.DataFrame({
        "age": pd.cut(age, [0, 34, 54, 64, 200], labels=False),
        "white": ethnicity.isin([1, 2, 3, 4]).to_numpy(),
        "nation": pool["countryW31"].to_numpy(),
    })
    frame = cells.assign(w=weights, built=can_build)
    rate = frame.groupby(["age", "white", "nation"], dropna=False).apply(
        lambda g: (g.w * g.built).sum() / g.w.sum() if g.w.sum() else 1.0, include_groups=False)
    completion = frame.merge(rate.rename("rate").reset_index(), on=["age", "white", "nation"], how="left")["rate"].to_numpy()
    adjusted = np.where(can_build, weights / np.clip(completion, 0.2, 1.0), 0.0)
    if verbose:
        print(f"  {int(can_build.sum())} of {len(pool)} respondents can be carded; "
              f"completion by cell ranges {completion.min():.0%}-{completion.max():.0%}")
    return adjusted


def _open(path: Path, mode: str):
    return gzip.open(path, mode + "t", encoding="utf-8") if str(path).endswith(".gz") else open(path, mode, encoding="utf-8")


def write_profiles(profiles: list[dict], path: Path = config.PROFILES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _open(path, "w") as fh:
        for profile in profiles:
            fh.write(json.dumps(profile, ensure_ascii=False) + "\n")


def load_profiles(path: Path = config.PROFILES_PATH) -> list[dict]:
    with _open(path, "r") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def read_position(path: Path = config.POSITION_PATH) -> int:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def write_position(position: int, path: Path = config.POSITION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{position}\n")

"""A made-up panel with the shape of the BES, for running a whole build without the real survey file.

Every column is one the builder reads, filled at a deliberately uneven rate: some questions put to
everyone, some to a small subsample, some to one nation only. Nothing here is real data.
"""

import numpy as np
import pandas as pd

from voterbot import codes, geo


def synthetic_panel(size: int = 3000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    country = rng.choice([1, 2, 3], size=size, p=[0.8, 0.12, 0.08])
    seats = {n: [c for c in geo.constituencies() if c.startswith(prefix)] for n, prefix in ((1, "E"), (2, "S"), (3, "W"))}

    def some(values, share, only=None):
        """`values` drawn for `share` of respondents (of one nation only, if given), missing for the rest."""
        drawn = rng.choice(values, size=size).astype(float)
        asked = rng.random(size) < share
        if only is not None:
            asked &= country == only
        return np.where(asked, drawn, np.nan)

    panel = pd.DataFrame({
        "id": np.arange(1, size + 1),
        "countryW31": country,
        "ageW31": rng.integers(18, 90, size),
        "gender": rng.choice([1, 2], size),
        "wt_new_W31": rng.uniform(0.5, 2.0, size),
        "eligibleUKGEW31": 1,
        "p_ethnicity2W31": rng.choice([1, 1, 1, 1, 1, 1, 1, 9, 10, 14], size),
        "p_religionW31": rng.choice([1, 1, 2, 3, 4, 12], size),
        "new_pcon_codeW31": [rng.choice(seats[c]) for c in country],
        "p_turnout_2024": rng.choice([0, 1, 1, 1], size),
        "p_past_vote_2024": rng.choice([1, 2, 3, 7, 12], size),
        "generalElectionVoteW31": rng.choice([0, 1, 2, 3, 7, 12], size),
        "mii_cat_llmW31": rng.choice([12, 12, 26, 31, 32, 32, 1, 40, 19], size),
        "englishnessW31": rng.integers(1, 8, size), "scottishnessW31": rng.integers(1, 8, size),
        "welshnessW31": rng.integers(1, 8, size), "britishnessW31": rng.integers(1, 8, size),
        # opinion items: everyone, a subsample, a sliver, one nation only
        "immigSelfW31": some(range(0, 11), 0.95),
        "taxSpendSelfW31": some(range(0, 11), 0.9),
        "changeCostLiveW31": some([1, 2, 4, 5], 0.9),
        "euMoreW26": some(range(0, 11), 0.12),
        "monarchW25": some([1, 2, 4, 5], 0.15),
        "zeroHourContractW27": some([1, 2, 3, 4], 0.03),
        "scotReferendumIntentionW31": some([0, 1], 0.95, only=2),
        "welshReferendumIntentionW31": some([0, 1], 0.95, only=3),
        # life: home, money, work, class, education, traits
        "homeOwn2W31": rng.choice([1, 2, 3, 4, 5, 6], size),
        "p_gross_householdW31": some(range(1, 16), 0.8),
        "econPersonalRetroW31": some([1, 2, 3, 4, 5], 0.9),
        "workingStatusW31": rng.choice([1, 2, 7, 8], size),
        "ns_secW31": some([31, 41, 71, 111, 131], 0.9),
        "sectorW31": some([1, 3], 0.9),
        "subjClassW31": some([0, 1, 2], 0.9),
        "p_edlevelW31": some([0, 1, 2, 3, 4, 5], 0.9),
        "p_hh_sizeW31": rng.integers(1, 5, size),
        "p_maritalW31": rng.integers(1, 9, size),
        "big_five_extraversion": some(range(4, 21), 0.6),
        "big_five_agreeableness": some(range(12, 21), 0.6),  # lopsided, as agreeableness is
        "riskScaleW20": some(range(1, 17), 0.3),
        "polAttentionW31": some(range(0, 11), 0.95),
        "discussPolDaysW28": some(range(0, 8), 0.5),
        "p_paper_readW31": some(list(codes.NEWSPAPER) + [16], 0.7),
    })
    for i in range(1, 6):  # the value batteries, which are also opinion items
        panel[f"lr{i}W31"] = some([1, 2, 3, 4, 5], 0.9)
        panel[f"al{i}W31"] = some([1, 2, 3, 4, 5], 0.9)
    for column in codes.LEADERS:
        panel[column] = some(range(0, 11), 0.9)
    return panel

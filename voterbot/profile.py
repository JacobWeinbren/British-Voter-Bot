"""Assembling a complete profile for one respondent.

A profile is a plain dict (so it can be written to profiles.jsonl and rendered
later without the survey data to hand). `build_profile` returns None when a
respondent does not have enough usable answers for a full card.
"""

from __future__ import annotations

import collections
import random
import re

import numpy as np
import pandas as pd

from . import codes, config, geo, items, layout, persona
from .data import text_value, value

LR_ITEMS = ["lr1W31", "lr2W31", "lr3W31", "lr4W31", "lr5W31"]
AL_ITEMS = ["al1W31", "al2W31", "al3W31", "al4W31", "al5W31"]
# Earlier fieldings of the same five-item batteries, most recent first, used when wave 31 is missing
VALUE_WAVES = ["W31", "W30", "W27W29", "W25W26", "W24", "W23", "W22", "W21", "W20"]
ISSUE_COLUMNS = ["mii_cat_llmW31", "mii_cat_llmW30", "mii_cat_llmW29", "mii_cat_llmW28", "mii_cat_llmW27", "mii_cat_llmW26"]
UNUSABLE_ISSUES = {45, 46, 47}


def values_score(row, columns: list[str], reverse: bool = False) -> float | None:
    """Mean of the five-point value items (at least three of the five answered), 1-5."""
    answers = [value(row, c) for c in columns]
    answers = [a for a in answers if a is not None]
    if len(answers) < 3:
        return None
    mean = float(np.mean(answers))
    return 6 - mean if reverse else mean


def latest_values_score(row, stem: str, reverse: bool = False) -> float | None:
    """The value-scale score from the most recent wave with enough items answered."""
    for wave in VALUE_WAVES:
        score = values_score(row, [f"{stem}{i}{wave}" for i in range(1, 6)], reverse)
        if score is not None:
            return score
    return None


def top_issue(row) -> tuple[str | None, bool, int | None]:
    """(issue phrase or None, whether they explicitly said there was no single issue, issue code)."""
    for column in ISSUE_COLUMNS:
        code = value(row, column)
        if code is not None and int(code) in codes.TOP_ISSUE and int(code) not in UNUSABLE_ISSUES:
            return codes.TOP_ISSUE[int(code)], False, int(code)
    return None, value(row, "miiW31") == 2, None


class Spectrum:
    """Where a score sits on the BES 0-10 value scale, and where the middle half of voters sits.

    The five-item batteries average to 1-5; that maps straight onto the 0-10
    scale the BES reports (0 = most left / most liberal, 10 = most right / most
    authoritarian) and then onto 0-100% of the track. The tick on the card is
    the scale midpoint, 5, fixed at 50%. The darker band is the weighted
    interquartile range of voters on the same scale - so it sits left of the
    tick on economics and right of it on culture, because that is where voters
    actually are.
    """

    def __init__(self, scores: pd.Series, weights: pd.Series):
        frame = pd.DataFrame({"score": scores, "weight": weights}).dropna().sort_values("score")
        w = frame["weight"].to_numpy(dtype=float)
        x = frame["score"].to_numpy(dtype=float)
        cumulative = np.cumsum(w) / w.sum()
        self.q1, self.median, self.q3 = (float(np.interp(q, cumulative, x)) for q in (0.25, 0.5, 0.75))
        self.iqr = [round(self.position(self.q1), 1), round(self.position(self.q3), 1)]

    @staticmethod
    def score10(score: float) -> float:
        """The 1-5 item average on the 0-10 scale."""
        return round((score - 1) / 4 * 10, 1)

    @staticmethod
    def position(score: float) -> float:
        """Percent along the track, clamped so the marker is never drawn off the end."""
        return round(min(97.0, max(3.0, (score - 1) / 4 * 100)), 1)


def detail_availability(panel: pd.DataFrame, seed: int = config.RANDOM_SEED) -> dict[str, float]:
    """How often each life detail can be offered at all, as a share of the respondents measured.

    The life paragraph has the same shape of problem as the bubbles: a tenure or an
    income band is there for nearly everyone, while having been on strike or holding no
    passport is there for a handful, and a flat draw lets the common facts crowd the rest
    out. Measured over the same sample, keyed by the fact each option states.
    """
    rows = panel.sample(min(config.AVAILABILITY_SAMPLE, len(panel)), random_state=seed)
    rng = random.Random(seed)  # only picks between wordings of the same fact, which does not affect the key
    seen: collections.Counter = collections.Counter()
    measured = 0
    for _, row in rows.iterrows():
        country = value(row, "countryW31")
        if country is None or int(country) not in codes.NATIONS:
            continue
        measured += 1
        for key, _text in persona.money_options(row, rng):
            seen[key] += 1
        for key, _theme, _text in persona.extra_options(row, int(country), rng):
            seen[key] += 1
    if not measured:
        return {}
    return {key: count / measured for key, count in seen.items()}


def item_availability(panel: pd.DataFrame, seed: int = config.RANDOM_SEED) -> dict[str, float]:
    """How often each item has something to say, as a share of the respondents measured.

    A card can only draw from the questions its respondent was actually asked, so an
    item fielded to the whole panel in wave 31 sits in nearly every pool while one asked
    once, years ago, of a subsample sits in a handful. Measuring that share is what lets
    the draw correct for it (see pick_opinions). Estimated on a sample, because asking
    every item of every respondent is the expensive half of a build.
    """
    rows = panel.sample(min(config.AVAILABILITY_SAMPLE, len(panel)), random_state=seed)
    seen: collections.Counter = collections.Counter()
    measured = 0
    for _, row in rows.iterrows():
        country = value(row, "countryW31")
        if country is None or int(country) not in codes.NATIONS:
            continue
        measured += 1
        for item, _text in items.candidate_statements(row, int(country)):
            seen[item.key] += 1
    if not measured:
        return {}
    floor = 1 / measured  # an item nobody in the sample could say is treated as one-in-the-sample rare, not impossible
    return {item.key: max(seen[item.key] / measured, floor) for item in items.ITEMS}


class ProfileBuilder:
    """Holds the population-level context (the two spectrums, how often each item is answered) needed per card."""

    def __init__(self, panel: pd.DataFrame):
        self.panel = panel
        econ = panel.apply(lambda r: values_score(r, LR_ITEMS, reverse=True), axis=1)
        cult = panel.apply(lambda r: values_score(r, AL_ITEMS), axis=1)
        weights = panel[config.WEIGHT_COLUMN]
        self.economic = Spectrum(econ, weights)
        self.cultural = Spectrum(cult, weights)
        self.availability = item_availability(panel)
        self.details = detail_availability(panel)

    def detail_rarity(self, key: str) -> float:
        """The same lift as `rarity`, for the facts the life paragraph draws from."""
        share = self.details.get(key)
        return (1 / share) ** config.QUESTION_RARITY if share else 1.0

    def rarity(self, key: str) -> float:
        """How much to lift an item for being one few respondents can answer.

        The inverse of its availability, tempered by config.QUESTION_RARITY. This can
        never push an item past the share of cards it could appear on at all, so a
        question almost nobody was asked stays rare on the feed - it just stops being
        invisible.
        """
        share = self.availability.get(key)
        return (1 / share) ** config.QUESTION_RARITY if share else 1.0

    def build(self, row: pd.Series, seed: int) -> dict | None:
        """A full card, or None when the basics (nation, age, any vote answer) are missing or they hold too few recorded views to fill four bubbles.

        Nobody is left out for their answers: people who neither voted in 2024
        nor would now get a card that says so. Everything else falls back rather
        than drops: an earlier wave's top issue or value items, the region when
        the postcode gave no constituency, a plain statement when leaders were
        not rated. Wording choices (alternative phrasings, which bubbles) come
        from the card's seed, so a returning respondent reads differently.
        """
        rng = random.Random(seed)
        country = value(row, "countryW31")
        if country is None or int(country) not in codes.NATIONS:
            return None
        country = int(country)
        age = value(row, "ageW31")
        if age is None or age < 18 or value(row, "gender") is None:
            return None
        age = int(age)

        band = persona.band(row) or persona.dont_know_band(row)
        if band is None:
            return None
        band_text, intention_party = band

        code = text_value(row, "new_pcon_codeW31")
        constituency = geo.constituencies().get(code or "")
        region = text_value(row, "gorW31")
        place = constituency.name if constituency else (region if region and region not in codes.NATIONS.values() else codes.NATIONS[country])

        issue, no_single_issue, issue_code = top_issue(row)
        econ = latest_values_score(row, "lr", reverse=True)
        cult = latest_values_score(row, "al")

        intention_code = value(row, "generalElectionVoteW31")
        leader = persona.leader_bubble(row, country, int(intention_code) if intention_code is not None else None, rng)
        seat = constituency.code if constituency else None
        head = persona.headline(row, country, place, age, seat)
        life = persona.life_paragraph(row, country, rng, seat, self.detail_rarity)
        media = persona.media_paragraph(row, country, rng)

        # config.MAX_OPINIONS opinion bubbles besides the leader line (three: four bubbles in all); a layout
        # estimate trims back if a larger setting would not fit.
        opinions, kinds = self.pick_opinions(row, country, rng, issue_code, count=config.MAX_OPINIONS)
        room = layout.middle_room(head.plain(), life.plain(), media.plain() if media else "", bool(issue or no_single_issue),
                                  econ is not None and cult is not None, band_text)
        while len(opinions) > 3 and not layout.bubbles_fit([leader.plain()] + [s.plain() for s in opinions], room):
            drop = max((i for i, k in enumerate(kinds) if k == "general"), default=len(opinions) - 1)
            del opinions[drop], kinds[drop]
        rng.shuffle(opinions)
        bubbles = [leader] + opinions
        if len(bubbles) < 4:
            return None  # answered too few of the attitude questions to fill a card

        profile = {
            "id": int(row["id"]),
            "country": country,
            "nation": codes.NATIONS[country],
            "constituency_code": constituency.code if constituency else None,
            "constituency": place,
            "possessive": {1: "his", 2: "her"}.get(int(value(row, "gender")), "their"),
            "headline": head.as_dict(),
            "life": life.as_dict(),
            "media": media.as_dict() if media else None,
            "top_issue": issue,
            "no_single_issue": no_single_issue,
            "bubbles": [b.as_dict() for b in bubbles],
            "econ_pct": self.economic.position(econ) if econ is not None else None,
            "cultural_pct": self.cultural.position(cult) if cult is not None else None,
            "econ_score10": Spectrum.score10(econ) if econ is not None else None,
            "cultural_score10": Spectrum.score10(cult) if cult is not None else None,
            "econ_iqr": self.economic.iqr,
            "cultural_iqr": self.cultural.iqr,
            "intention_party": intention_party,
            "band_text": band_text,
            "footnote": ("Party they identify with" if "supporter*" in band_text else "Party they feel closest to, at a push" if "at a push" in band_text else "Voting intention"),
        }
        profile["alt_text"] = alt_text(profile)
        profile["post_text"] = post_text(profile)
        return profile

    def pick_opinions(self, row, country: int, rng: random.Random, issue_code: int | None = None, count: int = 3) -> tuple[list[persona.Span], list[str]]:
        """Up to `count` opinion bubbles on different topics, with what kind each is (issue, general, nation).

        When they named a top issue and hold a view on that subject, one bubble
        always speaks to it; the last slot favours nation and identity; no two
        bubbles come from the same issue theme (items.THEMES). The caller shuffles.

        Three things bend the draw away from a flat pick, so the feed is not simply
        whatever the BES asks most people. A middling answer is drawn at
        items.NEUTRAL_WEIGHT, because surveys nudge people to the middle and a view
        either way says more. A topic's items share one topic's worth of weight
        between them, so a subject the library happens to phrase nine ways does not
        get nine times the chances of one phrased once. And each item is lifted by
        how rarely it can be said at all (config.QUESTION_RARITY), which is what
        stops the handful of questions put to everyone from crowding out the rest.
        """
        candidates = items.candidate_statements(row, country, rng)
        chosen: list[persona.Span] = []
        kinds: list[str] = []
        used_themes: set[str] = set()  # one bubble per issue theme (items.THEMES), not just per topic

        def draw(pool):
            pool = [(i, t) for i, t in pool if items.theme_of(i.topic) not in used_themes]
            if not pool:
                return None
            mates = collections.Counter(i.topic for i, _ in pool)
            weights = [i.weight
                       * (items.NEUTRAL_WEIGHT if items.is_neutral(t) else 1.0)
                       / mates[i.topic]
                       * self.rarity(i.key)
                       for i, t in pool]
            item, text = rng.choices(pool, weights=weights, k=1)[0]
            used_themes.add(items.theme_of(item.topic))
            return persona.Span(text)

        nation_pool = [(i, t) for i, t in candidates if i.topic in items.NATION_TOPICS]
        general_pool = [(i, t) for i, t in candidates if i.topic not in items.NATION_TOPICS]
        related = items.ISSUE_TOPICS.get(issue_code or 0, set())
        issue_pool = [(i, t) for i, t in candidates if i.topic in related]
        if issue_pool:
            span = draw(issue_pool)
            if span:
                chosen.append(span)
                kinds.append("issue")
        while len(chosen) < count - 1:
            span = draw(general_pool)
            if not span:
                break
            chosen.append(span)
            kinds.append("general")
        # Scots and Welsh respondents nearly always get a nation bubble; in England it is less of a talking point.
        nation_chance = 0.85 if country in (2, 3) else 0.45
        last = draw(nation_pool) if nation_pool and rng.random() < nation_chance else None
        kind = "nation" if last else "general"
        if last is None:
            last = draw(general_pool) or draw(nation_pool)
        if last:
            chosen.append(last)
            kinds.append(kind)
        return chosen, kinds


def _plain(span: dict | None) -> str:
    if not span:
        return ""
    return span["template"].format(**span["bold"])


ALT_TEXT_LIMIT = 2000  # Bluesky's cap on image alt text


def scale_description(score10: float, pct: float, iqr: list[float], low: str, high: str) -> str:
    """What the marker shows: the 0-10 score and whether it is inside the middle half of voters."""
    if pct < iqr[0]:
        band = f"{low} the middle half of voters"
    elif pct > iqr[1]:
        band = f"{high} the middle half of voters"
    else:
        band = "within the middle half of voters"
    return f"{score10:g} out of 10, {band}"


def alt_text(profile: dict) -> str:
    """Text alternative for the card image, written to WCAG 1.1.1 and the W3C images guidance.

    The post text already gives the headline, top issue and vote, so the alt text
    does not repeat them. It says what the image is, then gives what the image
    alone conveys: the map, the life and news lines, the four views, and what
    the two scales show - the 0-10 scores and whether they fall inside the
    middle half of voters. Colour is not described because the party it
    encodes is in words.
    """
    views = " ".join(_plain(b) for b in profile["bubbles"])
    if profile.get("econ_pct") is not None and profile.get("cultural_pct") is not None:
        economic = scale_description(profile["econ_score10"], profile["econ_pct"], profile["econ_iqr"], "further left than", "further right than")
        cultural = scale_description(profile["cultural_score10"], profile["cultural_pct"], profile["cultural_iqr"], "more liberal than", "more authoritarian than")
        scales = (f"Where they sit on the BES 0 to 10 value scales: economic, left to right, {economic}; "
                  f"social, liberal to authoritarian, {cultural}.")
    else:
        scales = "The value scales are left off because they did not answer those questions."
    map_line = (f"A map of {profile['nation']} with a dot on {profile['constituency']}." if profile.get("constituency_code")
                else f"A map of {profile['nation']}; their constituency is not recorded.")
    sections = [
        "Voter card.",
        map_line,
        f"About them, in their words: {_plain(profile['life'])}",
        f"News habits: {_plain(profile['media'])}" if profile.get("media") else "",
        f"{profile.get('possessive', 'their').capitalize()} views, from {profile.get('possessive', 'their')} survey answers, in {codes.NUMBER_WORDS.get(len(profile['bubbles']), len(profile['bubbles']))} speech bubbles: {views}",
        scales,
    ]
    text = " ".join(s for s in sections if s)
    if len(text) > ALT_TEXT_LIMIT:  # rare; drop the news line first, then tighten
        sections[3] = ""
        text = " ".join(s for s in sections if s)
    return spoken(text)[:ALT_TEXT_LIMIT]


def spoken(text: str) -> str:
    """Small changes so a screen reader says what a sighted reader sees: ranges as 'to', not a hyphen."""
    text = re.sub(r"(£[\d,]+)-(£[\d,]+)", r"\1 to \2", text)
    text = re.sub(r"\b(\d+)-(\d+)\b", r"\1 to \2", text)
    return text


def post_text(profile: dict) -> str:
    """The visible post: the headline, top issue and vote - the text the alt text builds on."""
    head = _plain(profile["headline"])
    band = profile["band_text"].replace("*", "") + "."
    issue = issue_line(profile)
    text = f"{head} {issue} {band}" if issue else f"{head} {band}"
    if len(text) > 295:
        text = f"{head} {band}"
    return text[:300]


def issue_line(profile: dict) -> str:
    """The top-issue sentence, or the honest alternative, or nothing."""
    if profile.get("top_issue"):
        return f"My top issue is {profile['top_issue']}."
    if profile.get("no_single_issue"):
        return "I couldn't pick a single top issue."
    return ""

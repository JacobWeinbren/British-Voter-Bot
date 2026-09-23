"""Bringing an already-built queue in line with the current anonymity rules.

The queue in outputs/profiles.jsonl.gz was built before religion was coarsened to
census-level groups (codes.RELIGION), age to a decade band (persona.age_band), and a
faith with almost no one of it in the respondent's constituency left off altogether
(persona.faith_is_rare).
Rebuilding it from the raw BES file would answer that, but it would also reshuffle
every card and strand the posting position, so the queue is rewritten in place
instead: same respondents, same order, coarser headline.

Idempotent - a queue that has already been through this is left alone. What it cannot do is
take a group back apart: once a card says "Christian" or "in my thirties", the denomination
and the exact age behind it are gone, so a rule that splits a group needs the queue as it
stood before anonymising.
"""

from __future__ import annotations

import collections
import json
import os
import re
from pathlib import Path

from . import codes, config, persona
from .profile import alt_text, post_text
from .sample import load_profiles, write_profiles

# The denomination labels cards carried before the change, and nothing else: an unfamiliar
# label means the queue holds something this migration was not written for, so it stops.
RETIRED_DENOMINATIONS = {
    "Episcopalian": "Anglican",
    "Presbyterian": "Christian", "Methodist": "Christian", "Baptist": "Christian",
    "United Reformed": "Christian", "Free Presbyterian": "Christian", "Brethren": "Christian",
    "Orthodox Christian": "Christian", "Pentecostal": "Christian", "evangelical Christian": "Christian",
}
CURRENT_LABELS = {label for label in codes.RELIGION.values() if label}
CURRENT_BANDS = {band for _, band in persona.AGE_BANDS} | {persona.OLDEST_BAND}

# Wording that has since been corrected at source, and what the queued copy should read instead.
# Applied to the life paragraph, the news paragraph, every bubble and the vote line; each replacement
# leaves text that no longer contains what it replaced, so running it twice changes nothing.
RETIRED_WORDINGS = {
    "My highest qualification is A-levels.": "My highest qualifications are A-levels.",
    "A-levels are the top qualification I've got.": "A-levels are the top qualifications I've got.",
    "GCSEs are my highest qualification.": "GCSEs are my highest qualifications.",
    "I passed political posts on on ": "I passed on political posts on ",
    "I passed political content on ": "I passed on political content ",
    "is the only one I can rate, and ": "is the only one I could give a score to, and ",
    " a slightly easier ride than most in Britain.": " a slightly easier ride than other groups in Britain.",
    " a little better treated than most in Britain.": " treated a little better than other groups in Britain.",
    "voted another party": "voted for another party",
    "went another party": "went for another party",
    "Growing up, around 14, the main wage earner": "When I was about 14, the main wage earner",
    "growing up, around 14, the main wage earner": "when I was about 14, the main wage earner",
    "I'm a SNP supporter": "I'm an SNP supporter",
    # the September 2026 copy review
    "semi-routine": "semi-skilled",
    "I stayed in education past 20.": "I stayed in education until I was 20 or older.",
    "Europe, outside the EU": "a European country outside the EU",
    "I've a health problem or disability that limits what I can do day to day a lot.": "A health problem or disability limits a lot of what I can do day to day.",
    "I've a health problem that limits what I can do day to day a little.": "A health problem limits what I can do day to day, but only a little.",
    "General elections are one vote I'm not eligible to cast.": "I'm not allowed to vote in general elections.",
    "I'm the sort who keeps in the background, as I see it.": "I'm the sort who keeps in the background.",
    "My local community is somewhere I feel a sense of belonging.": "My local community is somewhere I feel I belong.",
    "put my household down near the poorest end in the country": "put my household near the poorest end of the scale",
    "put my household up near the richest end in the country": "put my household near the richest end of the scale",
    "member of the Conservative party": "member of the Conservative Party",
    "member of the Labour party": "member of the Labour Party",
    "member of the Lib Dem party": "member of the Lib Dems",
    "member of the SNP party": "member of the SNP",
    "member of the Plaid Cymru party": "member of Plaid Cymru",
    "member of the UKIP party": "member of UKIP",
    "member of the Green party": "member of the Green Party",
    "member of the BNP party": "member of the BNP",
    "member of the Change UK party": "member of Change UK",
    "member of the Reform party": "member of Reform UK",
    "I like every one of the party leaders, and much the same amount.": "I like every one of the party leaders, all about equally.",
    "preacher who preaches hatred": "preacher who spreads hatred",
    "A preacher of hatred of the West": "Someone who preaches hatred of the West",
    "a preacher of hatred of the West": "someone who preaches hatred of the West",
    "I wish I'd voted differently to how I voted in 2024.": "I wish I'd voted differently in 2024.",
    "have gone about right, as far as I'm concerned.": "are about where they should be, as far as I'm concerned.",
    "the amount of public services run by": "the number of public services run by",
    "Cut taxes a lot, even if it means spending much less on health and social services.": "Taxes should be cut a lot, even if it means spending much less on health and social services.",
    "Raise taxes a lot and spend much more on health and social services.": "We should raise taxes a lot and spend much more on health and social services.",
    "with a bit of spending cut too": "with a few spending cuts too",
    "a really high quality education": "a really high-quality education",
}
# Corrections that have to move a bold slot, so cannot be a plain substitution.
RETIRED_PATTERNS = [
    (re.compile(r"\{(\w+)\} is something I( also)? watch\."), r"I\2 use {\1}."),
    (re.compile(r"When I meet another of the (Remainer|Leaver)s,"), r"When I meet a fellow \1,"),
    (re.compile(r"I feel a bond with any of the (Remainer|Leaver)s I meet\."), r"I feel a bond with any fellow \1 I meet."),
    (re.compile(r"When I come across one of the other (Remainer|Leaver)s,"), r"When I come across another \1,"),
]
# A whole sentence naming where someone worships, which names their faith along with it.
WORSHIP_SENTENCE = re.compile(r"[^.]*\b(?:mosque|gurdwara|synagogue|temple)\b[^.]*\.\s*")


def coarse_religion(label: str) -> str:
    """A stored religion label as the current rules would write it."""
    if label in CURRENT_LABELS:
        return label
    if label in RETIRED_DENOMINATIONS:
        return RETIRED_DENOMINATIONS[label]
    raise ValueError(f"unknown religion label in the queue: {label!r}")


def spoken_headline(card: dict) -> str:
    return card["headline"]["template"].format(**card["headline"]["bold"])


def drop_religion(headline: dict) -> None:
    """Take the faith out of a stored headline, and put the article right behind it."""
    headline["bold"].pop("religion", None)
    template = headline["template"].replace("{religion} ", "")
    first = next((headline["bold"][slot] for slot in ("ethnicity", "gender") if slot in headline["bold"]), None)
    if first:
        template = re.sub(r"^I'm an? ", f"I'm {persona.article(first)} ", template)
    headline["template"] = template


def migrate_card(card: dict) -> bool:
    """Bring one card in line with the current rules, in place; True if anything changed."""
    headline = card["headline"]
    bold = headline["bold"]
    before = json.dumps(card, sort_keys=True)

    if "religion" in bold:
        bold["religion"] = coarse_religion(bold["religion"])
        if persona.faith_is_rare(bold["religion"], card.get("constituency_code")):
            drop_religion(headline)
            card["life"]["template"] = WORSHIP_SENTENCE.sub("", card["life"]["template"]).strip()
    for span in [card["life"], card.get("media"), *card["bubbles"]]:
        if span:
            span["template"] = _corrected(span["template"])
    card["band_text"] = _corrected(card["band_text"])
    if bold.get("age", "").isdigit():
        bold["age"] = persona.age_band(int(bold["age"]))
        headline["template"] = headline["template"].replace("aged {age}", "in my {age}")
    elif bold.get("age") not in CURRENT_BANDS:
        # A band that has since been split or renamed cannot be rewritten from itself - the
        # exact age it came from is gone. Migrate the queue as it was before anonymising.
        raise ValueError(f"retired age band in the queue: {bold.get('age')!r}")

    if json.dumps(card, sort_keys=True) == before:
        return False
    card["post_text"] = post_text(card)  # the post text carries the headline; the alt text carries the rest
    card["alt_text"] = alt_text(card)
    return True


def _corrected(text: str) -> str:
    """Stored copy with any since-corrected wording put right."""
    for was, now in RETIRED_WORDINGS.items():
        text = text.replace(was, now)
    for pattern, now in RETIRED_PATTERNS:
        text = pattern.sub(now, text)
    return text


def migrate(path: Path = config.PROFILES_PATH, dry_run: bool = False) -> dict:
    """Rewrite the queue with coarse religion and banded age. Returns a summary of what changed."""
    cards = load_profiles(path)
    changed = 0
    examples: list[tuple[str, str]] = []
    religions: collections.Counter = collections.Counter()
    bands: collections.Counter = collections.Counter()
    for card in cards:
        before = spoken_headline(card)
        if migrate_card(card):
            changed += 1
            if len(examples) < 5:
                examples.append((before, spoken_headline(card)))
        religions[card["headline"]["bold"].get("religion")] += 1
        bands[card["headline"]["bold"].get("age")] += 1
    if changed and not dry_run:  # written beside the queue and moved into place, so a crash cannot truncate it
        temp = path.with_name(f"{path.stem}.tmp{path.suffix}")
        write_profiles(cards, temp)
        os.replace(temp, path)
    return {"total": len(cards), "changed": changed, "religions": religions, "bands": bands, "examples": examples}


def describe(summary: dict) -> str:
    """The summary as the CLI prints it."""
    total = summary["total"] or 1
    lines = [f"{summary['changed']} of {summary['total']} cards rewritten"]
    for before, after in summary["examples"]:
        lines += [f"  - {before}", f"  + {after}"]
    for title, counts in (("religion", summary["religions"]), ("age band", summary["bands"])):
        lines.append(f"\n{title}:")
        lines += [f"  {name or '(none)':<26}{n:6d}  {n / total:5.1%}" for name, n in counts.most_common()]
    return "\n".join(lines)

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

# Sentences whose wording has since been corrected, and what they should read instead.
RETIRED_WORDINGS = {
    "My highest qualification is A-levels.": "My highest qualifications are A-levels.",
    "A-levels are the top qualification I've got.": "A-levels are the top qualifications I've got.",
    "GCSEs are my highest qualification.": "GCSEs are my highest qualifications.",
}
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
    before = (headline["template"], dict(bold), card["life"]["template"])

    if "religion" in bold:
        bold["religion"] = coarse_religion(bold["religion"])
        if persona.faith_is_rare(bold["religion"], card.get("constituency_code")):
            drop_religion(headline)
            card["life"]["template"] = WORSHIP_SENTENCE.sub("", card["life"]["template"]).strip()
    card["life"]["template"] = _corrected(card["life"]["template"])
    if bold.get("age", "").isdigit():
        bold["age"] = persona.age_band(int(bold["age"]))
        headline["template"] = headline["template"].replace("aged {age}", "in my {age}")
    elif bold.get("age") not in CURRENT_BANDS:
        # A band that has since been split or renamed cannot be rewritten from itself - the
        # exact age it came from is gone. Migrate the queue as it was before anonymising.
        raise ValueError(f"retired age band in the queue: {bold.get('age')!r}")

    if (headline["template"], bold, card["life"]["template"]) == before:
        return False
    card["post_text"] = post_text(card)  # the post text carries the headline; the alt text never has
    card["alt_text"] = alt_text(card)
    return True


def _corrected(life: str) -> str:
    """A stored life paragraph with any since-corrected wording put right."""
    for was, now in RETIRED_WORDINGS.items():
        life = life.replace(was, now)
    return life


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

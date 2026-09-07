"""Bringing an already-built queue in line with the current anonymity rules.

The queue in outputs/profiles.jsonl.gz was built before religion was coarsened to
census-level groups (codes.RELIGION) and age to a decade band (persona.age_band).
Rebuilding it from the raw BES file would answer that, but it would also reshuffle
every card and strand the posting position, so the queue is rewritten in place
instead: same respondents, same order, coarser headline.

Idempotent - a queue that has already been through this is left alone.
"""

from __future__ import annotations

import collections
import os
from pathlib import Path

from . import codes, config, persona
from .profile import alt_text, post_text
from .sample import load_profiles, write_profiles

# The denomination labels cards carried before the change, and nothing else: an unfamiliar
# label means the queue holds something this migration was not written for, so it stops.
RETIRED_DENOMINATIONS = {
    "Anglican": "Christian", "Episcopalian": "Christian", "Catholic": "Christian",
    "Presbyterian": "Christian", "Methodist": "Christian", "Baptist": "Christian",
    "United Reformed": "Christian", "Free Presbyterian": "Christian", "Brethren": "Christian",
    "Orthodox Christian": "Christian", "Pentecostal": "Christian", "evangelical Christian": "Christian",
}
CURRENT_LABELS = {label for label in codes.RELIGION.values() if label}


def coarse_religion(label: str) -> str:
    """A stored religion label as the current rules would write it."""
    if label in CURRENT_LABELS:
        return label
    if label in RETIRED_DENOMINATIONS:
        return RETIRED_DENOMINATIONS[label]
    raise ValueError(f"unknown religion label in the queue: {label!r}")


def spoken_headline(card: dict) -> str:
    return card["headline"]["template"].format(**card["headline"]["bold"])


def migrate_card(card: dict) -> bool:
    """Coarsen one card's headline in place; True if anything changed."""
    headline = card["headline"]
    bold = headline["bold"]
    before = (headline["template"], dict(bold))

    if "religion" in bold:
        bold["religion"] = coarse_religion(bold["religion"])
    if bold.get("age", "").isdigit():
        bold["age"] = persona.age_band(int(bold["age"]))
        headline["template"] = headline["template"].replace("aged {age}", "in my {age}")

    if (headline["template"], bold) == before:
        return False
    card["post_text"] = post_text(card)  # the post text carries the headline; the alt text never has
    card["alt_text"] = alt_text(card)
    return True


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

"""When the next card is due.

The feed posts at fixed UK times (config.SLOT_HOURS). GitHub's cron is best
effort: runs start late, often by half an hour and sometimes by hours, and
during an Actions incident they do not start at all. So the workflow does not
ask "is it one of the posting hours right now?" - a late run would answer no
and the slot would be lost. It asks "has the most recent slot been posted
yet?", comparing the slot's start with the time of the last post, which `post`
records in outputs/last_post.txt. A late run still posts; a dropped run is made
up by the next one; and after a long outage the feed posts one card and then
waits for the next slot rather than catching up in a burst.

outputs/last_post.txt is the ledger, and it is written by a commit that happens
*after* the card is already on the feed. That leaves one window where it lies:
the post succeeds and the push does not. The workflow retries the push and
fails loudly, but if all three attempts fail the ledger is stale and the next
check posts the same card a second time. A duplicate on the feed is permanent;
a skipped check is made up an hour later. So before posting we confirm against
the feed itself, and treat a feed we cannot read as "do not post". The one
exception is an unset BLUESKY_HANDLE, which leaves nothing to ask: that falls
back to the ledger, because a missing secret should not stop the feed dead.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo

from . import config

UK = ZoneInfo("Europe/London")

# The public appview. Read-only and unauthenticated, so `due` still needs no app password and no
# third-party packages - it keeps running on the runner's own python3, which is what makes the
# hourly check cheap enough to run sixteen times a day.
FEED_HOST = "https://public.api.bsky.app"
FEED_LIMIT = 10
FEED_TIMEOUT = 10


def latest_slot(now: datetime) -> datetime:
    """The start of the most recent posting slot at or before `now`, as a UK wall-clock time.

    Works across the clock changes because the slots are wall-clock hours in
    Europe/London, not UTC hours: 10am is 10am whether or not summer time is on.
    """
    local = now.astimezone(UK)
    for days_back in (0, 1):
        day = (local - timedelta(days=days_back)).date()
        for hour in sorted(config.SLOT_HOURS, reverse=True):
            slot = datetime.combine(day, time(hour), tzinfo=UK)
            if slot <= local:
                return slot
    raise AssertionError("yesterday's last slot is always in the past")


def is_due(now: datetime, last_post: datetime | None) -> bool:
    """True when nothing has been posted since the most recent slot began."""
    return last_post is None or last_post < latest_slot(now)


def read_last_post(path: Path = config.LAST_POST_PATH) -> datetime | None:
    """The time of the last post, or None if none has been recorded."""
    try:
        text = path.read_text().strip()
    except FileNotFoundError:
        return None
    if not text:
        return None
    when = datetime.fromisoformat(text.replace("Z", "+00:00"))  # a trailing Z is only understood from Python 3.11
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def write_last_post(when: datetime, path: Path = config.LAST_POST_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")


def handle_from_env() -> str:
    """The account handle from BLUESKY_HANDLE, tidied as voterbot.bluesky tidies it, or "" if unset.

    Read here rather than imported from voterbot.bluesky, which pulls in atproto:
    `due` has to keep running on the runner's own python3 with nothing installed.
    """
    return (os.environ.get("BLUESKY_HANDLE") or "").strip().lstrip("@").strip()


def feed_last_post(handle: str, *, limit: int = FEED_LIMIT, timeout: int = FEED_TIMEOUT) -> datetime | None:
    """The time of the newest post on the account's feed, or None if it has none.

    Network and parse failures are raised, not swallowed: `decide` turns them into a
    refusal to post, and the distinction between "the feed says nothing is there" and
    "we could not ask the feed" is exactly the one that must not be lost here.
    """
    query = urllib.parse.urlencode(
        {"actor": handle, "limit": str(limit), "filter": "posts_no_replies"}
    )
    url = f"{FEED_HOST}/xrpc/app.bsky.feed.getAuthorFeed?{query}"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        feed = json.load(response)["feed"]

    times = []
    for item in feed:
        # A repost carries the original post's createdAt, which would be an old timestamp
        # attached to a recent action. Only the account's own posts count as a slot filled.
        if "reason" in item:
            continue
        created = item.get("post", {}).get("record", {}).get("createdAt")
        if created:
            times.append(datetime.fromisoformat(created.replace("Z", "+00:00")))
    return max(times) if times else None


class Decision(NamedTuple):
    """What to do this run, and why.

    `repair` is set when the feed and the ledger disagree: the card is up but
    outputs/last_post.txt never landed. The caller writes it before exiting so the
    disagreement is fixed once rather than re-discovered every hour.
    """

    post: bool
    reason: str
    repair: datetime | None = None


def decide(now: datetime, handle: str, last_post: datetime | None) -> Decision:
    """Whether to post the next card."""
    slot = latest_slot(now)

    if not is_due(now, last_post):
        return Decision(False, f"the {describe(slot)} card went out at {describe(last_post)}")

    if not handle:
        # Nothing to ask the feed with. Fail open on purpose: this is the behaviour the bot had
        # before the feed check existed, and a misconfigured handle that stopped the feed dead
        # would be a worse fault than the duplicate the check is here to prevent.
        return Decision(True, f"nothing recorded since the {describe(slot)} slot opened; the feed was not checked (BLUESKY_HANDLE is not set)")

    try:
        posted = feed_last_post(handle)
    except Exception as error:  # noqa: BLE001 - any failure to read the feed means the same thing
        # Fail closed. Posting blind risks a permanent duplicate; skipping costs an hour, and
        # the next check will very likely succeed. If the appview is unreachable the PDS we
        # would post to is often unwell too, so this rarely gives up a card that would have
        # landed anyway.
        return Decision(False, f"could not read the feed ({error}) - leaving this to the next check")

    if posted is not None and posted >= slot:
        return Decision(
            False,
            f"the {describe(slot)} card is already on the feed, posted {describe(posted)} - "
            "the queue position never committed, repairing the ledger",
            repair=posted,
        )

    return Decision(True, f"nothing on the feed since the {describe(slot)} slot opened")


def describe(when: datetime | None) -> str:
    return when.astimezone(UK).strftime("%a %d %b %H:%M %Z") if when else "never"

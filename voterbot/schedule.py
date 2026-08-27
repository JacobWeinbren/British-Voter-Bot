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
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import config

UK = ZoneInfo("Europe/London")


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


def describe(when: datetime | None) -> str:
    return when.astimezone(UK).strftime("%a %d %b %H:%M %Z") if when else "never"

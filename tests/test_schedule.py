"""The posting gate survives GitHub's cron: a late run still posts, a dropped run is made up, nothing posts twice."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from voterbot import cli, config, schedule
from voterbot.schedule import UK, is_due, latest_slot, read_last_post, write_last_post


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=timezone.utc)


def uk(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UK)


def test_slots_are_uk_wall_clock_hours():
    assert config.SLOT_HOURS == (10, 13, 17, 21)
    assert config.POSTS_PER_DAY == 4


@pytest.mark.parametrize("now, slot", [
    (uk("2026-08-26 23:49"), uk("2026-08-26 21:00")),  # summer time
    (uk("2026-08-27 00:30"), uk("2026-08-26 21:00")),  # after midnight: yesterday's last slot
    (uk("2026-08-27 09:59"), uk("2026-08-26 21:00")),
    (uk("2026-08-27 10:00"), uk("2026-08-27 10:00")),  # on the hour counts
    (uk("2026-08-27 14:10"), uk("2026-08-27 13:00")),
    (uk("2026-01-15 17:45"), uk("2026-01-15 17:00")),  # winter
    (uk("2026-03-29 10:30"), uk("2026-03-29 10:00")),  # the day the clocks go forward
    (uk("2026-10-25 10:30"), uk("2026-10-25 10:00")),  # the day the clocks go back
])
def test_latest_slot(now, slot):
    assert latest_slot(now) == slot


def test_slots_follow_the_clock_change():
    # 10am UK is 09:00 UTC in summer and 10:00 UTC in winter
    assert latest_slot(utc("2026-08-27 09:30")) == utc("2026-08-27 09:00")
    assert latest_slot(utc("2026-01-15 09:30")) == utc("2026-01-14 21:00")
    assert latest_slot(utc("2026-01-15 10:30")) == utc("2026-01-15 10:00")


def test_the_run_that_lost_the_26_august_evening_post_now_posts():
    # The 21:00 cron started at 22:49 UTC (23:49 BST); the old hour check saw 23 and skipped.
    last_post = utc("2026-08-26 16:50:42")
    assert is_due(utc("2026-08-26 22:49:26"), last_post)


def test_a_slot_is_posted_once():
    slot_start = utc("2026-08-26 16:00")  # 17:00 BST
    assert is_due(utc("2026-08-26 16:03"), utc("2026-08-26 11:55"))
    assert not is_due(utc("2026-08-26 16:23"), utc("2026-08-26 16:05"))  # posted at 17:05 BST: the 17:23 and 17:43 checks do nothing
    assert not is_due(utc("2026-08-26 19:43"), utc("2026-08-26 16:05"))
    assert is_due(utc("2026-08-26 20:03"), utc("2026-08-26 16:05"))  # the 21:00 slot
    assert not is_due(slot_start, slot_start)


def test_after_an_outage_one_card_is_posted_then_the_feed_waits_for_the_next_slot():
    last_post = utc("2026-08-24 20:32")
    now = utc("2026-08-27 14:03")  # three days of dropped runs
    assert is_due(now, last_post)
    assert not is_due(utc("2026-08-27 14:23"), now)  # not a burst of the missed cards
    assert is_due(utc("2026-08-27 16:03"), now)  # the 17:00 slot, as normal


def test_no_record_means_due():
    assert is_due(utc("2026-08-27 14:03"), None)


def test_last_post_round_trips_in_utc(tmp_path):
    path = tmp_path / "last_post.txt"
    assert read_last_post(path) is None
    write_last_post(uk("2026-08-27 17:47:05"), path)
    assert path.read_text() == "2026-08-27T16:47:05Z\n"
    assert read_last_post(path) == utc("2026-08-27 16:47:05")


def test_a_blank_or_naive_record_is_tolerated(tmp_path):
    path = tmp_path / "last_post.txt"
    path.write_text("\n")
    assert read_last_post(path) is None
    path.write_text("2026-08-27T16:47:05\n")
    assert read_last_post(path) == utc("2026-08-27 16:47:05")


def test_the_committed_record_is_a_real_time():
    assert read_last_post() is not None


def test_due_command_exit_codes(monkeypatch, capsys):
    monkeypatch.setattr(schedule, "read_last_post", lambda: utc("2026-08-26 16:50"))
    cli.main(["due"])  # the 21:00 slot on 26 August, and every slot since, is unposted
    assert capsys.readouterr().out.startswith("due:")

    monkeypatch.setattr(schedule, "read_last_post", lambda: datetime.now(timezone.utc))
    with pytest.raises(SystemExit) as stop:
        cli.main(["due"])
    assert stop.value.code == cli.NOT_DUE
    assert capsys.readouterr().out.startswith("not due:")


# --- the feed check: the ledger can lie, so `due` confirms against the feed before it says yes ---

HANDLE = "britishvoterbot.bsky.social"


def feed(monkeypatch, posted: datetime | None = None, error: Exception | None = None):
    def fake(handle, **kwargs):
        assert handle == HANDLE
        if error is not None:
            raise error
        return posted
    monkeypatch.setattr(schedule, "feed_last_post", fake)


def test_the_feed_is_only_asked_once_the_ledger_says_a_card_is_due(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("the feed should not be read when the ledger already accounts for the slot")
    monkeypatch.setattr(schedule, "feed_last_post", never)
    decision = schedule.decide(utc("2026-08-26 16:23"), HANDLE, utc("2026-08-26 16:05"))
    assert not decision.post and decision.repair is None


def test_an_empty_feed_since_the_slot_opened_posts(monkeypatch):
    feed(monkeypatch, posted=utc("2026-08-26 11:55"))  # the 13:00 card, not the 17:00 one
    decision = schedule.decide(utc("2026-08-26 16:03"), HANDLE, utc("2026-08-26 11:55"))
    assert decision.post and decision.repair is None


def test_a_card_already_on_the_feed_is_not_posted_twice(monkeypatch):
    # The 17:00 card went up at 17:05 BST and the queue position never pushed, so the ledger
    # still reads 13:00. Without the feed check the next hour would post the same card again.
    feed(monkeypatch, posted=utc("2026-08-26 16:05"))
    decision = schedule.decide(utc("2026-08-26 17:03"), HANDLE, utc("2026-08-26 11:55"))
    assert not decision.post
    assert decision.repair == utc("2026-08-26 16:05")


def test_a_feed_that_cannot_be_read_does_not_post(monkeypatch):
    feed(monkeypatch, error=OSError("appview timed out"))
    decision = schedule.decide(utc("2026-08-26 16:03"), HANDLE, utc("2026-08-26 11:55"))
    assert not decision.post and decision.repair is None


def test_no_handle_falls_back_to_the_ledger(monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("there is no handle to ask the feed with")
    monkeypatch.setattr(schedule, "feed_last_post", never)
    assert schedule.decide(utc("2026-08-26 16:03"), "", utc("2026-08-26 11:55")).post
    assert not schedule.decide(utc("2026-08-26 16:23"), "", utc("2026-08-26 16:05")).post


def test_handle_from_env_is_tidied_like_the_posting_credentials(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", " @britishvoterbot.bsky.social ")
    assert schedule.handle_from_env() == HANDLE
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    assert schedule.handle_from_env() == ""


def test_reposts_do_not_count_as_a_slot_filled(monkeypatch):
    body = {"feed": [
        {"reason": {"$type": "app.bsky.feed.defs#reasonRepost"},
         "post": {"record": {"createdAt": "2026-08-26T16:05:00Z"}}},
        {"post": {"record": {"createdAt": "2026-08-26T11:55:00Z"}}},
    ]}
    monkeypatch.setattr(schedule.urllib.request, "urlopen", fake_urlopen(body))
    assert schedule.feed_last_post(HANDLE) == utc("2026-08-26 11:55")


def test_an_empty_feed_reads_as_nothing_posted(monkeypatch):
    monkeypatch.setattr(schedule.urllib.request, "urlopen", fake_urlopen({"feed": []}))
    assert schedule.feed_last_post(HANDLE) is None


def fake_urlopen(body: dict):
    import contextlib, io, json

    @contextlib.contextmanager
    def opener(url, timeout=None):
        assert HANDLE in url and "posts_no_replies" in url
        yield io.StringIO(json.dumps(body))
    return opener


def test_due_repairs_the_ledger_when_the_card_is_already_up(monkeypatch, capsys, tmp_path):
    ledger = tmp_path / "last_post.txt"
    write_last_post(utc("2026-08-26 11:55"), ledger)
    monkeypatch.setattr(config, "LAST_POST_PATH", ledger)
    monkeypatch.setenv("BLUESKY_HANDLE", HANDLE)
    monkeypatch.setattr(schedule, "read_last_post", lambda: utc("2026-08-26 11:55"))
    monkeypatch.setattr(schedule, "latest_slot", lambda now: utc("2026-08-26 16:00"))
    feed(monkeypatch, posted=utc("2026-08-26 16:05"))

    with pytest.raises(SystemExit) as stop:
        cli.main(["due"])
    assert stop.value.code == cli.NOT_DUE
    assert "already on the feed" in capsys.readouterr().out
    assert read_last_post(ledger) == utc("2026-08-26 16:05")  # repaired, so the next hour stops asking

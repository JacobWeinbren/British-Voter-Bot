"""The Bluesky post carries the card's alt text (WCAG 1.1.1), and keeps it when the PNG fallback is sent."""

from __future__ import annotations

import pytest

from voterbot import bluesky, config
from voterbot.profile import ALT_TEXT_LIMIT

ALT = "Card for one voter: a map of Wales with a magenta dot, four speech bubbles and two scales."


class FakeClient:
    """Records send_image calls; refuses the image bytes listed in `refuse` the way a PDS would."""

    def __init__(self, refuse: set[bytes] = frozenset()):
        self.calls: list[dict] = []
        self.refuse = refuse

    def send_image(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["image"] in self.refuse:
            raise RuntimeError("blob refused")
        return type("Response", (), {"uri": f"at://did:plc:bot/app.bsky.feed.post/{len(self.calls)}"})()


@pytest.fixture
def images(tmp_path):
    webp, png = tmp_path / "card.webp", tmp_path / "card.png"
    webp.write_bytes(b"WEBP")
    png.write_bytes(b"PNG")
    return webp, png


def test_post_carries_the_alt_text(monkeypatch, images):
    fake = FakeClient()
    monkeypatch.setattr(bluesky, "_client", lambda: fake)
    webp, png = images
    uri = bluesky.post_card("I'm a voter.", webp, ALT, fallback_path=png)
    assert uri.startswith("at://")
    (call,) = fake.calls
    assert call["image_alt"] == ALT
    assert call["text"] == "I'm a voter." and call["image"] == b"WEBP"
    assert (call["image_aspect_ratio"].width, call["image_aspect_ratio"].height) == (config.CARD_WIDTH, config.CARD_HEIGHT)


def test_png_fallback_keeps_the_alt_text(monkeypatch, images):
    fake = FakeClient(refuse={b"WEBP"})
    monkeypatch.setattr(bluesky, "_client", lambda: fake)
    webp, png = images
    bluesky.post_card("I'm a voter.", webp, ALT, fallback_path=png)
    assert [c["image"] for c in fake.calls] == [b"WEBP", b"PNG"]
    assert all(c["image_alt"] == ALT for c in fake.calls)


def test_alt_text_is_cut_at_the_bluesky_limit(monkeypatch, images):
    fake = FakeClient()
    monkeypatch.setattr(bluesky, "_client", lambda: fake)
    webp, _ = images
    bluesky.post_card("I'm a voter.", webp, "x" * (ALT_TEXT_LIMIT + 50))
    assert len(fake.calls[0]["image_alt"]) == ALT_TEXT_LIMIT


def test_blank_alt_text_is_refused_before_login(monkeypatch, images):
    monkeypatch.setattr(bluesky, "_client", lambda: pytest.fail("must not log in without alt text"))
    webp, _ = images
    with pytest.raises(ValueError, match="alt text"):
        bluesky.post_card("I'm a voter.", webp, "   ")


def test_every_queued_card_has_alt_text_within_the_limit():
    if not config.PROFILES_PATH.exists():
        pytest.skip("no posting queue built")
    from voterbot.sample import load_profiles

    profiles = load_profiles()
    assert profiles
    for profile in profiles:
        assert profile["alt_text"].strip() and len(profile["alt_text"]) <= ALT_TEXT_LIMIT
        assert "Cultural" not in profile["alt_text"] and "cultural, liberal" not in profile["alt_text"]  # the scale is the social one


def test_handle_pasted_with_an_at_sign_or_spaces_is_tidied(monkeypatch):
    monkeypatch.setenv("BLUESKY_HANDLE", " @britishvoterbot.bsky.social ")
    monkeypatch.setenv("BLUESKY_PASSWORD", " abcd-efgh-ijkl-mnop\n")
    assert bluesky.credentials() == ("britishvoterbot.bsky.social", "abcd-efgh-ijkl-mnop")


def test_missing_credentials_stop_before_login(monkeypatch):
    monkeypatch.delenv("BLUESKY_HANDLE", raising=False)
    monkeypatch.setenv("BLUESKY_PASSWORD", "x")
    with pytest.raises(SystemExit, match="BLUESKY_HANDLE"):
        bluesky.credentials()

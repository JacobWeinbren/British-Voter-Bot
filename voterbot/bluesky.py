"""Posting a card to Bluesky.

Credentials come from the environment: BLUESKY_HANDLE and BLUESKY_PASSWORD
(an app password). On GitHub they are repository secrets or variables, passed
in by .github/workflows/post.yml; locally, export them in the shell.
"""

from __future__ import annotations

import os
from pathlib import Path

from atproto import Client, models

from . import config

from .profile import ALT_TEXT_LIMIT

POST_TEXT_LIMIT = 300


def credentials() -> tuple[str, str]:
    """The handle and app password from the environment, tidied: a handle pasted as '@name.bsky.social'
    or with stray whitespace would otherwise be taken for an email address by the PDS ('InvalidEmail')."""
    handle = (os.environ.get("BLUESKY_HANDLE") or "").strip().lstrip("@").strip()
    password = (os.environ.get("BLUESKY_PASSWORD") or "").strip()
    if not handle or not password:
        raise SystemExit("BLUESKY_HANDLE and BLUESKY_PASSWORD are not set. On GitHub add them under Settings > Secrets and variables > Actions; "
                         "locally, export them before running `python -m voterbot post`.")
    return handle, password


def _client() -> Client:
    handle, password = credentials()
    client = Client()
    client.login(handle, password)  # note: the PDS allows only a handful of failed logins a day, so a bad secret stays bad for a while
    return client


def post_card(text: str, image_path: Path, alt_text: str, fallback_path: Path | None = None) -> str:
    """Post an image with alt text; returns the post URI.

    The image is sent as uploaded (lossless WebP by default) - the PDS sniffs
    the type itself. If the server refuses it, the PNG fallback is sent instead.
    """
    if len(text) > POST_TEXT_LIMIT:
        raise ValueError(f"post text is {len(text)} characters; the limit is {POST_TEXT_LIMIT}")
    if not alt_text.strip():
        raise ValueError("every image needs alt text")
    client = _client()
    attempts = [Path(image_path)] + ([Path(fallback_path)] if fallback_path else [])
    last_error: Exception | None = None
    for path in attempts:
        try:
            response = client.send_image(
                text=text,
                image=path.read_bytes(),
                image_alt=alt_text[:ALT_TEXT_LIMIT],
                image_aspect_ratio=models.AppBskyEmbedDefs.AspectRatio(width=config.CARD_WIDTH, height=config.CARD_HEIGHT),
            )
            return response.uri
        except Exception as error:  # noqa: BLE001 - try the next format, then re-raise
            last_error = error
    raise last_error  # type: ignore[misc]

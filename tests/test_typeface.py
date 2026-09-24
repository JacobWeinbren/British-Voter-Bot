"""The cards are drawn in Archivo, on this machine and on the posting runner alike.

For months every card went out in the fallback sans-serif: the fonts were linked by file://,
Chromium refused to read them from a page loaded with set_content, and nothing said so. The
fonts are inlined now, the runner checks them before it posts (`python -m voterbot fontcheck`),
and the renderer refuses to screenshot a card whose typeface failed. These start their own
browser, so they sit apart from the layout tests and their shared one.
"""

import pytest

from voterbot import config, render
from voterbot.render import CHROMIUM_ARGS, build_html

from test_card_layout import CARD


@pytest.fixture(scope="module")
def renders():
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        with sync_api.sync_playwright() as pw:
            pw.chromium.launch(args=CHROMIUM_ARGS).close()
    except Exception as error:  # no browser installed here
        pytest.skip(f"Chromium unavailable: {error}")


def test_the_font_check_the_runner_does_before_posting_passes(renders):
    assert render.check_fonts() == {weight: "loaded" for weight in config.FONT_WEIGHTS}


def test_a_card_whose_typeface_fails_is_never_rendered(renders, monkeypatch, tmp_path):
    """The old failure, reproduced: fonts linked by file:// error out, and the renderer must refuse."""
    broken = "".join(f'@font-face {{ font-family: "Archivo"; font-weight: {w}; src: url("file://{config.FONT_DIR}/Archivo-{w}.ttf"); }}'
                     for w in config.FONT_WEIGHTS)
    monkeypatch.setattr(render, "font_css", lambda: broken)
    with pytest.raises(RuntimeError, match="typeface failed to load"):
        render.screenshot_html(build_html(CARD), tmp_path / "card.png", config.CARD_WIDTH, config.CARD_HEIGHT)
    assert not (tmp_path / "card.png").exists()

"""Whether a card fits its canvas with every line of text at its design size.

The card never shrinks its text to make room: small type on a phone screen is the one thing a
card cannot afford. So the build composes each card to fit instead. It lays every card out in
Chromium at the design sizes and, where one runs past the canvas, composes it again with less of
its optional copy (profile.TRIMS) until it fits. The views still grow into any room left over.

The layout is the real one: the card's own HTML and CSS in headless Chromium, with the Archivo
files loaded once and each card swapped into the same page, which takes a few milliseconds a card.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from . import config
from .render import build_html, font_css

_SHELL = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
          '<style id="fonts">{fonts}</style><style id="card-style"></style></head><body></body></html>')

# Swap one card into the page (its script does not run, so nothing is grown or fitted) and return
# the height left over in the content column at design sizes - negative where the card runs past
# the canvas - and whether each vote label fits its half of the band.
_MEASURE = """html => {
  const doc = new DOMParser().parseFromString(html, "text/html");
  document.getElementById("card-style").textContent = doc.querySelector("style").textContent;
  document.body.innerHTML = doc.body.innerHTML;
  const content = document.getElementById("content");
  const style = getComputedStyle(content);
  const blocks = [...content.children];
  const used = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
    + blocks.reduce((sum, el) => sum + el.getBoundingClientRect().height, 0)
    + parseFloat(style.rowGap) * Math.max(0, blocks.length - 1);
  const labels = [...document.querySelectorAll(".journey .who")].every(el => el.scrollWidth <= el.clientWidth);
  return [content.clientHeight - used, labels];
}"""


class Measurer:
    """One headless Chromium page that lays out cards at their design sizes.

        with Measurer() as measure:
            room = measure.room(profile)   # pixels to spare; below zero, the card does not fit
    """

    def __enter__(self) -> "Measurer":
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch()
        self._page = self._browser.new_page(viewport={"width": config.CARD_WIDTH, "height": config.CARD_HEIGHT})
        self._page.set_content(_SHELL.format(fonts=font_css()), wait_until="load")
        faces = self._page.evaluate("""Promise.allSettled([...document.fonts].map(f => f.load()))
                                       .then(() => [...document.fonts].map(f => f.status))""")
        if faces != ["loaded"] * len(config.FONT_WEIGHTS):  # fallback metrics would measure a different card
            self.__exit__(None, None, None)
            raise RuntimeError(f"typeface failed to load, nothing measured: {faces}")
        return self

    def __exit__(self, *exc) -> None:
        self._browser.close()
        self._pw.stop()

    def room(self, profile: dict) -> float:
        """Height to spare at design sizes, in CSS pixels: below zero, the card runs past its canvas.

        A vote label too wide for its half of the band counts as not fitting too.
        """
        room, labels_fit = self._page.evaluate(_MEASURE, build_html(profile, fonts=False))
        return room if labels_fit else min(room, -1.0)

    def fits(self, profile: dict) -> bool:
        return self.room(profile) >= 0

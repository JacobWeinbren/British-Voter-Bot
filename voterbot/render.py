"""Turn a profile into the 1080x1350 card image.

The card is an HTML template (voterbot/templates/card.html) filled with Jinja2
and screenshotted with headless Chromium via Playwright. Fonts are loaded from
assets/fonts so rendering is identical offline and in CI.
"""

from __future__ import annotations

import html
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

from . import config, geo

_env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR), autoescape=select_autoescape(["html"]))


def _bold(text: str) -> str:
    return f"<strong>{html.escape(text)}</strong>"


def _emphasise(template: str, **parts: str) -> str:
    """Fill `{name}` slots with bold, escaped text; everything else is escaped plainly."""
    out = html.escape(template)
    for key, value in parts.items():
        out = out.replace(html.escape("{" + key + "}"), _bold(value))
    return out


def band_colours(profile: dict) -> tuple[str, str]:
    """Party colour for a named party; otherwise undecided, wouldn't vote and other party each get their own."""
    party = profile.get("intention_party")
    if party:
        return config.PARTY_COLOURS.get(party, config.OTHER_PARTY_COLOURS)
    text = profile["band_text"]
    if "don't know" in text:
        return config.DONT_KNOW_COLOURS
    if "wouldn't" in text:  # "wouldn't vote" and "wouldn't either"
        return config.NO_VOTE_COLOURS
    return config.OTHER_PARTY_COLOURS


def build_html(profile: dict) -> str:
    """Render the card HTML for one profile (a dict as stored in profiles.jsonl)."""
    band_bg, band_ink = band_colours(profile)
    headline = _emphasise(profile["headline"]["template"], **profile["headline"]["bold"])
    place = html.escape(profile["headline"]["bold"]["place"]).replace("-", "&#8209;")  # keep "Stratford-on-Avon" on one line
    headline = headline.replace(_bold(profile["headline"]["bold"]["place"]), f'<strong class="place">{place}</strong>')
    template = _env.get_template("card.html")
    return template.render(
        width=config.CARD_WIDTH, height=config.CARD_HEIGHT,
        map_width=config.MAP_WIDTH, map_height=config.MAP_HEIGHTS.get(profile["country"], config.MAP_HEIGHT),
        font_dir=str(config.FONT_DIR),
        ink=config.INK, body=config.BODY, secondary=config.SECONDARY, accent=config.ACCENT,
        bubble_fill=config.BUBBLE_FILL, track=config.TRACK, middle_band=config.MIDDLE_BAND, scale_band=config.SCALE_BAND,
        band_bg=band_bg, band_ink=band_ink,
        alt_title=profile["alt_text"][:80],
        headline_html=headline,
        life_html=_emphasise(profile["life"]["template"], **profile["life"]["bold"]),
        media_html=_emphasise(profile["media"]["template"], **profile["media"]["bold"]) if profile.get("media") else "",
        top_issue=profile.get("top_issue"), no_single_issue=profile.get("no_single_issue"),
        map_svg=geo.nation_svg(profile["country"], profile.get("constituency_code"), height=config.MAP_HEIGHTS.get(profile["country"], config.MAP_HEIGHT)),
        bubbles_html=[_emphasise(b["template"], **b["bold"]) for b in profile["bubbles"]],
        views_heading=f"{profile.get('possessive', 'their').capitalize()} views, from {profile.get('possessive', 'their')} survey answers",
        econ_pct=profile["econ_pct"], cultural_pct=profile["cultural_pct"],
        econ_iqr=profile.get("econ_iqr", [25, 75]), cultural_iqr=profile.get("cultural_iqr", [25, 75]),
        band_text=profile["band_text"],
        footnote=profile.get("footnote", "Voting intention"),
        fieldwork=config.FIELDWORK_LABEL,
    )


def render_png(profile: dict, out_path: Path, keep_html: bool = False, scale: float = 1.0) -> Path:
    """Write the card PNG for a profile and return its path.

    `scale` multiplies the 1080x1350 layout (the posting pipeline uses
    config.RENDER_SCALE for a 1600x2000 image); if the file would exceed the
    blob limit the scale steps down until it fits.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    page_html = build_html(profile)
    if keep_html:
        out_path.with_suffix(".html").write_text(page_html, encoding="utf-8")
    for factor in (scale, 1.25, 1.0):
        screenshot_html(page_html, out_path, config.CARD_WIDTH, config.CARD_HEIGHT, scale=factor)
        optimise_png(out_path)
        if out_path.stat().st_size <= config.MAX_IMAGE_BYTES or factor <= 1.0:
            break
    return out_path


def optimise_png(path: Path) -> Path:
    """Recompress a PNG losslessly (smaller file, identical pixels)."""
    with Image.open(path) as image:
        image.save(path, format="PNG", optimize=True, compress_level=9)
    return path


def write_webp(png_path: Path) -> Path:
    """A lossless WebP beside the PNG - usually a third smaller, identical pixels."""
    webp = png_path.with_suffix(".webp")
    with Image.open(png_path) as image:
        image.save(webp, format="WEBP", lossless=True, quality=100, method=6)
    return webp


def render_card(profile: dict, out_png: Path, scale: float = config.RENDER_SCALE) -> tuple[Path, Path]:
    """The posting pipeline: a 1600x2000 card as optimised PNG and lossless WebP."""
    png = render_png(profile, out_png, scale=scale)
    return png, write_webp(png)


def screenshot_html(page_html: str, out_path: Path, width: int, height: int, selector: str = "#card", scale: float = 1.0) -> None:
    """Screenshot one element of an HTML document; `scale` sets the device pixel ratio (lossless PNG)."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        page.set_content(page_html, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(150)  # let the fit script and font layout settle
        page.locator(selector).screenshot(path=str(out_path), type="png")
        browser.close()

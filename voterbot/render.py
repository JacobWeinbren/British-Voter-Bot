"""Turn a profile into the 1080x1350 card image.

The card is an HTML template (voterbot/templates/card.html) filled with Jinja2
and screenshotted with headless Chromium via Playwright. The Archivo files in
assets/fonts travel inside the page (font_css), so rendering is identical offline
and in CI.
"""

from __future__ import annotations

import base64
import functools
import html
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image
from playwright.sync_api import sync_playwright

from . import config, geo
from .persona import article

_env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR), autoescape=select_autoescape(["html"]))

# Every Chromium that lays out a card starts with these. On Linux, Chromium hints glyphs to the
# pixel grid by default, which widens a line just enough that about one card in sixty wraps
# differently on the posting runner than on the Mac that built the queue - a whole extra line,
# enough to push a card that fitted past its canvas. Unhinted, Linux lays out every card exactly as
# macOS does (3,000 queued cards compared in the Playwright Linux image), and macOS is unchanged.
CHROMIUM_ARGS = ["--font-render-hinting=none"]


class CardOverflow(RuntimeError):
    """The card runs past its canvas with its text at design size, so nothing was rendered."""


@functools.lru_cache(maxsize=1)
def font_css() -> str:
    """@font-face rules for Archivo with each weight's file inlined as a data URI.

    A page handed to Chromium with set_content has no origin allowed to read file:// URLs, so
    fonts linked that way fail without a word and every card falls back to the system sans-serif.
    """
    rules = []
    for weight in config.FONT_WEIGHTS:
        data = base64.b64encode((config.FONT_DIR / f"Archivo-{weight}.ttf").read_bytes()).decode("ascii")
        rules.append(f'@font-face {{ font-family: "Archivo"; font-style: normal; font-weight: {weight}; '
                     f'src: url("data:font/ttf;base64,{data}") format("truetype"); }}')
    return "\n".join(rules)


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


# The first sentence of a stored vote line - how they voted in 2024 - and what the card's 2024 step says.
PAST_VOTE = {
    "In 2024 I didn't vote": ("Didn't vote", config.NO_VOTE_COLOURS),
    "In 2024 I voted for a smaller party": ("A smaller party", config.OTHER_PARTY_COLOURS),
    "In 2024 I voted for an independent": ("An independent", config.OTHER_PARTY_COLOURS),
    "In 2024 I voted": ("Voted", config.DONT_KNOW_COLOURS),  # a party the survey file does not name
    "I can't remember how I voted in 2024": ("Can't remember", config.DONT_KNOW_COLOURS),
    "I'm not sure whether I voted in 2024": ("Not sure I voted", config.DONT_KNOW_COLOURS),
}


def vote_steps(profile: dict) -> dict:
    """The stored vote line as the band's two steps: how they voted in 2024, and how they would today.

    Each step is a short label in its own colour - the party's where there is one, the lilac-grey for a
    smaller party or an independent, grey for not voting or not knowing. A qualifier ("if pushed",
    "closest to Labour") sits beside "Today", and takes the asterisk when the footnote explains it.
    An unfamiliar sentence raises rather than printing something the line never said.
    """
    past, _, today = profile["band_text"].rstrip("*").partition(". ")
    party = re.fullmatch(r"In 2024 I voted (.+)", past)
    if party and party.group(1) in config.PARTY_COLOURS:
        then, (then_bg, then_ink) = party.group(1), config.PARTY_COLOURS[party.group(1)]
    elif past in PAST_VOTE:
        then, (then_bg, then_ink) = PAST_VOTE[past]
    else:
        raise ValueError(f"unrecognised 2024 vote: {past!r}")

    note = ""
    if today == "Today I still would":
        now = "Still " + (then[0].lower() + then[1:] if then.startswith(("A ", "An ")) else then)
    elif match := re.fullmatch(r"Today I'd vote (?:for )?(.+?)( \(if pushed\))?", today):
        name = match.group(1)
        now = {"a smaller party": "A smaller party", "an independent": "An independent"}.get(name, name)
        note = "if pushed" if match.group(2) else ""
    elif today == "Today I don't know who I'd vote for":
        now = "Don't know"
    elif today == "Today I wouldn't vote":
        now = "Wouldn't vote"
    elif match := re.fullmatch(r"Today I wouldn't either(?:, but I'm an? (.+) supporter| - at a push, I'm closest to (.+))?", today):
        now = "Still wouldn't vote"
        note = f"{article(match.group(1))} {match.group(1)} supporter" if match.group(1) else f"closest to {match.group(2)}" if match.group(2) else ""
    else:
        raise ValueError(f"unrecognised vote today: {today!r}")
    now_bg, now_ink = band_colours(profile)
    return {"then": then, "then_bg": then_bg, "then_ink": then_ink, "now": now, "now_bg": now_bg, "now_ink": now_ink, "note": note}


def map_box(profile: dict) -> tuple[int, int]:
    """The map's width and height: the handoff's box, or a larger one where there are no scales to fit in.

    A card whose text would not otherwise fit at design size may carry a `map_scale` below 1
    (profile.TRIMS): the map gives up a little room so that no line of text has to.
    """
    width, height = config.MAP_WIDTH, config.MAP_HEIGHTS.get(profile["country"], config.MAP_HEIGHT)
    scale = profile.get("map_scale", 1.0)
    if profile.get("econ_pct") is None or profile.get("cultural_pct") is None:
        scale *= config.MAP_SCALE_WITHOUT_SCALES
    return round(width * scale), round(height * scale)


def build_html(profile: dict, fonts: bool = True) -> str:
    """Render the card HTML for one profile (a dict as stored in profiles.jsonl).

    `fonts=False` leaves out the inlined Archivo files, for a page that has loaded them already
    (fit.Measurer lays out thousands of cards in one page).
    """
    map_width, map_height = map_box(profile)
    headline = _emphasise(profile["headline"]["template"], **profile["headline"]["bold"])
    place = html.escape(profile["headline"]["bold"]["place"]).replace("-", "&#8209;")  # keep "Stratford-on-Avon" on one line
    headline = headline.replace(_bold(profile["headline"]["bold"]["place"]), f'<strong class="place">{place}</strong>')
    template = _env.get_template("card.html")
    return template.render(
        width=config.CARD_WIDTH, height=config.CARD_HEIGHT,
        map_width=map_width, map_height=map_height,
        font_css=font_css() if fonts else "",
        ink=config.INK, body=config.BODY, secondary=config.SECONDARY, accent=config.ACCENT,
        bubble_fill=config.BUBBLE_FILL, track=config.TRACK, middle_band=config.MIDDLE_BAND, scale_band=config.SCALE_BAND,
        alt_title=profile["alt_text"][:80],
        headline_html=headline,
        life_html=_emphasise(profile["life"]["template"], **profile["life"]["bold"]),
        media_html=_emphasise(profile["media"]["template"], **profile["media"]["bold"]) if profile.get("media") else "",
        top_issue=profile.get("top_issue"), no_single_issue=profile.get("no_single_issue"),
        map_svg=geo.nation_svg(profile["country"], profile.get("constituency_code"), width=map_width, height=map_height),
        bubbles_html=[_emphasise(b["template"], **b["bold"]) for b in profile["bubbles"]],
        views_heading=f"{profile.get('possessive', 'their').capitalize()} views, from {profile.get('possessive', 'their')} survey answers",
        econ_pct=profile["econ_pct"], cultural_pct=profile["cultural_pct"],
        econ_iqr=profile.get("econ_iqr", [25, 75]), cultural_iqr=profile.get("cultural_iqr", [25, 75]),
        vote=vote_steps(profile),
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
        browser = pw.chromium.launch(args=CHROMIUM_ARGS)
        page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=scale)
        page.set_content(page_html, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_function("document.body.dataset.fit !== 'pending'")  # a card's fit script has run
        page.wait_for_timeout(50)  # and its last change has been laid out
        failed = page.evaluate("[...document.fonts].filter(f => f.status === 'error').map(f => f.family + ' ' + f.weight)")
        if failed:  # never let an image out in the fallback sans-serif - that is how the old bug went unseen
            browser.close()
            raise RuntimeError(f"typeface failed to load, nothing rendered: {', '.join(failed)}")
        if page.evaluate("document.body.dataset.fit") == "overflow":  # the card never shrinks its text to fit
            browser.close()
            raise CardOverflow("the card runs past its canvas with its text at design size, nothing rendered "
                               "(the build composes every card to fit: voterbot/fit.py)")
        page.locator(selector).screenshot(path=str(out_path), type="png")
        browser.close()


def check_fonts() -> dict[int, str]:
    """Load every Archivo weight in Chromium the way a card does, and report each one's status.

    `python -m voterbot fontcheck` runs this on the posting runner before anything is posted.
    """
    text = "".join(f'<p style="font: {weight} 20px Archivo">Archivo {weight}</p>' for weight in config.FONT_WEIGHTS)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=CHROMIUM_ARGS)
        page = browser.new_page()
        page.set_content(f"<!doctype html><style>{font_css()}</style><body>{text}</body>", wait_until="load")
        faces = page.evaluate("""Promise.allSettled([...document.fonts].map(f => f.load()))
                                 .then(() => [...document.fonts].map(f => [f.weight, f.status]))""")
        browser.close()
    return {int(weight): status for weight, status in faces}

"""Bluesky profile assets: a Union Jack banner and an avatar with the persona dot.

Both follow the design handoff: flat SVG geometry using the official flag
construction (#012169 / #C8102E / white), cropped full-bleed.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, geo
from .render import optimise_png, screenshot_html, write_webp

CREDITS = [("Jacob Weinbren", "@jacobweinbren.bsky.social"), ("Lawrence McKay", "@lawrencemckay.bsky.social"),
           ("Chris Terry-Enescu", "@cjterry.bsky.social")]
CREDIT = " · ".join(name for name, _ in CREDITS)
SUBTITLE = "Taken one at a time, voters are messier - and more interesting - than any stereotype."
CADENCE = {1: "One voter a day", 2: "Two voters a day", 3: "Three voters a day", 4: "Four voters a day"}
CADENCE_SENTENCE = {1: "One voter a day.", 2: "One voter every morning and evening.", 3: "One voter every morning, midday and evening.", 4: "One voter, four times a day."}

# Text alternatives for the brand images, saved next to each PNG for pasting in when uploading.
BANNER_ALT = "The Union Jack."
AVATAR_ALT = "The Union Jack with a magenta dot at its centre - the marker that shows where each voter lives on the cards."


def intro_poster_alt(respondents: str, cadence: str) -> str:
    """Text alternative for the poster, in reading order, with each example graphic described in a few words."""
    return (
        "Introduction poster for British Voter Bot. Headline: Real British voters, one at a time. Every card on this account is one real, anonymous "
        "respondent to the British Election Study, Britain's largest survey of voters. Each card says who they are, what they "
        "think and how they'd vote, in their own answers to questions written by the BES. The views are the respondent's own, "
        "not ours. How to read a card, five rows: "
        "1. A map of Wales with a magenta dot. The dot is where they live: each voter is drawn over their home nation, marked "
        "at their constituency. "
        "2. A lilac speech bubble. The bubbles are their views: favourite and least favourite leader, the issues they care "
        "about, how they see their nation - each one the respondent's own answer to a BES question, not the opinion of this "
        "account, its authors or the BES. "
        "3. A slider with a magenta dot left of centre, a black tick at the centre and a lilac band around it. The scales show "
        "where they sit: two BES 0 to 10 scales, economic left to right and social liberal to authoritarian. The tick is the "
        "centre of the scale (5); the lilac band is the voters' interquartile range. "
        "4. A magenta block reading 2024 to today. The band is their vote: how they voted in 2024 and who they'd vote for now, "
        "coloured by the party they're backing today, grey if they're undecided or wouldn't vote. "
        f"5. 24 lilac dots, one magenta. Together, they are Britain in miniature: voters are drawn from the "
        f"wave's {respondents} real respondents in proportion to BES survey weights, so the feed reflects the British adult "
        f"population by age, gender, region, past vote and more. {cadence} BES Wave {config.WAVE}, YouGov, {config.FIELDWORK_LABEL}. "
        "Closing band, magenta: No one is the average voter. " + SUBTITLE + " "
        f"Credits: {'; '.join(f'{name}, {handle}' for name, handle in CREDITS)}."
    )

_FLAG_SVG = """
<svg viewBox="0 0 60 30" preserveAspectRatio="xMidYMid slice" width="{w}" height="{h}" style="position:absolute;inset:0">
  <clipPath id="uk"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath>
  <rect width="60" height="30" fill="#012169"/>
  <path d="M0,0 L60,30 M60,0 L0,30" stroke="#ffffff" stroke-width="6"/>
  <path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#uk)" stroke="#C8102E" stroke-width="4"/>
  <path d="M30,0 v30 M0,15 h60" stroke="#ffffff" stroke-width="10"/>
  <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6"/>
</svg>
"""

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;background:#fff}}
#card{{width:{w}px;height:{h}px;position:relative;overflow:hidden;background:#012169}}
.dot{{position:absolute;left:50%;top:50%;width:230px;height:230px;border-radius:50%;background:{accent};
     border:22px solid #ffffff;transform:translate(-50%,-50%);box-sizing:border-box}}
</style></head><body><div id="card">{flag}{extra}</div></body></html>"""


def banner_html(width: int = 1500, height: int = 500) -> str:
    return _PAGE.format(w=width, h=height, accent=config.ACCENT, flag=_FLAG_SVG.format(w=width, h=height), extra="")


def avatar_html(size: int = 1000) -> str:
    return _PAGE.format(w=size, h=size, accent=config.ACCENT, flag=_FLAG_SVG.format(w=size, h=size),
                        extra='<div class="dot"></div>')


def respondent_count() -> int:
    """How many people took wave 31, read from the panel cache when it is there."""
    if config.PANEL_CACHE.exists():
        import pyarrow.parquet as pq

        return pq.ParquetFile(config.PANEL_CACHE).metadata.num_rows
    return config.WAVE_RESPONDENTS


def intro_html(respondents: int | None = None) -> str:
    """The pinned intro poster: what the bot is and how to read a card."""
    env = Environment(loader=FileSystemLoader(config.TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    montgomeryshire = next(c for c in geo.constituencies().values() if c.name.startswith("Montgomeryshire"))
    return env.get_template("intro.html").render(
        width=config.CARD_WIDTH, height=config.CARD_HEIGHT, font_dir=str(config.FONT_DIR),
        ink=config.INK, body=config.BODY, secondary=config.SECONDARY, accent=config.ACCENT,
        bubble_fill=config.BUBBLE_FILL, track=config.TRACK, middle_band=config.MIDDLE_BAND, scale_band=config.SCALE_BAND,
        map_svg=geo.nation_svg(3, montgomeryshire.code, width=120, height=146),
        respondents=f"{respondents or respondent_count():,}",
        wave=config.WAVE, fieldwork=config.FIELDWORK_LABEL,
        cadence=CADENCE.get(config.POSTS_PER_DAY, f"{config.POSTS_PER_DAY} voters a day"),
        cadence_sentence=CADENCE_SENTENCE.get(config.POSTS_PER_DAY, f"{config.POSTS_PER_DAY} voters a day."),
        credits=CREDITS, subtitle=SUBTITLE,
    )


def _write_alt(image: Path, text: str) -> None:
    """Keep each image's text alternative beside it, ready to paste in when uploading."""
    image.with_suffix(".alt.txt").write_text(text + "\n", encoding="utf-8")


def make_intro_poster(out_dir: Path = config.BRAND_DIR) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    poster = out_dir / "intro-poster.png"
    respondents = respondent_count()
    screenshot_html(intro_html(respondents), poster, config.CARD_WIDTH, config.CARD_HEIGHT, scale=config.RENDER_SCALE)  # 1600x2000
    optimise_png(poster)
    write_webp(poster)
    cadence = CADENCE_SENTENCE.get(config.POSTS_PER_DAY, f"{config.POSTS_PER_DAY} voters a day.")
    _write_alt(poster, intro_poster_alt(f"{respondents:,}", cadence))
    return poster


def make_brand_assets(out_dir: Path = config.BRAND_DIR) -> tuple[Path, Path]:
    """Write banner.png (1500x500) and avatar.png (1000x1000), each with its alt text, to the outputs folder."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    banner = out_dir / "banner.png"
    avatar = out_dir / "avatar.png"
    screenshot_html(banner_html(), banner, 1500, 500, scale=2.0)   # 3000x1000
    screenshot_html(avatar_html(), avatar, 1000, 1000, scale=2.0)  # 2000x2000
    for image in (banner, avatar):
        optimise_png(image)
        write_webp(image)
    _write_alt(banner, BANNER_ALT)
    _write_alt(avatar, AVATAR_ALT)
    return banner, avatar

"""Paths, constants and design tokens shared across the bot."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Data
RAW_DIR = ROOT / "data" / "raw"
REFERENCE_DIR = ROOT / "data" / "reference"
PROCESSED_DIR = ROOT / "data" / "processed"
SAV_PATH = RAW_DIR / "BES2024_W31_Panel_v31.05.sav"
CODEBOOK_PATH = RAW_DIR / "Bes_wave31Documentationv31.05-1.pdf"  # the questionnaire: scanned by `audit` for questions the SPSS file leaves out
PANEL_CACHE = PROCESSED_DIR / "w31_panel.parquet"
CONSTITUENCIES_PATH = REFERENCE_DIR / "pcon24_buc.geojson"
COUNTRIES_PATH = REFERENCE_DIR / "countries24_buc.geojson"

# Outputs
OUTPUT_DIR = ROOT / "outputs"
PROFILES_PATH = OUTPUT_DIR / "profiles.jsonl.gz"
POSITION_PATH = OUTPUT_DIR / "position.txt"
LAST_POST_PATH = OUTPUT_DIR / "last_post.txt"  # UTC time of the last post; the workflow posts again once a later slot has begun
CARDS_DIR = OUTPUT_DIR / "cards"
PREVIEW_DIR = OUTPUT_DIR / "previews"
BRAND_DIR = OUTPUT_DIR / "brand"

# Assets
ASSETS_DIR = ROOT / "assets"
FONT_DIR = ASSETS_DIR / "fonts"
TEMPLATE_DIR = ROOT / "voterbot" / "templates"

# Survey
WAVE = 31
WEIGHT_COLUMN = "wt_new_W31"
FIELDWORK_LABEL = "May-June 2026"  # wave 31 fieldwork, from the codebook introduction
EARLIEST_WAVE = 20  # rule of thumb: ignore questions last asked before wave 20

# Sampling: no cap - every eligible respondent is queued, in weighted-draw order.
# Pass --count to `build` to stop early for a test run.
PROFILE_COUNT = None
MINORITY_SHARE = 0.20  # ethnic minorities (p_ethnicity2 codes 5+) are boosted to a fifth of the feed; the mix within each side of the split stays survey-weighted
RANDOM_SEED = 31_2026
SLOT_HOURS = (10, 13, 17, 21)  # posting times, UK wall clock: see voterbot/schedule.py and .github/workflows/post.yml
POSTS_PER_DAY = len(SLOT_HOURS)
RENDER_SCALE = 2000 / 1350  # post images at 1600x2000: Bluesky's CDN caps the long side at 2000px, so nothing is resampled
MAX_IMAGE_BYTES = 950_000   # under the 1,000,000-byte limit for image blobs
MAX_OPINIONS = 3  # opinion bubbles besides the leader line: four bubbles in all (five was tried and felt crowded)
REPEAT_GAP_CYCLES = 3  # a voter can come round again only after this many yearly cycles
WAVE_RESPONDENTS = 31_392  # fallback for the intro poster if the panel cache is absent

# Card geometry
CARD_WIDTH = 1080
CARD_HEIGHT = 1350
MAP_WIDTH = 340
MAP_HEIGHT = 460  # England; see MAP_HEIGHTS
MAP_HEIGHTS = {1: 460, 2: 500, 3: 440}  # map box per nation (handoff turn 5: England 340x460, Wales 340x440)

# Design tokens (from the design handoff)
INK = "#201e1d"
BODY = "#3c3744"
SECONDARY = "#6b6371"
ACCENT = "#c2255c"
BUBBLE_FILL = "#f4eef6"
TRACK = "#eceae7"
MIDDLE_BAND = "#cfc5d6"  # decorative lilac-grey: the smaller-party band, poster dots
SCALE_BAND = "#9678ad"  # the middle half of voters: a lilac that still passes 3:1 against white and the track (the handoff's #cfc5d6 is 1.7:1)
MAP_FILL = "#6f9a6e"  # a shade deeper than the handoff's #84a883 so the white-ringed dot reaches 3:1
MAP_STROKE = "#41603f"

# Footer band colours keyed by party short name: (background, text)
PARTY_COLOURS: dict[str, tuple[str, str]] = {
    "SNP": ("#fdf38e", INK),
    "Labour": ("#e4003b", "#ffffff"),
    "Conservative": ("#0b6fc0", "#ffffff"),  # a shade deeper than #0087dc so 16px white text reaches 4.5:1
    "Reform UK": ("#12b6cf", INK),
    "Lib Dem": ("#faa61a", INK),
    "Green": ("#02a95b", INK),  # dark text: white on this green is only 3:1
    "Plaid Cymru": ("#005b54", "#ffffff"),
}
OTHER_PARTY_COLOURS = (MIDDLE_BAND, INK)  # a smaller party or an independent: lilac-grey, a colour no party owns (black would read as Restore)
DONT_KNOW_COLOURS = ("#dcd9d6", INK)  # undecided: the handoff's grey
NO_VOTE_COLOURS = ("#dcd9d6", INK)  # wouldn't vote: the same grey as undecided (handoff turn 5)
FALLBACK_COLOURS = OTHER_PARTY_COLOURS

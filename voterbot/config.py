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
RELIGION_COUNTS_PATH = REFERENCE_DIR / "religion_pcon24.csv"  # Census 2021 TS030 by 2024 constituency (England and Wales)

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
FONT_WEIGHTS = (400, 500, 600, 700, 800)  # the Archivo files in FONT_DIR, inlined into every page (render.font_css)
TEMPLATE_DIR = ROOT / "voterbot" / "templates"

# Survey
WAVE = 31
WEIGHT_COLUMN = "wt_new_W31"
FIELDWORK_LABEL = "May-June 2026"  # wave 31 fieldwork, from the codebook introduction
EARLIEST_WAVE = 20  # June 2020, the first wave after the 2019 general election: older answers predate Covid, Brexit taking effect and three changes of prime minister
# A faith the census counts at this many people or fewer in someone's constituency is left off
# their card: where a group is that small, naming it alongside a seat, an ethnicity and a gender
# comes close to naming the respondent. Ten is the usual floor in statistical disclosure control
# for publishing a count of people. See persona.faith_is_rare.
RARE_FAITH_THRESHOLD = 10

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
LIFE_DETAILS = 2  # human details drawn for the life paragraph besides home, money, work and class

# Choosing what reaches a card. Every draw - the opinion bubbles, the money sentence, the life
# details - is solved for (voterbot/balance.py) so the feed follows the targets below rather than
# whatever the BES happened to ask most people. These are the dials, and each is a stated choice:
#
# Half of the general bubbles follow what voters in each nation name as the most important issue
# facing the country (the BES's own question, measured at build time); the other half are spread
# evenly over every subject, so the ones nobody names still get a hearing.
SALIENCE_SHARE = 0.5
# No view or fact appears on more than half the cards that could carry it: an answer only a
# handful of people gave cannot be pushed further than that, or everyone who gave it would say it
# every time they came round.
MAX_APPEARANCE = 0.5
# A middling answer ("about right", "neither well nor badly") is drawn at a fifth of the weight of
# a view either way: surveys nudge people towards the middle option, and a view says more.
NEUTRAL_WEIGHT = 0.2
# How often a card's last bubble is about nation and identity. In Scotland and Wales the
# constitutional question is the second axis of politics; in England it is less of a talking point.
NATION_BUBBLE_CHANCE = {1: 0.45, 2: 0.85, 3: 0.85}
# A personality or risk trait is mentioned only for the outer tenth of the panel either side,
# measured at build time: "I'm an extrovert" should mean more extrovert than most people.
TRAIT_TAIL = 0.10
# Line budgets, from the card as drawn: a line of the life paragraph holds about 100 characters of
# Archivo at 22px, a line of the news paragraph about 115 at 19px (measured over 400 queued cards).
# They are a first cut per paragraph. Whether the whole card fits is measured after: the build lays
# every card out at its design sizes and leaves optional copy off any that would run over (voterbot/fit.py).
LIFE_MAX_LINES, LIFE_CHARS_PER_LINE = 4, 100
MEDIA_MAX_LINES, MEDIA_CHARS_PER_LINE = 3, 115
# The blocks may run into the 32px padding above the vote band, but never closer to it than this,
# or the scale labels sit on the band: half the padding, kept on every card (the card's own fit
# script and voterbot/fit.py both hold to it).
BAND_CLEARANCE = 16
GENERATOR = 4  # stamped on every built card; tests of build-time behaviour apply to queues built by this version
REPEAT_GAP_CYCLES = 3  # a voter can come round again only after this many yearly cycles
# How often one exact sentence may come round: at four cards a day, no more than twice a week. A
# sentence family on many cards (class, the leader line) needs as many wordings as that takes; a
# fact on few cards needs just one (tests/test_copy.py measures it on a built queue).
MAX_WORDING_SHARE = 2 / (7 * POSTS_PER_DAY)
WAVE_RESPONDENTS = 31_392  # fallback for the intro poster if the panel cache is absent

# Card geometry
CARD_WIDTH = 1080
CARD_HEIGHT = 1350
MAP_WIDTH = 340
MAP_HEIGHT = 460  # England; see MAP_HEIGHTS
MAP_HEIGHTS = {1: 460, 2: 500, 3: 440}  # map box per nation (handoff turn 5: England 340x460, Wales 340x440)
# A card whose respondent skipped the value batteries has no scales, which frees about 240px; the map
# grows into it, so the card still reads as finished rather than as a card with a hole in it.
MAP_SCALE_WITHOUT_SCALES = 1.3

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

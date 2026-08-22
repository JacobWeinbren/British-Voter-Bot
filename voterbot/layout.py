"""A cheap estimate of whether a card's bubbles fit, calibrated against real renders of the 2b layout.

Only consulted when config.MAX_OPINIONS allows more than three opinions; the
turn-5 layout (tighter text, 340px map) has slightly more room, so the estimate
errs on the safe side there.

Measured on rendered cards: the headline, life, media and issue blocks plus the
middle row (map and bubbles) always add up to 806px, or 767px when the vote band
wraps to two lines (36px block gaps, 28/18px inside the intro); the spectrums
block is a fixed 200px plus its gap. Line
breaks follow character counts closely enough to estimate the block heights.
"""

from __future__ import annotations

import math

ROW_TOTAL = 806            # middle row + headline + life + media + issue line, one-line band
TWO_LINE_BAND = 39         # extra height when the band text wraps
TWO_LINE_BAND_CHARS = 78   # the band shrinks to 24px before wrapping; longer than this still wraps
SPECTRUMS = 236            # the two scales block plus its gap, when present
ISSUE_LINE = 36
MARGIN = 16                # breathing room below the last bubble
BUBBLE_GAP = 20
LINE = {"head": (50, 51.2), "life": (92, 33.35), "media": (105, 29.0), "bubble": (47, 31.0)}  # chars per line, line height


def lines(text: str, kind: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / LINE[kind][0]))


def block_height(text: str, kind: str) -> float:
    return lines(text, kind) * LINE[kind][1]


def bubble_height(text: str) -> float:
    return 36 + block_height(text, "bubble")


def middle_room(head: str, life: str, media: str, has_issue: bool, has_scales: bool, band_text: str) -> float:
    """Vertical room for the map-and-bubbles row."""
    room = ROW_TOTAL - block_height(head, "head") - block_height(life, "life") - block_height(media, "media")
    room -= ISSUE_LINE if has_issue else 0
    room -= TWO_LINE_BAND if len(band_text) > TWO_LINE_BAND_CHARS else 0
    room += 0 if has_scales else SPECTRUMS
    return room


def bubbles_fit(bubbles: list[str], room: float) -> bool:
    column = sum(bubble_height(b) for b in bubbles) + BUBBLE_GAP * (len(bubbles) - 1)
    return column <= room - MARGIN

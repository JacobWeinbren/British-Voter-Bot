"""Nation outlines and constituency markers as inline SVG.

The card shows the respondent's nation (England, Scotland or Wales) with a dot
on their 2024 Westminster constituency. Geometry comes from the ONS Open
Geography "ultra generalised" boundary files kept in data/reference, projected
with a plain Mercator fit to the map box - no external libraries needed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache

from . import config

NATION_CODES = {1: "E92000001", 2: "S92000003", 3: "W92000004"}
NATION_NAMES = {1: "England", 2: "Scotland", 3: "Wales"}


@dataclass(frozen=True)
class Constituency:
    code: str
    name: str
    lon: float
    lat: float


@lru_cache(maxsize=1)
def constituencies() -> dict[str, Constituency]:
    """2024 constituencies keyed by ONS code, with population-weighted centroids."""
    with open(config.CONSTITUENCIES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    out: dict[str, Constituency] = {}
    for feature in data["features"]:
        p = feature["properties"]
        out[p["PCON24CD"]] = Constituency(p["PCON24CD"], p["PCON24NM"], float(p["LONG"]), float(p["LAT"]))
    return out


@lru_cache(maxsize=4)
def nation_polygons(country_code: int) -> tuple[tuple[tuple[float, float], ...], ...]:
    """Outer rings of a nation, as tuples of (lon, lat)."""
    with open(config.COUNTRIES_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    wanted = NATION_CODES[country_code]
    for feature in data["features"]:
        if feature["properties"]["CTRY24CD"] != wanted:
            continue
        geom = feature["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        return tuple(tuple((float(x), float(y)) for x, y in poly[0]) for poly in polys)
    raise KeyError(f"nation {wanted} not found in {config.COUNTRIES_PATH}")


def _mercator(lon: float, lat: float) -> tuple[float, float]:
    x = math.radians(lon)
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    return x, -y  # flip so north is up in screen space


class Projection:
    """Mercator projection fitted to a box with an inset, like d3's fitExtent."""

    def __init__(self, rings, width: float, height: float, inset: float = 8.0):
        xs, ys = [], []
        for ring in rings:
            for lon, lat in ring:
                x, y = _mercator(lon, lat)
                xs.append(x)
                ys.append(y)
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        scale = min((width - 2 * inset) / (max_x - min_x), (height - 2 * inset) / (max_y - min_y))
        self.scale = scale
        # centre the projected bbox in the box
        self.offset_x = inset + ((width - 2 * inset) - (max_x - min_x) * scale) / 2 - min_x * scale
        self.offset_y = inset + ((height - 2 * inset) - (max_y - min_y) * scale) / 2 - min_y * scale

    def __call__(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = _mercator(lon, lat)
        return x * self.scale + self.offset_x, y * self.scale + self.offset_y


def nation_path(country_code: int, width: int = config.MAP_WIDTH, height: int = config.MAP_HEIGHT,
                tolerance: float = 1.4, min_extent: float = 7.0) -> tuple[str, Projection]:
    """SVG path data for a nation outline plus the projection used to draw it.

    Points closer than `tolerance` px to the previous one are dropped and islets
    whose bounding box is smaller than `min_extent` px are culled, matching the
    reference design's simplification.
    """
    rings = nation_polygons(country_code)
    proj = Projection(rings, width, height)
    parts: list[str] = []
    for ring in rings:
        pts: list[tuple[float, float]] = []
        for lon, lat in ring:
            p = proj(lon, lat)
            if not pts or math.hypot(p[0] - pts[-1][0], p[1] - pts[-1][1]) >= tolerance:
                pts.append(p)
        if len(pts) < 4:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs)) + (max(ys) - min(ys)) < min_extent:
            continue
        parts.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
    return "".join(parts), proj


def nation_svg(country_code: int, constituency_code: str | None,
               width: int = config.MAP_WIDTH, height: int = config.MAP_HEIGHT) -> str:
    """Complete inline SVG: sage-green nation with the constituency marked by a dot."""
    path, proj = nation_path(country_code, width, height)
    marker = ""
    if constituency_code and constituency_code in constituencies():
        c = constituencies()[constituency_code]
        x, y = proj(c.lon, c.lat)
        radius = max(5.0, min(11.0, min(width, height) * 0.032))  # scales with the map box (handoff turn 5)
        marker = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{config.ACCENT}" '
                  f'stroke="#ffffff" stroke-width="{3 if radius > 8 else 2}"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" role="img" aria-label="Map of {NATION_NAMES[country_code]}">'
        f'<path d="{path}" fill="{config.MAP_FILL}" stroke="{config.MAP_STROKE}" '
        f'stroke-width="1.25" stroke-linejoin="round"/>{marker}</svg>'
    )

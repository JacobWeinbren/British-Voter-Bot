"""Loading the BES panel and reading answers safely.

The full SPSS file is 2 GB. `load_panel()` reads it once, keeps only wave 31
respondents and every column asked from wave 20 onwards, and caches the result
as parquet in data/processed so later runs take seconds.
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Iterable

import pandas as pd

from . import config

MISSING_CODES = {97, 98, 99, 997, 998, 999, 9997, 9998, 9999}


def _wanted_columns(names: Iterable[str]) -> list[str]:
    wave_suffix = re.compile(r"((?:W\d+)+)$")
    keep = []
    for name in names:
        match = wave_suffix.search(name)
        if not match:
            keep.append(name)  # wave-less variables (id, gender, past votes...)
            continue
        waves = [int(w) for w in re.findall(r"W(\d+)", match.group(1))]
        if max(waves) >= config.EARLIEST_WAVE:
            keep.append(name)
    return keep


def build_cache(sav_path=config.SAV_PATH, cache_path=config.PANEL_CACHE, chunk: int = 350) -> pd.DataFrame:
    """Extract wave-31 respondents from the SPSS file and cache them as parquet."""
    import pyreadstat  # imported lazily: only needed for the one-off extraction

    _, meta = pyreadstat.read_sav(str(sav_path), metadataonly=True)
    columns = _wanted_columns(meta.column_names)
    parts = []
    started = time.time()
    for i in range(0, len(columns), chunk):
        cols = columns[i:i + chunk]
        if "wave31" not in cols:
            cols = ["wave31"] + cols
        frame, _ = pyreadstat.read_sav(str(sav_path), usecols=cols)
        frame = frame[frame["wave31"] == 1]
        if i > 0:
            frame = frame.drop(columns=["wave31"])
        for col in frame.columns:
            if frame[col].dtype == "float64":
                frame[col] = frame[col].astype("float32")  # codes are small integers
        parts.append(frame.reset_index(drop=True))
        print(f"  read {min(i + chunk, len(columns))}/{len(columns)} columns ({time.time() - started:.0f}s)")
    panel = pd.concat(parts, axis=1)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(cache_path, index=False)
    return panel


def load_panel() -> pd.DataFrame:
    """Wave-31 respondents with all wave 20+ columns (from cache, building it if needed)."""
    if config.PANEL_CACHE.exists():
        return pd.read_parquet(config.PANEL_CACHE)
    if not config.SAV_PATH.exists():
        raise SystemExit(f"Neither {config.PANEL_CACHE} nor {config.SAV_PATH} exists. "
                         "Download the BES wave 31 panel (SPSS) into data/raw first.")
    print("Building the wave-31 cache from the SPSS file (a few minutes, once only)...")
    return build_cache()


def value(row, column: str, max_valid: float = 9000) -> float | None:
    """A numeric answer, or None if unanswered, 'don't know', skipped or not asked."""
    if column not in row.index:
        return None
    raw = row[column]
    if raw is None:
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or number < 0 or number >= max_valid or int(number) in MISSING_CODES:
        return None
    return number


def raw_code(row, column: str) -> float | None:
    """The stored code as-is (including 9998-style special codes), or None if empty."""
    if column not in row.index:
        return None
    try:
        number = float(row[column])
    except (TypeError, ValueError):
        return None
    return None if math.isnan(number) else number


def latest(row, columns: Iterable[str], max_valid: float = 9000) -> tuple[float, str] | tuple[None, None]:
    """First valid answer across columns listed most-recent-first, with the column used."""
    for column in columns:
        answer = value(row, column, max_valid)
        if answer is not None:
            return answer, column
    return None, None


def text_value(row, column: str) -> str | None:
    if column not in row.index:
        return None
    raw = row[column]
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    text = str(raw).strip()
    return text or None


_WAVE_RE = re.compile(r"^(.*?)(W\d+(?:_?W\d+)*)$")
_FIELDINGS: dict[int, dict[str, list[str]]] = {}


def _max_wave(column: str) -> int:
    match = _WAVE_RE.match(column)
    return max((int(w) for w in re.findall(r"W(\d+)", match.group(2))), default=0) if match else 0


def fieldings(columns, stem: str, floor: int = 20) -> list[str]:
    """Every column for a question stem, most recent wave first, from the floor wave on.

    The BES keeps a variable name stable when the question is unchanged, so
    `fieldings(row.index, "enviroGrowth")` gives the full run of that question.
    """
    key = id(columns)
    if key not in _FIELDINGS:
        registry: dict[str, list[str]] = {}
        for column in columns:
            match = _WAVE_RE.match(column)
            if match:
                registry.setdefault(match.group(1), []).append(column)
        for cols in registry.values():
            cols.sort(key=_max_wave, reverse=True)
        _FIELDINGS[key] = registry
    return [c for c in _FIELDINGS[key].get(stem, []) if _max_wave(c) >= floor]


def latest_value(row, stem: str, max_valid: float = 9000, floor: int = 20) -> tuple[float | None, str | None]:
    """The most recent answer to a question across all its fieldings, and the column it came from."""
    for column in fieldings(row.index, stem, floor):
        answer = value(row, column, max_valid)
        if answer is not None:
            return answer, column
    return None, None

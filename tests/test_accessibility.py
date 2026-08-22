"""Colour contrast on the card meets WCAG 2.1 AA: 4.5:1 for the 16px footnote on every band, 3:1 for graphics."""

from voterbot import config


def _luminance(colour: str) -> float:
    r, g, b = (int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def all_bands() -> dict[str, tuple[str, str]]:
    bands = dict(config.PARTY_COLOURS)
    bands.update({"don't know": config.DONT_KNOW_COLOURS, "wouldn't vote": config.NO_VOTE_COLOURS, "smaller party": config.OTHER_PARTY_COLOURS})
    return bands


def test_band_text_and_footnote_are_readable_on_every_band_colour():
    for name, (background, ink) in all_bands().items():
        assert contrast(ink, background) >= 4.5, f"{name}: {contrast(ink, background):.2f}:1 for 16px text on {background}"


def test_body_text_colours_pass_on_white():
    for colour in (config.INK, config.BODY, config.SECONDARY, config.ACCENT):
        assert contrast(colour, "#ffffff") >= 4.5


def test_spectrum_band_and_map_marker_pass_non_text_contrast():
    assert contrast(config.SCALE_BAND, "#ffffff") >= 3.0
    assert contrast(config.SCALE_BAND, config.TRACK) >= 3.0
    assert contrast("#ffffff", config.SCALE_BAND) >= 3.0  # the marker's white ring on the band
    assert contrast(config.ACCENT, "#ffffff") >= 3.0      # the marker on the bare track / page
    assert contrast("#ffffff", config.MAP_FILL) >= 3.0    # the marker's white ring on the map

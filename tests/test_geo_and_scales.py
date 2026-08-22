import pandas as pd

from voterbot import geo
from voterbot.profile import Spectrum


def test_nation_paths_render_for_all_three_nations():
    for country in (1, 2, 3):
        path, projection = geo.nation_path(country)
        assert path.startswith("M") and path.endswith("Z")
        assert path.count("M") >= 1


def test_constituency_marker_lands_inside_the_box():
    glasgow_north = next(c for c in geo.constituencies().values() if c.name == "Glasgow North")
    _, projection = geo.nation_path(2)
    x, y = projection(glasgow_north.lon, glasgow_north.lat)
    assert 0 < x < geo.config.MAP_WIDTH and 0 < y < geo.config.MAP_HEIGHT
    svg = geo.nation_svg(2, glasgow_north.code)
    assert "<circle" in svg


def test_spectrum_maps_the_item_average_onto_the_0_to_10_scale():
    scores = pd.Series([1.0, 2.0, 2.0, 3.0, 5.0])
    weights = pd.Series([1.0] * 5)
    spectrum = Spectrum(scores, weights)
    assert Spectrum.score10(1.0) == 0.0 and Spectrum.score10(3.0) == 5.0 and Spectrum.score10(5.0) == 10.0
    assert spectrum.position(3.0) == 50.0  # the scale midpoint is the fixed tick
    assert spectrum.position(1.0) == 3.0 and spectrum.position(5.0) == 97.0
    assert 6.0 <= spectrum.iqr[0] <= 6.5 and 43.5 <= spectrum.iqr[1] <= 44.0  # weighted quartiles 1.25 and 2.75 on the track



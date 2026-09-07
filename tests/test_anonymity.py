"""What a card may say about religion and age: census-level groups and a decade band, never more.

A card already names a real BES respondent's constituency, ethnicity and gender, so the
two attributes that used to be finer than that - the denomination and the exact age - are
coarsened here and checked in both places they can leak: the phrasing code, and the queue
that ships with the repository.
"""

import copy
import json

import pytest

from voterbot import anonymise, codes, config, persona
from voterbot.sample import load_profiles

PERMITTED = {"non-religious", "Anglican", "Catholic", "Christian", "Jewish", "Hindu", "Muslim", "Sikh", "Buddhist"}
BANDS = {band for _, band in persona.AGE_BANDS} | {persona.OLDEST_BAND}

CARD = {
    "headline": {"template": "I'm a {ethnicity} {religion} {gender} from {place}, aged {age}.",
                 "bold": {"ethnicity": "White Scottish", "religion": "Episcopalian", "gender": "man",
                          "place": "Lothian East", "age": "43"}},
    "life": {"template": "I rent privately.", "bold": {}},
    "media": None,
    "top_issue": "the economy",
    "nation": "Scotland",
    "constituency": "Lothian East",
    "constituency_code": "S14000104",
    "possessive": "his",
    "bubbles": [{"template": "I feel more Scottish than British.", "bold": {}}],
    "econ_pct": None, "cultural_pct": None,
    "band_text": "In 2024 I voted Labour. Today I still would",
}


def test_the_religion_map_holds_only_groups_large_enough_to_hide_in():
    """The two largest churches keep their name; every smaller denomination is folded away."""
    assert set(codes.RELIGION.values()) - {None} == PERMITTED
    assert set(anonymise.RETIRED_DENOMINATIONS) & PERMITTED == set()


@pytest.mark.parametrize("age,band", [
    (18, "late teens"), (19, "late teens"), (20, "twenties"), (29, "twenties"),
    (30, "thirties"), (39, "thirties"), (40, "forties"), (59, "fifties"), (60, "sixties"),
    (79, "seventies"), (80, "eighties or older"), (96, "eighties or older"),
])
def test_age_bands_run_by_decade_and_top_code_the_eighties(age, band):
    assert persona.age_band(age) == band


def test_migrating_a_card_coarsens_the_headline_and_the_post_text():
    card = copy.deepcopy(CARD)
    assert anonymise.migrate_card(card) is True
    assert anonymise.spoken_headline(card) == "I'm a White Scottish Anglican man from Lothian East, in my forties."
    assert card["post_text"].startswith("I'm a White Scottish Anglican man from Lothian East, in my forties.")


def test_migrating_a_card_twice_changes_nothing_the_second_time():
    card = copy.deepcopy(CARD)
    anonymise.migrate_card(card)
    once = json.dumps(card, sort_keys=True)
    assert anonymise.migrate_card(card) is False
    assert json.dumps(card, sort_keys=True) == once


def test_an_unrecognised_religion_label_stops_the_migration():
    with pytest.raises(ValueError):
        anonymise.coarse_religion("Zoroastrian")


def test_a_retired_age_band_stops_the_migration_rather_than_being_kept():
    """A band that has since been split cannot be rewritten from itself - the exact age is gone."""
    card = copy.deepcopy(CARD)
    card["headline"]["template"] = card["headline"]["template"].replace("aged {age}", "in my {age}")
    card["headline"]["bold"]["age"] = "late teens or twenties"
    with pytest.raises(ValueError, match="retired age band"):
        anonymise.migrate_card(card)


@pytest.mark.skipif(not config.PROFILES_PATH.exists(), reason="no queue built")
def test_the_queued_cards_carry_no_exact_age_or_denomination():
    for card in load_profiles():
        bold = card["headline"]["bold"]
        assert bold["age"] in BANDS, bold["age"]
        assert bold.get("religion", "non-religious") in PERMITTED, bold.get("religion")
        assert "aged" not in card["headline"]["template"]

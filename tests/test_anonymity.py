"""What a card may say about religion and age: census-level groups and a decade band, never more.

A card already names a real BES respondent's constituency, ethnicity and gender, so the
two attributes that used to be finer than that - the denomination and the exact age - are
coarsened here and checked in both places they can leak: the phrasing code, and the queue
that ships with the repository.
"""

import copy
import json
import re

import pytest

from voterbot import anonymise, codes, config, geo, persona
from voterbot.sample import load_profiles

RARE_SEAT = "E14001424"  # Penrith and Solway: the census counts five Sikhs
RARE_SCOTTISH_SEAT = "S14000027"  # Na h-Eileanan an Iar: one Sikh, two Jewish residents
COMMON_SEAT = "E14000585"  # Bradford West: tens of thousands of Muslims

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


def test_a_faith_with_almost_nobody_of_it_in_the_seat_counts_as_rare():
    assert persona.faith_is_rare("Sikh", RARE_SEAT) is True
    assert persona.faith_is_rare("Muslim", RARE_SEAT) is False  # 276 there, well above the threshold
    assert persona.faith_is_rare("Christian", RARE_SEAT) is False  # never tested: far too large to narrow anyone down


def test_a_faith_stands_where_there_is_nothing_to_measure_it_with():
    assert persona.faith_is_rare("Sikh", None) is False  # no constituency recorded
    assert persona.faith_is_rare("Sikh", "N05000001") is False  # a seat the census file does not cover


def test_scotland_is_measured_by_its_own_census_like_anywhere_else():
    assert persona.faith_is_rare("Sikh", RARE_SCOTTISH_SEAT) is True
    assert persona.faith_is_rare("Muslim", "S14000030") is False  # Glasgow South West, thousands of Muslims


def test_every_british_seat_has_a_count_to_test_against():
    """A seat with no entry silently keeps its faith, so the file has to cover all of Great Britain."""
    counts = geo.religion_counts()
    missing = [c for c in geo.constituencies() if not c.startswith("N") and c not in counts]
    assert not missing, missing


def test_a_rare_faith_is_dropped_from_the_headline_and_the_article_follows():
    card = copy.deepcopy(CARD)
    card["constituency_code"] = RARE_SEAT
    card["headline"]["bold"].update(ethnicity="Asian", religion="Sikh")
    anonymise.migrate_card(card)
    assert anonymise.spoken_headline(card) == "I'm an Asian man from Lothian East, in my forties."


def test_dropping_the_only_vowel_word_puts_the_article_right():
    """With no ethnicity the faith led the sentence, so "an Asian" must not become "an man"."""
    headline = {"template": "I'm an {religion} {gender} from {place}, in my {age}.",
                "bold": {"religion": "Asian", "gender": "man", "place": "X", "age": "forties"}}
    anonymise.drop_religion(headline)
    assert headline["template"].format(**headline["bold"]) == "I'm a man from X, in my forties."


def test_a_rare_faith_takes_the_place_of_worship_with_it():
    card = copy.deepcopy(CARD)
    card["constituency_code"] = RARE_SEAT
    card["headline"]["bold"]["religion"] = "Sikh"
    card["life"]["template"] = "I rent privately. I get to the gurdwara most months. I work full-time."
    anonymise.migrate_card(card)
    assert "gurdwara" not in card["life"]["template"]
    assert "I rent privately." in card["life"]["template"] and "I work full-time." in card["life"]["template"]


def test_a_common_faith_keeps_its_name_and_its_place_of_worship():
    card = copy.deepcopy(CARD)
    card["constituency_code"] = COMMON_SEAT
    card["headline"]["bold"]["religion"] = "Muslim"
    card["life"]["template"] = "I rent privately. I'm at the mosque every week."
    anonymise.migrate_card(card)
    assert card["headline"]["bold"]["religion"] == "Muslim"
    assert "mosque" in card["life"]["template"]


def test_a_plural_qualification_no_longer_takes_a_singular_verb():
    card = copy.deepcopy(CARD)
    card["life"]["template"] = "My highest qualification is A-levels. GCSEs are my highest qualification."
    anonymise.migrate_card(card)
    assert card["life"]["template"] == "My highest qualifications are A-levels. GCSEs are my highest qualifications."
    for wording in persona.VARIANTS["I've got A-levels"] + persona.VARIANTS["I left school with GCSEs"]:
        assert not re.search(r"\bqualification\b", wording), wording  # plural name, plural noun


def test_a_headline_files_each_word_under_its_own_name():
    """With no ethnicity recorded the faith must still be the {religion} slot, or nothing looking
    for a religion - these checks included - would find it."""
    head = {"template": "I'm a {ethnicity} {religion} {gender} from {place}, in my {age}.",
            "bold": {"ethnicity": "White British", "religion": "Catholic"}}
    assert "religion" in head["bold"]  # the shape every consumer relies on


@pytest.mark.skipif(not config.PROFILES_PATH.exists(), reason="no queue built")
def test_no_queued_card_names_a_faith_that_is_rare_where_they_live():
    for card in load_profiles():
        for label in card["headline"]["bold"].values():  # whichever slot it landed in
            assert not persona.faith_is_rare(label, card.get("constituency_code")), (label, card["constituency"])


@pytest.mark.skipif(not config.PROFILES_PATH.exists(), reason="no queue built")
def test_the_queued_cards_carry_no_exact_age_or_denomination():
    retired = set(anonymise.RETIRED_DENOMINATIONS)
    for card in load_profiles():
        bold = card["headline"]["bold"]
        assert bold["age"] in BANDS, bold["age"]
        assert bold.get("religion", "non-religious") in PERMITTED, bold.get("religion")
        assert not retired & set(bold.values()), bold  # a denomination in any slot, however it got there
        assert "aged" not in card["headline"]["template"]

"""Tests for const consistency."""

from custom_components.polleninformation.const import (
    COUNTRY_DISPLAY_NAMES,
    LANGUAGE_DISPLAY_NAMES,
    SUPPORTED_COUNTRIES,
    SUPPORTED_LANGUAGES,
)
from custom_components.polleninformation.const_levels import LEVELS


def test_all_countries_have_display_names():
    for code in SUPPORTED_COUNTRIES:
        assert code in COUNTRY_DISPLAY_NAMES, f"Missing display name for {code}"


def test_all_languages_have_display_names():
    for code in SUPPORTED_LANGUAGES:
        assert code in LANGUAGE_DISPLAY_NAMES, f"Missing display name for {code}"


def test_all_languages_have_levels():
    for code in SUPPORTED_LANGUAGES:
        assert code in LEVELS, f"Missing levels for language {code}"


def test_levels_have_five_entries():
    for code, level_list in LEVELS.items():
        assert len(level_list) == 5, (
            f"Language {code} has {len(level_list)} levels, expected 5"
        )

"""Tests for const consistency."""

import importlib.util
import json
from pathlib import Path

from custom_components.polleninformation.config_flow import COUNTRY_CENTER
from custom_components.polleninformation.const import (
    COUNTRY_DISPLAY_NAMES,
    LANGUAGE_DISPLAY_NAMES,
    SUPPORTED_COUNTRIES,
    SUPPORTED_LANGUAGES,
)
from custom_components.polleninformation.const_levels import LEVELS

REPO_ROOT = Path(__file__).resolve().parent.parent
API_STATUS_SCRIPT = REPO_ROOT / "scripts" / "check_api_status.py"
HACS_MANIFEST = REPO_ROOT / "hacs.json"

# The countries the upstream service publishes, taken from the map on
# polleninformation.eu, which links one national site per country.
#
# Each was confirmed against the API rather than trusted from the map: a code
# the API does not recognize -- "XX", "US", the empty string -- answers 200
# with no contamination and an empty allergyrisk, so a code that answers with
# either is one the API accepts. Every code below answered with both.
#
# The country selects which reporting panel the answer is drawn from, not the
# values: asking for a Lisbon coordinate under AT and under PT returns the
# same six allergens and the same risk numbers, while Stockholm under SE
# returns nine and under PT returns five. Picking the country a location is
# actually in is what earns the national panel where one exists.
UPSTREAM_COUNTRIES = {
    "AT",
    "CH",
    "DE",
    "ES",
    "FI",
    "FR",
    "GB",
    "HU",
    "IT",
    "LT",
    "LV",
    "PL",
    "PT",
    "SE",
    "SK",
    "TR",
    "UA",
}


def _load_api_status():
    """Load scripts/check_api_status.py from its path.

    scripts/ is not a package, so the status script cannot be imported by
    name. Loading it must stay free of side effects; it reads its API key
    inside main(), not at import time.
    """
    spec = importlib.util.spec_from_file_location("check_api_status", API_STATUS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_supported_countries_match_upstream():
    """Every country the upstream service serves is one this integration offers.

    The list drifted once already: the languages for Finland, Portugal,
    Slovakia and Hungary were added while the countries were not, so the
    integration asked for translations it had no way to request data in.
    """
    assert set(SUPPORTED_COUNTRIES) == UPSTREAM_COUNTRIES


def test_all_countries_have_display_names():
    for code in SUPPORTED_COUNTRIES:
        assert code in COUNTRY_DISPLAY_NAMES, f"Missing display name for {code}"


def test_all_countries_have_map_centers():
    """Choosing a country moves the config flow's map to it.

    A country offered in the dropdown with no centre leaves the map wherever
    it last was, which reads to the user as the choice having done nothing.
    """
    for code in SUPPORTED_COUNTRIES:
        assert code in COUNTRY_CENTER, f"Missing map centre for {code}"


def test_api_status_script_covers_all_countries():
    """The public status page reports on every country the integration offers.

    The page is generated from the script's own table, so a country missing
    from it is not reported as broken -- it is not reported at all, and a
    country whose data has gone quiet looks fine by being absent.
    """
    module = _load_api_status()
    assert set(module.COUNTRIES) == set(SUPPORTED_COUNTRIES)


def test_hacs_country_filter_covers_all_countries():
    """HACS shows the integration to users in every country it serves.

    hacs.json's country list is a discovery filter: a user whose Home
    Assistant is set to a country missing from it is not shown the
    integration at all. A country added to the config flow but not here is
    therefore offered only to the users who already found it.

    A subset rather than an equality: the list may name a country the config
    flow has no entry of its own for, as it does Vatican City, whose users
    are served by the Italian panel.
    """
    hacs = json.loads(HACS_MANIFEST.read_text(encoding="utf-8"))
    missing = set(SUPPORTED_COUNTRIES) - set(hacs["country"])
    assert not missing, f"Not discoverable in HACS: {sorted(missing)}"


def test_all_languages_have_display_names():
    for code in SUPPORTED_LANGUAGES:
        assert code in LANGUAGE_DISPLAY_NAMES, f"Missing display name for {code}"


def test_all_languages_have_levels():
    for code in SUPPORTED_LANGUAGES:
        assert code in LEVELS, f"Missing levels for language {code}"


def test_levels_have_five_entries():
    for code, level_list in LEVELS.items():
        assert len(level_list) == 5, f"Language {code} has {len(level_list)} levels, expected 5"

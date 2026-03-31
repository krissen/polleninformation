"""Shared fixtures for polleninformation tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.polleninformation.const import DOMAIN

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for polleninformation."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hamburg",
        data={
            "country": "DE",
            "latitude": 53.5289,
            "longitude": 10.0415,
            "lang": "en",
            "apikey": "test-api-key-12345",
            "location": "Hamburg",
            "location_title": "Hamburg",
            "location_slug": "hamburg",
        },
        options={},
    )


@pytest.fixture
def mock_api_response() -> dict:
    """Return a realistic API response fixture."""
    return json.loads((FIXTURES_DIR / "api_response_de.json").read_text())


@pytest.fixture
def mock_api_response_empty() -> dict:
    """Return an empty API response fixture."""
    return json.loads((FIXTURES_DIR / "api_response_empty.json").read_text())


@pytest.fixture
def mock_language_map():
    """Patch language map loading with minimal test data."""
    minimal_map = {
        "en": {
            "lang_code": "en",
            "lang": "English",
            "poll_titles": [
                {"name": "Alder", "latin": "Alnus"},
                {"name": "Birch", "latin": "Betula"},
                {"name": "Grasses", "latin": "Poaceae"},
            ],
        },
        "sv": {
            "lang_code": "sv",
            "lang": "Swedish",
            "poll_titles": [
                {"name": "Al", "latin": "Alnus"},
                {"name": "Björk", "latin": "Betula"},
                {"name": "Gräs", "latin": "Poaceae"},
            ],
        },
    }
    with patch(
        "custom_components.polleninformation.utils._sync_load_language_map",
        return_value=minimal_map,
    ):
        yield minimal_map

"""Tests for the polleninformation.at API client."""

import asyncio
import json

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.polleninformation.api import (
    API_URL,
    PollenApiAuthError,
    PollenApiConnectionError,
    PollenApiError,
    async_get_pollenat_data,
)

API_URL_PREFIX = API_URL.split("?")[0]

CALL_KWARGS = {
    "latitude": 53.5289,
    "longitude": 10.0415,
    "country": "DE",
    "lang": "en",
    "apikey": "test-key",
}


def mock_json_response(aioclient_mock, payload):
    """Mock a JSON API response with an explicit JSON content type."""
    aioclient_mock.get(
        API_URL_PREFIX,
        text=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )


async def test_successful_response(hass: HomeAssistant, aioclient_mock):
    payload = {"contamination": [{"poll_title": "Birch", "contamination_1": 1}]}
    mock_json_response(aioclient_mock, payload)
    result = await async_get_pollenat_data(hass, **CALL_KWARGS)
    assert result == payload


async def test_401_raises_auth_error(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL_PREFIX, status=401)
    with pytest.raises(PollenApiAuthError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_403_raises_auth_error(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL_PREFIX, status=403)
    with pytest.raises(PollenApiAuthError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_500_raises_api_error(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL_PREFIX, status=500)
    with pytest.raises(PollenApiError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_timeout_raises_connection_error(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.get(API_URL_PREFIX, exc=asyncio.TimeoutError())
    with pytest.raises(PollenApiConnectionError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_client_error_raises_connection_error(
    hass: HomeAssistant, aioclient_mock
):
    aioclient_mock.get(API_URL_PREFIX, exc=aiohttp.ClientError())
    with pytest.raises(PollenApiConnectionError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_json_error_apikey_raises_auth_error(hass: HomeAssistant, aioclient_mock):
    mock_json_response(aioclient_mock, {"error": "invalid api key"})
    with pytest.raises(PollenApiAuthError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)


async def test_json_error_other_raises_api_error(hass: HomeAssistant, aioclient_mock):
    mock_json_response(aioclient_mock, {"error": "rate limit exceeded"})
    with pytest.raises(PollenApiError):
        await async_get_pollenat_data(hass, **CALL_KWARGS)

"""custom_components/polleninformation/api.py"""

import logging

import aiohttp
import async_timeout

from .const import (DEFAULT_ID, DEFAULT_L, DEFAULT_LANG, DEFAULT_LANG_ID,
                    DEFAULT_PASYFO, DEFAULT_PERSONAL_CONTAMINATION,
                    DEFAULT_SENSITIVITY, DEFAULT_SESSIONID, DEFAULT_SHOW_POLLS,
                    DEFAULT_TX_ACTION, DEFAULT_TYPE, POLLENAT_API_URL)

_LOGGER = logging.getLogger(__name__)

async def async_get_pollenat_data(
    hass,
    latitude,
    longitude,
    country,
    country_id,
    lang=DEFAULT_LANG,
    lang_id=DEFAULT_LANG_ID,
    show_polls=DEFAULT_SHOW_POLLS,
    sessionid=DEFAULT_SESSIONID,
    personal_contamination=DEFAULT_PERSONAL_CONTAMINATION,
    sensitivity=DEFAULT_SENSITIVITY,
    tx_action=DEFAULT_TX_ACTION,
    id_=DEFAULT_ID,
    type_=DEFAULT_TYPE,
    L=DEFAULT_L,
    pasyfo=DEFAULT_PASYFO,
    C=None,
):
    """
    Hämtar polleninformation-data från polleninformation.at med rätt nya parametrar.

    :param hass: Home Assistant-instans (för ev. async session).
    :param latitude: Latitud (float)
    :param longitude: Longitud (float)
    :param country: Landkod, t.ex. "SE"
    :param country_id: Numeriskt country-id (t.ex. 26 för SE)
    :param lang: Språkkod, t.ex. "sv"
    :param lang_id: Språk-id, t.ex. "7" för svenska
    :param show_polls: Kommaseparerad lista över pollen-id
    :param sessionid: Sessionid, vanligtvis tom
    :param personal_contamination: "true" eller "false"
    :param sensitivity: "0"
    :param tx_action: t.ex. "getFullContaminationData"
    :param id_: API-param id
    :param type_: API-param type
    :param L: API-param L
    :param pasyfo: API-param pasyfo
    :param C: landets numeriska id (om ej angivet används country_id)
    :return: dict (API-responsens JSON) eller None vid fel
    """

    params = {
        "id": id_,
        "type": type_,
        "lang_code": lang,
        "lang_id": lang_id,
        "L": L,
        "tx_scapp_appapi[action]": tx_action,
        "locationType": "gps",
        "show_polls": show_polls,
        "C": str(C if C is not None else country_id),
        "personal_contamination": personal_contamination,
        "sensitivity": sensitivity,
        "country": country,
        "sessionid": sessionid,
        "pasyfo": pasyfo,
        "value[latitude]": str(latitude),
        "value[longitude]": str(longitude),
    }

    url = POLLENAT_API_URL.format(
        id=params["id"],
        type=params["type"],
        lang=params["lang_code"],
        lang_id=params["lang_id"],
        L=params["L"],
        tx_action=params["tx_scapp_appapi[action]"],
        show_polls=params["show_polls"],
        country_id=params["C"],
        personal_contamination=params["personal_contamination"],
        sensitivity=params["sensitivity"],
        country=params["country"],
        sessionid=params["sessionid"],
        pasyfo=params["pasyfo"],
        lat=params["value[latitude]"],
        lon=params["value[longitude]"],
    )

    _LOGGER.debug(f"Kallar polleninformation.at: {url}")

    try:
        async with async_timeout.timeout(15):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
                    }
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
    except Exception as e:
        _LOGGER.error(f"Fel vid anrop till polleninformation.at: {e}")
        return None

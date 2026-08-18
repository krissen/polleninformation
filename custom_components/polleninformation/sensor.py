"""Sensors for polleninformation.at integration (new API version).

Supports:
- Allergen sensors with localized and English names, latin name, object_id based on English, icon mapping, levels per language.
- One sensor for allergy risk (daily), one for allergy risk (hourly), with scaled values and forecast attributes.
- All attributes and device info as previously.
- DRY/KISS principles.
- All comments and docstrings in English.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify as ha_slugify

from .const import (
    CONF_COUNTRY,
    CONF_LANG,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAMES_IN_INTEGRATION_LANG,
    DEFAULT_LANG,
    DEFAULT_NAMES_IN_INTEGRATION_LANG,
    DOMAIN,
)
from .const_levels import ALLERGEN_DISPLAY_OVERRIDES, LEVELS, RISK_SENSOR_NAMES
from .utils import (
    allergen_names_from_item,
    async_get_language_block,
    get_allergen_info_by_latin,
    normalize,
    slugify,
    usable_contamination,
    usable_risk_block,
)

_LOGGER = logging.getLogger(__name__)

# English allergen name per latin name, as the API returns it for lang=en.
# This is the source of the allergen slug, and therefore of the unique_id and
# the entity_id. Deriving the slug from the localized response instead would
# give a different unique_id per interface language. language_map.json only
# covers the twelve allergens that had a localized name when it was
# generated, so the API is the authority here.
LATIN_TO_ENGLISH_NAME = {
    "Ailanthus altissima": "tree of heaven",
    "Alnus": "alder",
    "Alternaria": "fungal spores",
    "Ambrosia": "ragweed",
    "Artemisia": "mugwort",
    "Betula": "birch",
    "Castanea": "sweet chestnut",
    "Corylus": "hazel",
    "Cupressaceae": "cypress family",
    "Fagus": "beech",
    "Fraxinus": "ash",
    "Olea": "olive",
    "Plantago": "plantain",
    "Platanus": "plane tree",
    "Poaceae": "grasses",
    "Quercus": "oak",
    "Rumex": "dock/sorrel",
    "Salix": "willow",
    "Secale": "rye",
    "Tilia": "linden",
    "Ulmus": "elm",
    "Urticaceae": "nettle family",
}

# Spellings the API sends in the latin field that are not latin names, and the
# name each one stands for. The Slovak response spells ragweed "ambrózia",
# which is the Slovak word rather than a candidate scientific name, so nothing
# above matches it and the allergen would be unknown.
#
# This is an allow-list on purpose: every entry is a fact about the API's data,
# added after seeing it. A latin name the API sends that is simply not in the
# map above is left alone, because it identifies its allergen whatever we can
# resolve it to. Keys are lowercase; lookups normalize.
#
# A key here may not be a latin name the map above already knows, genus keys
# included: the indexes let the real name win and resolve_latin_alias lets the
# alias win, so such a key would make the two disagree about the same string
# with nothing to warn about it. The value must be a key of the map above.
# Both properties are pinned in tests/test_sensor.py.
LATIN_NAME_ALIASES = {
    "ambrózia": "Ambrosia",
}

# Icons group the allergens by pollen source, which is what makes a list of
# them scannable: the name next to the icon already says which species it is.
# Material Design Icons has no species-specific plant icons, so a shared icon
# is preferred over one that would depict the wrong plant.
ALLERGEN_ICON_MAP = {
    # Catkin trees, the early-spring group
    "alder": "mdi:tree-outline",
    "birch": "mdi:tree-outline",
    "willow": "mdi:tree-outline",
    "hazel": "mdi:hops",  # a hazel catkin has the shape of a hop cone
    # Broadleaf trees
    "ash": "mdi:tree",
    "beech": "mdi:tree",
    "elm": "mdi:tree",
    "linden": "mdi:tree",
    "oak": "mdi:tree",
    "sweet_chestnut": "mdi:tree",
    "tree_of_heaven": "mdi:tree",
    "plane_tree": "mdi:leaf-maple",  # the one species whose leaf is maple-like
    # Evergreens
    "cypress_family": "mdi:pine-tree",
    "olive": "mdi:leaf-circle",
    # Grasses and cereals
    "grasses": "mdi:grass",
    "rye": "mdi:barley",
    # Weeds and herbs
    "mugwort": "mdi:flower",
    "ragweed": "mdi:flower-poppy",
    "dock_sorrel": "mdi:sprout",
    "nettle_family": "mdi:leaf",
    "plantain": "mdi:leaf",
    # Not a plant at all
    "fungal_spores": "mdi:mushroom",
    "default": "mdi:flower-pollen",
}

RISK_SLUGS = ("allergy_risk", "allergy_risk_hourly")

KNOWN_ALLERGEN_SLUGS = (
    set(ALLERGEN_ICON_MAP.keys()) - {"default"}
    | {slugify(name) for name in LATIN_TO_ENGLISH_NAME.values()}
    | set(RISK_SLUGS)
)


def capitalize_first(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def extract_allergen_slug_from_unique_id(unique_id: str) -> str | None:
    """Extract allergen slug from unique_id by matching known suffixes.

    unique_id format: polleninformation_<location_slug>_<allergen_slug>
    location_slug can contain underscores, so we match against known allergen slugs.
    """
    if not unique_id or not unique_id.startswith("polleninformation_"):
        return None

    for slug in sorted(KNOWN_ALLERGEN_SLUGS, key=len, reverse=True):
        suffix = f"_{slug}"
        if unique_id.endswith(suffix):
            return slug
    return None


@lru_cache(maxsize=1)
def _latin_name_index() -> dict[str, str]:
    """Case-insensitive latin lookup, extended with genus-only keys.

    The API spells a latin name with the genus alone for most allergens but
    with genus and species for others, and the case is not consistent between
    languages.
    """
    index = {latin.lower(): name for latin, name in LATIN_TO_ENGLISH_NAME.items()}
    for latin, name in LATIN_TO_ENGLISH_NAME.items():
        index.setdefault(latin.split()[0].lower(), name)
    for alias, latin in LATIN_NAME_ALIASES.items():
        index.setdefault(alias, LATIN_TO_ENGLISH_NAME[latin])
    return index


def resolve_latin_alias(latin: str | None) -> str | None:
    """Return the latin name a declared spelling stands for.

    Only a spelling declared in LATIN_NAME_ALIASES is rewritten, so a latin
    name the API sent that no map knows is returned unchanged, species and
    all.
    """
    if not latin:
        return latin
    return LATIN_NAME_ALIASES.get(latin.strip().lower(), latin)


@lru_cache(maxsize=1)
def _canonical_latin_index() -> dict[str, str]:
    """The key of LATIN_TO_ENGLISH_NAME per spelling that resolves to it."""
    index = {latin.lower(): latin for latin in LATIN_TO_ENGLISH_NAME}
    for latin in LATIN_TO_ENGLISH_NAME:
        index.setdefault(latin.split()[0].lower(), latin)
    for alias, latin in LATIN_NAME_ALIASES.items():
        index.setdefault(alias, latin)
    return index


def canonical_latin(latin: str | None) -> str | None:
    """Return the key of LATIN_TO_ENGLISH_NAME a latin name resolves to.

    None when no map knows it. This is the spelling anything keyed by latin
    name has to store, because the lookups against a language block match
    exactly: an entry recorded as "poaceae" or "Ambrosia artemisiifolia" is
    never found again by a consumer holding "Poaceae" or "Ambrosia".

    A latin name that carries a species falls back to its genus, exactly as
    english_name_for_latin does, so the two agree on what is recognized.
    """
    if not latin:
        return None
    index = _canonical_latin_index()
    key = latin.strip().lower()
    if canonical := index.get(key):
        return canonical
    return index.get(key.split()[0]) if key.split() else None


def canonical_latin_for_display_name(name: str | None) -> str | None:
    """Return the map key for a display name that IS a latin name, or None.

    The display-name half of canonical_latin, and it does NOT fall back to
    the genus, exactly as english_name_for_display_name does not: a display
    name that merely begins with a genus is prose, and "Ambrosia hojas" is
    not ragweed. The genus fallback belongs to the latin field, where a name
    carrying a species really does resolve to its genus.

    The pair mirrors english_name_for_latin and english_name_for_display_name
    on purpose. Anything keyed by latin name has to agree with the sensors
    about which allergen an entry is, and the two cannot agree if one of them
    guesses from a first word where the other refuses to.
    """
    return _canonical_latin_index().get(name.strip().lower()) if name else None


def english_name_for_latin(latin: str | None) -> str | None:
    """Return the English allergen name for a latin name, or None if unknown.

    A latin name that carries a species falls back to its genus, so both
    "Ambrosia" and "Ambrosia artemisiifolia" resolve.
    """
    if not latin:
        return None
    index = _latin_name_index()
    key = latin.strip().lower()
    if name := index.get(key):
        return name
    return index.get(key.split()[0]) if key.split() else None


def english_name_for_display_name(name: str | None) -> str | None:
    """Return the English allergen name for a display name that IS a latin name.

    Unlike english_name_for_latin this does not fall back to the first token:
    a display name that merely begins with a genus is prose, not an identity.
    A latin name the map knows is matched whole, genus-plus-species keys
    included.
    """
    return _latin_name_index().get(name.strip().lower()) if name else None


@lru_cache(maxsize=1)
def _slug_index() -> dict[str, tuple[str, str]]:
    """Canonical English name and latin name per allergen slug."""
    return {
        slugify(name): (name, latin) for latin, name in LATIN_TO_ENGLISH_NAME.items()
    }


def allergen_slug_for_item(item: dict) -> str | None:
    """Return the canonical allergen slug for a contamination entry, or None.

    The latin name in poll_title is the only part of the entry that does not
    vary with the configured language, so it is what identifies an allergen
    for a sensor that only knows its own slug.

    The title is parsed by the shared helper rather than here. This used to
    split the brackets itself and read poll_title without a guard, which was
    safe only because both callers happen to filter the block first: safety by
    call order, which lasts exactly until someone calls it from somewhere
    else. An entry the helper cannot read identifies nothing, which is the
    same answer this gave for a title it could not place.
    """
    parsed = allergen_names_from_item(item)
    if parsed is None:
        return None
    name, latin = parsed
    if latin:
        name_en = english_name_for_latin(latin)
    else:
        # No latin at all: the API sometimes sends the latin name as the
        # display name instead (e.g. "Artemisia"), so the name itself is the
        # last chance to identify the entry. Only tried when no latin was
        # sent, so an entry that carries one is identified by that alone.
        name_en = english_name_for_display_name(name)
    return slugify(name_en) if name_en else None


def entity_id_available(hass, ent_reg, entity_id: str) -> bool:
    """Return True when the registry would accept this entity_id.

    Mirrors the registry's own rule: async_update_entity raises when the
    target is registered OR occupied in the state machine. A YAML or template
    entity holds an entity_id without a registry entry, so checking the
    registry alone lets that call raise and abort setup.
    """
    return not ent_reg.async_is_registered(entity_id) and hass.states.async_available(
        entity_id
    )


ALLERGEN_IDENTITY_OPTION = "latin"


def allergen_identity_key(latin) -> str | None:
    """Return the key two latin names must share to be the same allergen.

    The map's own spelling when it knows the name, so that "Ambrosia",
    "Ambrosia artemisiifolia" and every alias of them answer alike; the name
    itself, folded, when no map knows it. That second half is the point: the
    rows this exists to protect are exactly the ones no map can place, so a
    key that only spoke for known allergens would say "unknown" for the whole
    population it was written for.
    """
    if not isinstance(latin, str) or not latin.strip():
        return None
    return canonical_latin(latin) or latin.strip().lower()


def stored_allergen_latin(ent_reg, entity_id) -> str | None:
    """Return the latin name a registry row records for itself, or None.

    None means the row does not say, which is every row on every installation
    that upgraded into this. Absent has to mean UNKNOWN rather than mismatch:
    a row that says nothing about itself gets exactly the behaviour it had
    before there was anywhere to say it.
    """
    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return None
    stored = (entry.options.get(DOMAIN) or {}).get(ALLERGEN_IDENTITY_OPTION)
    return stored if isinstance(stored, str) and stored.strip() else None


def store_allergen_identity(ent_reg, entity_id, latin) -> None:
    """Record which allergen a registry row is, where a restart keeps it.

    The registry stores a slug, a display name and an icon, and no allergen
    identity, so for a slug no map can place there has been nothing to check a
    rename against and a legacy candidate had to be trusted on its name alone.
    Per-entity options under this integration's own domain are the sanctioned
    place to keep something of ours: they are written to the registry store
    and read back at load, unlike state attributes, which are not persisted at
    all.

    Only this integration's key is written, and the other keys under it are
    carried over, so nothing else on the row is touched. A row already
    recorded as this allergen is left alone rather than rewritten, and the
    comparison is by identity rather than by spelling so that the two paths
    which can name the same allergen -- the response, which may send a
    species, and a recreated sensor, which can only name the genus -- do not
    take turns overwriting each other.
    """
    key = allergen_identity_key(latin)
    if not key or not entity_id:
        return
    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return
    options = dict(entry.options.get(DOMAIN) or {})
    if allergen_identity_key(options.get(ALLERGEN_IDENTITY_OPTION)) == key:
        return
    options[ALLERGEN_IDENTITY_OPTION] = latin.strip()
    ent_reg.async_update_entity_options(entity_id, DOMAIN, options)


def migrate_localized_allergen_ids(hass, location_slug, renames) -> None:
    """Rename allergen ids that were derived from a localized allergen name.

    The renames are (legacy_slug, canonical_slug) pairs derived from the
    current API response, so only ids this integration can itself have
    produced are ever considered. The unique_id is always migrated; the
    entity_id only when it is exactly what this integration would have
    generated, so an entity_id the user chose is kept even when it happens to
    end in the old slug. Either step is skipped with a warning when its
    target is taken.
    """
    if not renames:
        return

    ent_reg = er.async_get(hass)
    for legacy_slug, canonical_slug in renames:
        legacy_unique_id = f"polleninformation_{location_slug}_{legacy_slug}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, legacy_unique_id)
        if entity_id is None:
            continue

        canonical_unique_id = f"polleninformation_{location_slug}_{canonical_slug}"
        if ent_reg.async_get_entity_id("sensor", DOMAIN, canonical_unique_id):
            _LOGGER.warning(
                "Not migrating %s: an entity with unique_id %s already exists",
                entity_id,
                canonical_unique_id,
            )
            continue

        updates: dict[str, str] = {"new_unique_id": canonical_unique_id}
        prefix = f"polleninformation_{location_slug}_"
        if entity_id == f"sensor.{prefix}{legacy_slug}":
            new_entity_id = f"sensor.{prefix}{canonical_slug}"
            if entity_id_available(hass, ent_reg, new_entity_id):
                updates["new_entity_id"] = new_entity_id
            else:
                _LOGGER.warning(
                    "Keeping entity_id %s: %s is already taken",
                    entity_id,
                    new_entity_id,
                )
        else:
            _LOGGER.debug(
                "Keeping entity_id %s: it is not the generated one for %s",
                entity_id,
                legacy_slug,
            )

        _LOGGER.info(
            "Migrating localized allergen sensor %s (%s) to %s",
            entity_id,
            legacy_slug,
            canonical_slug,
        )
        ent_reg.async_update_entity(entity_id, **updates)


@lru_cache(maxsize=1)
def localized_risk_object_id_suffixes() -> dict[str, frozenset[str]]:
    """Return the localized object_id suffixes the risk sensors can have produced.

    Home Assistant derives an entity_id from the entity name, so a translated
    risk sensor name yields a translated object_id. Every translated name --
    from the translation files as well as from RISK_SENSOR_NAMES -- is a
    suffix a released version may have written to the registry. The canonical
    slug itself is excluded so it is never treated as a rename candidate.
    """
    suffixes: dict[str, set[str]] = {slug: set() for slug in RISK_SLUGS}

    for names in RISK_SENSOR_NAMES.values():
        for slug in RISK_SLUGS:
            if name := names.get(slug):
                suffixes[slug].add(ha_slugify(name))

    for path in sorted((Path(__file__).parent / "translations").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _LOGGER.debug("Could not read translation file %s", path, exc_info=True)
            continue
        sensors = data.get("entity", {}).get("sensor", {})
        for slug in RISK_SLUGS:
            if name := sensors.get(slug, {}).get("name"):
                suffixes[slug].add(ha_slugify(name))

    for slug in RISK_SLUGS:
        suffixes[slug].discard(slug)
    return {slug: frozenset(values) for slug, values in suffixes.items()}


async def async_migrate_localized_risk_entity_ids(hass, entry, location_slug) -> None:
    """Rename risk sensor entity_ids that were created from a translated name.

    Only an entity_id that is exactly what this integration would itself have
    generated from a translated name is touched, so an entity_id the user
    chose is left alone even when it happens to end in a translated name.
    """
    ent_reg = er.async_get(hass)
    candidates = []
    for reg_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if reg_entry.domain != "sensor":
            continue
        slug = extract_allergen_slug_from_unique_id(reg_entry.unique_id)
        if slug in RISK_SLUGS:
            candidates.append((reg_entry, slug))
    if not candidates:
        return

    suffixes = await hass.async_add_executor_job(localized_risk_object_id_suffixes)
    prefix = f"polleninformation_{location_slug}_"

    for reg_entry, slug in candidates:
        object_id = reg_entry.entity_id.split(".", 1)[1]
        localized = next(
            (s for s in suffixes[slug] if object_id == f"{prefix}{s}"), None
        )
        if localized is None:
            continue

        new_entity_id = f"{reg_entry.domain}.{prefix}{slug}"
        if not entity_id_available(hass, ent_reg, new_entity_id):
            _LOGGER.warning(
                "Cannot rename %s to %s: target entity_id already exists",
                reg_entry.entity_id,
                new_entity_id,
            )
            continue
        _LOGGER.info(
            "Renaming localized entity_id %s to %s", reg_entry.entity_id, new_entity_id
        )
        ent_reg.async_update_entity(reg_entry.entity_id, new_entity_id=new_entity_id)


def scale_allergy_risk(value: Any) -> int | None:
    try:
        return int(round(value / 2.5))
    except Exception:
        return None


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Get existing entities from registry to handle stale data scenarios
    ent_reg = er.async_get(hass)
    existing_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    existing_unique_ids = {
        e.unique_id
        for e in existing_entities
        if e.domain == "sensor" and not e.disabled
    }

    has_data = coordinator.data is not None
    raw_contamination = coordinator.data.get("contamination", []) if has_data else []
    # Emptiness is a question about usable allergens, not about how many
    # entries the API sent. An entry that identifies nothing builds no sensor,
    # so a block of nothing but those is as empty as a block of none, and
    # counting the raw list instead would leave the sensors this location
    # already has absent rather than recreated and marked stale.
    contamination = usable_contamination(raw_contamination)
    is_data_empty = len(contamination) == 0
    for item in raw_contamination:
        if allergen_names_from_item(item) is None:
            _LOGGER.warning(
                "Skipping a pollen entry that identifies no allergen: %r", item
            )

    # Options override data (options flow writes to entry.options)
    def _opt(key, default=None):
        return entry.options.get(key, entry.data.get(key, default))

    lat = _opt(CONF_LATITUDE)
    lon = _opt(CONF_LONGITUDE)
    country = _opt(CONF_COUNTRY)
    lang = _opt(CONF_LANG, DEFAULT_LANG)
    location_title = _opt("location_title")

    if not location_title or location_title.strip() == "":
        from .utils import async_get_country_options

        country_options = await async_get_country_options(hass)
        country_name = country_options.get(country, country)
        lat_str = f"{lat:.4f}" if lat is not None else "?"
        lon_str = f"{lon:.4f}" if lon is not None else "?"
        location_title = f"{country_name} ({lat_str}, {lon_str})"
    location_slug = normalize(location_title)

    # Needs location_slug: a rename only happens for the entity_id this
    # integration would itself have generated for this location.
    await async_migrate_localized_risk_entity_ids(hass, entry, location_slug)

    language_block_current = await async_get_language_block(hass, lang)
    language_block_en = await async_get_language_block(hass, "en")
    levels_current = LEVELS.get(
        lang, LEVELS.get("en", ["none", "low", "moderate", "high", "very high"])
    )
    levels_en = LEVELS.get("en", ["none", "low", "moderate", "high", "very high"])
    display_overrides = ALLERGEN_DISPLAY_OVERRIDES.get(lang, {})

    # When names follow the integration language, an explicit name is passed
    # to the risk sensors; otherwise they keep their translation key and are
    # named in the Home Assistant UI language.
    if _opt(CONF_NAMES_IN_INTEGRATION_LANG, DEFAULT_NAMES_IN_INTEGRATION_LANG):
        risk_names = RISK_SENSOR_NAMES.get(lang, RISK_SENSOR_NAMES["en"])
    else:
        risk_names = {}
    risk_name = risk_names.get("allergy_risk")
    risk_name_hourly = risk_names.get("allergy_risk_hourly")

    entities: list[SensorEntity] = []
    new_unique_ids: set[str] = set()
    allergen_renames: list[tuple[str, str]] = []

    for item in contamination:
        # Every entry here identifies an allergen: usable_contamination has
        # already dropped the ones that do not, warned about each, and counted
        # what is left towards is_data_empty above.
        name, latin = allergen_names_from_item(item)
        poll_title_local = capitalize_first(name)
        if not latin and poll_title_local:
            # A blank never matches a blank, in either direction: the language
            # map can hold an entry whose name is blank, for an allergen the
            # API named by its latin name alone, and matching that against a
            # blank display name would hand the nameless entry the other one's
            # latin name and make it that allergen.
            #
            # No accepted entry can reach here with a blank display name any
            # more: reaching this line at all means no latin name was sent,
            # and the guard above then refuses the entry unless it has a
            # display name. Kept because it costs one comparison and it is
            # what makes that reasoning safe to change.
            # Read defensively: this is the shipped language map, not the
            # response, and it is the one input on this path nothing type
            # checks. A latin name that is not a string would raise on the
            # lookups below and take the whole config entry down.
            for allergen in language_block_current.get("poll_titles") or []:
                if not isinstance(allergen, dict):
                    continue
                if allergen.get("name") and allergen["name"] == poll_title_local:
                    if isinstance(allergen.get("latin"), str):
                        latin = allergen["latin"]
                    break
        # Resolution order: the static latin map, then the English language
        # block, then the name the API sent in the configured language. Only
        # the last of these varies with the language, so it stays a last
        # resort for an allergen no released map knows about.
        allergen_en_obj = (
            get_allergen_info_by_latin(latin, language_block_en) if latin else None
        )
        legacy_en = allergen_en_obj["name"] if allergen_en_obj else poll_title_local
        mapped_en = english_name_for_latin(latin)
        if not latin:
            # The API sometimes sends the latin name as the display name and
            # leaves the latin field empty (e.g. "Artemisia"), so nothing above
            # had a latin name to look up. The static map is keyed by latin
            # name, so try the display name against it before giving up: this
            # keeps the canonical English slug and icon and avoids a spurious
            # "unknown allergen" warning. A latin name the API did send is
            # authoritative even when no map knows it, so this never runs then;
            # a localized display name that is not itself a latin name stays
            # unresolved.
            mapped_en = english_name_for_display_name(poll_title_local)
            if mapped_en is not None:
                # The display name is a latin name, so report it as one
                # instead of the empty latin field the API sent.
                latin = poll_title_local
        if mapped_en is None and allergen_en_obj is None:
            _LOGGER.warning(
                "Unknown allergen %r (latin %r); its entity_id will follow the "
                "configured language. Please report this at "
                "https://github.com/krissen/polleninformation/issues",
                poll_title_local,
                latin or "",
            )
        allergen_en = mapped_en or legacy_en
        # name_la reports what the API said about this allergen, so a latin
        # name that carries a species keeps it: "Ambrosia artemisiifolia" is
        # more than the genus and the attribute is where that belongs. The one
        # rewrite is a spelling the API is known to send in place of a latin
        # name, so the attribute carries a latin name rather than a localized
        # word. Deliberately not canonicalized: the restore path below can
        # only report the genus, and matching it here would mean discarding a
        # species the API did send. See the comment there.
        allergen_la = resolve_latin_alias(latin) if latin else ""
        if allergen_la != latin:
            _LOGGER.debug(
                "Reporting %r as %r for allergen %r",
                latin,
                allergen_la,
                poll_title_local,
            )
        slug_en = slugify(allergen_en) if allergen_en else slugify(poll_title_local)
        # Every slug a previous version could have given this allergen, not
        # only the one the current language block implies. Before the display
        # name was resolvable, an allergen the block could not place was
        # slugged from the name the API sent, so that slug is a candidate
        # whatever the block says NOW. It matters because the block itself
        # changes: repairing a missing latin name in the map turned the
        # English-block lookup from a miss into a hit, which made legacy_en
        # equal allergen_en and queued no rename at all, leaving the old
        # entity orphaned beside a new one. A candidate is only ever acted on
        # when an entity with that unique_id actually exists, so listing one
        # that never occurred costs nothing.
        legacy_candidates = [
            slugify(legacy_en) if legacy_en else "",
            slugify(poll_title_local),
        ]
        for legacy_slug in dict.fromkeys(legacy_candidates):
            if not legacy_slug or legacy_slug == slug_en:
                continue
            if legacy_slug in KNOWN_ALLERGEN_SLUGS:
                # The candidate names a DIFFERENT allergen, so renaming would
                # not recover this allergen's old entity, it would take that
                # other allergen's row and its history. Both candidates come
                # from the live response in the end: the display name always,
                # and the English-block name whenever the block has no entry
                # for the latin the API sent, which is the case for the ten
                # allergens the map does not cover. A title like
                # "Birch (Artemisia)" resolves to mugwort and would otherwise
                # claim the birch row.
                _LOGGER.warning(
                    "Not migrating %r to %r: %r is another allergen's name",
                    legacy_slug,
                    slug_en,
                    legacy_slug,
                )
                continue
            allergen_renames.append((legacy_slug, slug_en))
        icon = ALLERGEN_ICON_MAP.get(slug_en, ALLERGEN_ICON_MAP["default"])

        sensor = PolleninformationSensor(
            coordinator=coordinator,
            sensor_type="pollen",
            allergen_name=poll_title_local,
            allergen_en=allergen_en,
            allergen_slug=slug_en,
            allergen_latin=allergen_la,
            levels_current=levels_current,
            levels_en=levels_en,
            location_slug=location_slug,
            location_title=location_title,
            icon=icon,
            display_name=display_overrides.get(slug_en, poll_title_local),
            identity_from_response=True,
        )
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    migrate_localized_allergen_ids(hass, location_slug, allergen_renames)

    # The risk sensors are gated on the API having SENT pollen data, not on our
    # having been able to read it. An empty contamination block means the API
    # had nothing to say and a risk number beside it would be meaningless,
    # which is what this gate was written for. A block we could not parse is
    # the opposite case: the forecast was there, we failed at it, and the risk
    # reading beside it is real and readable. Throwing it away would lose a
    # number the API did send.
    api_sent_pollen = (
        bool(raw_contamination) if isinstance(raw_contamination, list) else False
    )
    allergyrisk = (
        usable_risk_block(coordinator.data, "allergyrisk")
        if has_data and api_sent_pollen
        else {}
    )
    if allergyrisk:
        sensor = AllergyRiskSensor(
            coordinator=coordinator,
            levels_current=levels_current,
            location_slug=location_slug,
            location_title=location_title,
            name=risk_name,
        )
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    # Gated the same way, and read through the same helper: a block that is
    # not an object is empty here exactly as it is for the sensor that reads
    # it and for the coordinator, rather than truthy in this one place.
    allergyrisk_hourly = (
        usable_risk_block(coordinator.data, "allergyrisk_hourly")
        if has_data and api_sent_pollen
        else {}
    )
    if allergyrisk_hourly:
        sensor = AllergyRiskHourlySensor(
            coordinator=coordinator,
            levels_current=levels_current,
            location_slug=location_slug,
            location_title=location_title,
            name=risk_name_hourly,
        )
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    # Recreate stale entities from registry when API returns empty data
    if is_data_empty and existing_unique_ids:
        _LOGGER.warning(
            "API returned empty data for %s, recreating %d entities as stale",
            location_title,
            len(existing_unique_ids),
        )
        for unique_id in existing_unique_ids:
            if unique_id in new_unique_ids:
                continue
            allergen_slug = extract_allergen_slug_from_unique_id(unique_id)
            if not allergen_slug:
                continue
            if allergen_slug == "allergy_risk":
                sensor = AllergyRiskSensor(
                    coordinator=coordinator,
                    levels_current=levels_current,
                    location_slug=location_slug,
                    location_title=location_title,
                    name=risk_name,
                )
            elif allergen_slug == "allergy_risk_hourly":
                sensor = AllergyRiskHourlySensor(
                    coordinator=coordinator,
                    levels_current=levels_current,
                    location_slug=location_slug,
                    location_title=location_title,
                    name=risk_name_hourly,
                )
            else:
                # The slug is all the registry keeps, so the names are
                # derived back from it; the API is not answering right now.
                # That makes name_la the key of LATIN_TO_ENGLISH_NAME here,
                # which is the genus for every allergen the API spells with
                # one, where the setup path reports the species alongside it
                # when the API sends one. The slug does not carry a species,
                # so this is the most this path can say. A sensor whose latin
                # name has a species therefore reports the genus alone for as
                # long as the outage lasts, and reports the species again on
                # the first answer. Reporting the genus in both places would
                # remove the difference by throwing away what the API told us,
                # which is the wrong way to make two paths agree.
                allergen_en, allergen_la = _slug_index().get(
                    allergen_slug, (allergen_slug.replace("_", " "), "")
                )
                # The API sends poll_title in the configured language, and it
                # does not always carry the latin name, so the match key has
                # to be the localized name. It comes from the same language
                # block the setup path reads it from. An allergen the block
                # does not carry keeps the English name and stays matchable
                # through the latin name in poll_title.
                localized = (
                    get_allergen_info_by_latin(allergen_la, language_block_current)
                    if allergen_la
                    else None
                )
                allergen_name = capitalize_first(
                    (localized or {}).get("name") or allergen_en
                )
                icon = ALLERGEN_ICON_MAP.get(
                    allergen_slug, ALLERGEN_ICON_MAP["default"]
                )
                sensor = PolleninformationSensor(
                    coordinator=coordinator,
                    sensor_type="pollen",
                    allergen_name=allergen_name,
                    allergen_en=allergen_en,
                    allergen_slug=allergen_slug,
                    allergen_latin=allergen_la,
                    levels_current=levels_current,
                    levels_en=levels_en,
                    location_slug=location_slug,
                    location_title=location_title,
                    icon=icon,
                    display_name=display_overrides.get(allergen_slug, allergen_name),
                )
            entities.append(sensor)
            if sensor.unique_id:
                new_unique_ids.add(sensor.unique_id)

    async_add_entities(entities, update_before_add=True)


def stale_attrs(coordinator) -> dict[str, Any]:
    """Return the staleness attributes for a response that carried no data.

    data_stale is response level BY DEFINITION: it says this location's fetch
    succeeded and returned nothing usable, not that one sensor is missing a
    reading. A sensor with no reading of its own is unknown and carries no
    marker. The coordinator owns the timestamp, so every entity of a location
    reports the same one for the same outage.
    """
    if not coordinator.empty_since:
        return {}
    return {"data_stale": True, "stale_since": coordinator.empty_since}


class PolleninformationSensor(CoordinatorEntity, SensorEntity):
    """Pollen allergen sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        allergen_name: str,
        allergen_en: str,
        allergen_slug: str,
        allergen_latin: str,
        levels_current: list,
        levels_en: list,
        location_slug: str,
        location_title: str,
        icon: str,
        display_name: str | None = None,
        identity_from_response: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        # Matching key against the API's poll_title; never overridden.
        self._allergen_name = allergen_name
        self._display_name = display_name or allergen_name
        self._allergen_en = allergen_en
        self._allergen_slug = allergen_slug
        self._allergen_latin = allergen_latin
        self._levels_current = levels_current
        self._levels_en = levels_en
        self._location_slug = location_slug
        self._location_title = location_title
        # Whether this response identified the allergen, rather than the slug
        # in the registry having been read back and turned into a latin name
        # again. Only the first is evidence about the row.
        self._identity_from_response = identity_from_response

        self._attr_name = self._display_name
        self._attr_unique_id = f"polleninformation_{location_slug}_{allergen_slug}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }

    async def async_added_to_hass(self) -> None:
        """Record on the registry row which allergen this sensor is.

        Here rather than in setup for two reasons. The row of an entity being
        created does not exist while setup runs, so setup could only ever
        record the allergens that already had a sensor; and by this point the
        entity_id is the migrated one, where writing earlier would stamp the
        very row the migration is still deciding about, with a latin name
        taken from the same response that is claiming it. Evidence a rename
        manufactures for itself is not evidence.

        Every allergen this response identified is recorded, not only a newly
        created one, so an installation upgrading into this starts accounting
        for the sensors it already has on the first start rather than only for
        sensors made afterwards. An allergen the response does not carry is
        not recorded, which includes every sensor recreated from the registry
        during an outage: what such a sensor knows about its latin name it
        derived from its own slug, so recording it would write down the
        assumption the recording exists to check rather than something the API
        said. Its row keeps whatever it already had.
        """
        await super().async_added_to_hass()
        if self._identity_from_response:
            store_allergen_identity(
                er.async_get(self.hass), self.entity_id, self._allergen_latin
            )

    @property
    def suggested_object_id(self) -> str:
        return self._allergen_slug

    @property
    def available(self) -> bool:
        # Only unavailable if coordinator update failed (connectivity issue)
        # Stale/empty data still shows as available but with state "unknown"
        return self.coordinator.last_update_success is not False

    def _find_item(self, contamination: list) -> dict | None:
        """Return this allergen's contamination entry, or None.

        The slug comes from the language-invariant latin name, so it
        identifies an entry outright and is searched first, across every
        entry. The name is only a fallback, for an entry no map can place
        and for a sensor recreated from the registry.

        Two entries can share a name: poll_title_local drops the
        parenthesized latin, so "Artemisia (Asteraceae)" and a bare
        "Artemisia" both leave "Artemisia" as the match key while resolving
        to different allergens. The name pass therefore skips any entry that
        identifies as a different allergen, and a name match only ever lands
        on an entry that nothing else claims.

        Entries that identify no allergen are dropped first, by the same
        predicate the setup path uses to decide which ones become sensors. A
        non-object entry beside a good one used to raise here on every update,
        which takes out every pollen sensor of the location rather than the
        one bad entry.
        """
        contamination = usable_contamination(contamination)
        for item in contamination:
            if allergen_slug_for_item(item) == self._allergen_slug:
                return item
        for item in contamination:
            slug = allergen_slug_for_item(item)
            if slug is not None and slug != self._allergen_slug:
                continue
            # The display name through the shared parse, not a third reading
            # of "the part before the bracket". The None cannot happen: the
            # list was filtered by the same predicate at the top of this
            # function, not by whoever called it. Handled anyway, so the line
            # states the invariant instead of depending on a filter four lines
            # up staying where it is.
            parsed = allergen_names_from_item(item)
            if parsed is None:
                continue
            name, _ = parsed
            if name.lower() == self._allergen_name.lower():
                return item
        return None

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        contamination = self.coordinator.data.get("contamination", [])
        found = self._find_item(contamination)
        if not found:
            return None
        raw_val = found.get("contamination_1", 0)
        try:
            return self._levels_current[raw_val]
        except (IndexError, TypeError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return stale_attrs(self.coordinator)

        contamination = self.coordinator.data.get("contamination", [])
        forecast = []
        base_date = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if item := self._find_item(contamination):
            for day in range(1, 5):
                val = item.get(f"contamination_{day}", 0)
                level_name = (
                    self._levels_current[val]
                    if isinstance(val, int) and val < len(self._levels_current)
                    else str(val)
                )
                forecast.append(
                    {
                        "time": (base_date + timedelta(days=day - 1)).strftime(
                            "%Y-%m-%dT%H:%M:%S"
                        ),
                        "level": val,
                        "level_name": level_name,
                    }
                )

        today_raw = forecast[0] if forecast else None
        tomorrow_raw = forecast[1] if len(forecast) > 1 else None
        attrs = {
            "forecast": forecast,
            "numeric_state": today_raw["level"] if today_raw else None,
            "named_state": today_raw["level_name"] if today_raw else None,
            "tomorrow_numeric_state": tomorrow_raw["level"] if tomorrow_raw else None,
            "tomorrow_named_state": tomorrow_raw["level_name"]
            if tomorrow_raw
            else None,
            "friendly_name": self._display_name,
            "name_en": self._allergen_en,
            "name_la": self._allergen_latin,
            "allergen_slug": self._allergen_slug,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "type": self.sensor_type,
            "attribution": "Austrian Pollen Information Service",
            "icon": self._attr_icon,
            "levels_current": self._levels_current,
            "levels_en": self._levels_en,
            "update_success": self.coordinator.last_update_success,
            "last_updated": self.coordinator.last_updated
            if self.coordinator.last_updated
            else None,
        }
        attrs.update(stale_attrs(self.coordinator))
        return attrs


class AllergyRiskSensor(CoordinatorEntity, SensorEntity):
    """Daily allergy risk sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "allergy_risk"

    def __init__(
        self,
        coordinator,
        levels_current: list,
        location_slug: str,
        location_title: str,
        name: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title

        # An explicit name wins over the translation key; leaving it unset
        # lets the name follow the Home Assistant UI language.
        if name:
            self._attr_name = name
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk"
        self._attr_icon = "mdi:alert"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }

    @property
    def suggested_object_id(self) -> str:
        # Pins the object_id to the English slug so the entity_id does not
        # follow the translated or explicitly set name.
        return "allergy_risk"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success is not False

    @property
    def native_value(self) -> str | None:
        allergyrisk = usable_risk_block(self.coordinator.data, "allergyrisk")
        if not allergyrisk:
            return None
        value = allergyrisk.get("allergyrisk_1", None)
        scaled = scale_allergy_risk(value) if value is not None else None
        if scaled is not None and scaled < len(self._levels_current):
            return self._levels_current[scaled]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        allergyrisk = usable_risk_block(self.coordinator.data, "allergyrisk")
        if not allergyrisk:
            attrs: dict[str, Any] = {
                "location_title": self._location_title,
                "location_slug": self._location_slug,
                "attribution": "Austrian Pollen Information Service",
            }
            attrs.update(stale_attrs(self.coordinator))
            return attrs

        forecast = []
        base_date = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for day in range(1, 5):
            value_raw = allergyrisk.get(f"allergyrisk_{day}", None)
            scaled = scale_allergy_risk(value_raw) if value_raw is not None else None
            level_name = (
                self._levels_current[scaled]
                if scaled is not None and scaled < len(self._levels_current)
                else None
            )
            forecast.append(
                {
                    "time": (base_date + timedelta(days=day - 1)).strftime(
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                    "level": scaled,
                    "level_name": level_name,
                    "level_raw": value_raw,
                }
            )
        raw_value = allergyrisk.get("allergyrisk_1", None)
        scaled_today = scale_allergy_risk(raw_value) if raw_value is not None else None
        attrs = {
            "named_state": self.native_value,
            "numeric_state": scaled_today,
            "numeric_state_raw": raw_value,
            "forecast": forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.last_update_success,
            "last_updated": self.coordinator.last_updated
            if self.coordinator.last_updated
            else None,
        }
        # The block being present is not a reading: it can carry only a later
        # day, or a null, and leave this sensor unknown while the response as
        # a whole was fine. That is unknown, not stale.
        attrs.update(stale_attrs(self.coordinator))
        return attrs


def hourly_readings(block, field):
    """Return one day's hourly readings as a sequence.

    Deliberately NOT in usable_risk_block. That predicate answers the question
    every caller shares, whether there is anything here to read. What shape a
    value must have to BE read belongs to the reader: the daily sensor wants a
    number and scale_allergy_risk already swallows anything that is not one,
    while this one wants a sequence of hours. A scalar has no length, and a
    mapping is indexed by key rather than by hour, so neither is a day.
    """
    values = block.get(field)
    return values if isinstance(values, (list, tuple)) else []


class AllergyRiskHourlySensor(CoordinatorEntity, SensorEntity):
    """Hourly allergy risk sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "allergy_risk_hourly"

    def __init__(
        self,
        coordinator,
        levels_current: list,
        location_slug: str,
        location_title: str,
        name: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title

        # An explicit name wins over the translation key; leaving it unset
        # lets the name follow the Home Assistant UI language.
        if name:
            self._attr_name = name
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk_hourly"
        self._attr_icon = "mdi:timeline-clock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }

    @property
    def suggested_object_id(self) -> str:
        # Pins the object_id to the English slug so the entity_id does not
        # follow the translated or explicitly set name.
        return "allergy_risk_hourly"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success is not False

    @property
    def native_value(self) -> str | None:
        allergyrisk_hourly = usable_risk_block(
            self.coordinator.data, "allergyrisk_hourly"
        )
        if not allergyrisk_hourly:
            return None
        now_hour = dt_util.now().hour
        values = hourly_readings(allergyrisk_hourly, "allergyrisk_hourly_1")
        if 0 <= now_hour < len(values):
            raw = values[now_hour]
            scaled = scale_allergy_risk(raw)
            if scaled is not None and scaled < len(self._levels_current):
                return self._levels_current[scaled]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        allergyrisk_hourly = usable_risk_block(
            self.coordinator.data, "allergyrisk_hourly"
        )
        if not allergyrisk_hourly:
            attrs: dict[str, Any] = {
                "location_title": self._location_title,
                "location_slug": self._location_slug,
                "attribution": "Austrian Pollen Information Service",
            }
            attrs.update(stale_attrs(self.coordinator))
            return attrs

        base_time = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
        forecast = []
        for day in range(1, 5):
            values = hourly_readings(allergyrisk_hourly, f"allergyrisk_hourly_{day}")
            for hour, raw in enumerate(values):
                dt = base_time + timedelta(days=day - 1, hours=hour)
                scaled = scale_allergy_risk(raw)
                named = (
                    self._levels_current[scaled]
                    if scaled is not None and scaled < len(self._levels_current)
                    else None
                )
                forecast.append(
                    {
                        "time": dt.isoformat(),
                        "level": scaled,
                        "level_name": named,
                        "level_raw": raw,
                    }
                )

        now_hour = dt_util.now().hour
        values_today = hourly_readings(allergyrisk_hourly, "allergyrisk_hourly_1")
        raw_now = values_today[now_hour] if 0 <= now_hour < len(values_today) else None
        scaled_now = scale_allergy_risk(raw_now) if raw_now is not None else None
        named_now = (
            self._levels_current[scaled_now]
            if scaled_now is not None and scaled_now < len(self._levels_current)
            else None
        )
        attrs = {
            "named_state": named_now,
            "numeric_state": scaled_now,
            "numeric_state_raw": raw_now,
            "forecast": forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.last_update_success,
            "last_updated": self.coordinator.last_updated
            if self.coordinator.last_updated
            else None,
        }
        # The block being present is not a reading: it can carry only a later
        # day, or a null, and leave this sensor unknown while the response as
        # a whole was fine. That is unknown, not stale.
        attrs.update(stale_attrs(self.coordinator))
        return attrs

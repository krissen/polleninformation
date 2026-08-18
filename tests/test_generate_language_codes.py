"""Tests for scripts/generate_language_codes.py.

The script is not importable as a module (scripts/ is not a package and the
file name is not an identifier we import anywhere), so it is loaded from its
path. Loading it must stay free of side effects: it may not read API_KEY or
import requests at import time, which is why those live inside run_fetch.
"""

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_language_codes.py"
LANGUAGE_MAP = (
    REPO_ROOT / "custom_components" / "polleninformation" / "language_map.json"
)


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "generate_language_codes", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    """The generator, loaded from its path."""
    return _load_script()


class TestSplitPollTitle:
    """The transcription step: what the API sent, split in two."""

    def test_name_with_latin_in_brackets(self, script):
        assert script.split_poll_title("Ragweed (Ambrosia)") == (
            "Ragweed",
            "Ambrosia",
        )

    def test_localized_word_in_brackets_is_transcribed_as_sent(self, script):
        # The split does not judge; resolve_latin does.
        assert script.split_poll_title("Ragweed (ambrózia)") == (
            "Ragweed",
            "ambrózia",
        )

    def test_bare_name_has_no_latin(self, script):
        assert script.split_poll_title("Artemisia") == ("Artemisia", "")

    def test_empty_title(self, script):
        assert script.split_poll_title("") == ("", "")


class TestResolveLatin:
    """The validation step, over the shapes the API actually sends."""

    def test_known_latin_is_kept_without_a_warning(self, script):
        assert script.resolve_latin("Trávy", "Poaceae") == ("Poaceae", [])

    def test_genus_and_species_is_kept(self, script):
        latin, warnings = script.resolve_latin("Ambrosia", "Ambrosia artemisiifolia")
        assert latin == "Ambrosia artemisiifolia"
        assert warnings == []

    def test_a_declared_alias_is_recorded_as_the_name_it_stands_for(self, script):
        # The sk shape: the API put the Slovak word for ragweed where the
        # latin name goes. That spelling is declared in LATIN_NAME_ALIASES,
        # which is the only thing that may override what the API sent.
        latin, warnings = script.resolve_latin("Ragweed", "ambrózia")
        assert latin == "Ambrosia"
        assert len(warnings) == 1
        assert "ambrózia" in warnings[0]

    def test_an_alias_is_matched_case_insensitively(self, script):
        assert script.resolve_latin("Ragweed", "Ambrózia")[0] == "Ambrosia"

    def test_display_name_that_is_a_latin_name_supplies_the_missing_latin(self, script):
        # The es shape, and the shape reported in issue #71.
        latin, warnings = script.resolve_latin("Artemisia", "")
        assert latin == "Artemisia"
        assert len(warnings) == 1
        assert "Artemisia" in warnings[0]

    def test_a_latin_the_api_sent_outranks_a_latin_display_name(self, script):
        # "Artemisia (Asteraceae)" is the composite family, not mugwort. The
        # display name may only be read as a latin name when the API sent
        # none, exactly as the setup path in sensor.py has it.
        latin, warnings = script.resolve_latin("Artemisia", "Asteraceae")
        assert latin == "Asteraceae"
        assert len(warnings) == 1
        assert "Keeping it" in warnings[0]

    def test_an_english_display_name_never_overrides_a_latin_one(self, script):
        # "Ragweed (Asteraceae)" is the case that ruled out inferring a latin
        # name from the display name. Asteraceae is not a declared alias, so
        # nothing touches it.
        latin, warnings = script.resolve_latin("Ragweed", "Asteraceae")
        assert latin == "Asteraceae"
        assert len(warnings) == 1
        assert "Keeping it" in warnings[0]

    def test_unknown_latin_is_kept_as_sent_and_warned_about(self, script):
        latin, warnings = script.resolve_latin("Nässlor", "Nonexistentia")
        assert latin == "Nonexistentia"
        assert len(warnings) == 1
        assert "please open an issue" in warnings[0]

    def test_unknown_allergen_without_a_latin_is_warned_about(self, script):
        latin, warnings = script.resolve_latin("Något nytt", "")
        assert latin == ""
        assert len(warnings) == 1
        assert "no latin name" in warnings[0]


class TestPollTitlesFromContamination:
    """Nothing the API sends is ever dropped."""

    def test_every_entry_is_recorded(self, script):
        contamination = [
            {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
            {"poll_title": "Ragweed (ambrózia)", "poll_id": 6},
            {"poll_title": "Artemisia", "poll_id": 7},
            {"poll_title": "Något nytt (Nonexistentia)", "poll_id": 999},
        ]
        poll_titles, warnings = script.poll_titles_from_contamination(contamination)

        assert [entry["poll_id"] for entry in poll_titles] == [5, 6, 7, 999]
        assert [entry["latin"] for entry in poll_titles] == [
            "Poaceae",
            "Ambrosia",
            "Artemisia",
            "Nonexistentia",
        ]
        # One warning each for the two repairs and the unknown allergen.
        assert len(warnings) == 3

    def test_display_names_are_kept_as_the_api_sent_them(self, script):
        poll_titles, _ = script.poll_titles_from_contamination(
            [{"poll_title": "Ragweed (ambrózia)", "poll_id": 6}]
        )
        assert poll_titles[0]["name"] == "Ragweed"


class TestRepairDb:
    """The offline pass that lets an already recorded entry correct itself."""

    def test_repairs_the_two_shipped_shapes(self, script):
        db = {
            "sk": {
                "lang_code": "sk",
                "poll_titles": [
                    {"name": "Trávy", "latin": "Poaceae", "poll_id": 5},
                    {"name": "Ragweed", "latin": "ambrózia", "poll_id": 6},
                ],
            },
            "es": {
                "lang_code": "es",
                "poll_titles": [
                    {"name": "Artemisia", "latin": "", "poll_id": 7},
                ],
            },
        }
        changes, warnings = script.repair_db(db)

        assert db["sk"]["poll_titles"][1]["latin"] == "Ambrosia"
        assert db["es"]["poll_titles"][0]["latin"] == "Artemisia"
        assert len(changes) == 2
        assert len(warnings) == 2

    def test_leaves_a_clean_db_untouched(self, script):
        db = {
            "en": {
                "lang_code": "en",
                "poll_titles": [{"name": "grasses", "latin": "Poaceae", "poll_id": 5}],
            }
        }
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert warnings == []
        assert db["en"]["poll_titles"][0]["latin"] == "Poaceae"

    def test_is_idempotent(self, script):
        db = {
            "sk": {
                "lang_code": "sk",
                "poll_titles": [{"name": "Ragweed", "latin": "ambrózia"}],
            }
        }
        script.repair_db(db)
        changes, _ = script.repair_db(db)

        assert changes == []

    def test_keeps_an_unknown_allergen_and_warns_again(self, script):
        db = {
            "sv": {
                "lang_code": "sv",
                "poll_titles": [{"name": "Något nytt", "latin": "Nonexistentia"}],
            }
        }
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert len(warnings) == 1
        assert db["sv"]["poll_titles"][0]["latin"] == "Nonexistentia"

    def test_keeps_a_latin_the_api_sent_that_no_map_knows(self, script):
        # The repair rewrites a file we ship, so an entry the API recorded
        # correctly must survive it. Reading "Artemisia" as the latin name
        # here would record the composite family as mugwort, and the next
        # repair run would then confirm that as correct.
        db = {
            "de": {
                "lang_code": "de",
                "poll_titles": [
                    {"name": "Artemisia", "latin": "Asteraceae", "poll_id": 300}
                ],
            }
        }
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert db["de"]["poll_titles"][0]["latin"] == "Asteraceae"
        assert len(warnings) == 1

    def test_a_correctly_recorded_entry_survives_a_round_trip(self, script):
        db = {
            "de": {
                "lang_code": "de",
                "poll_titles": [
                    {"name": "Gräser", "latin": "Poaceae", "poll_id": 5},
                    {"name": "Artemisia", "latin": "Asteraceae", "poll_id": 300},
                ],
            }
        }
        before = json.dumps(db, sort_keys=True)

        script.repair_db(db)
        script.repair_db(db)

        assert json.dumps(db, sort_keys=True) == before

    def test_tolerates_an_error_entry(self, script):
        db = {"tr": {"lang_code": "tr", "error": "request error: timeout"}}
        assert script.repair_db(db) == ([], [])


class TestShippedLanguageMap:
    """The file itself, as shipped."""

    def test_every_recorded_latin_name_is_recognized(self, script):
        db = json.loads(LANGUAGE_MAP.read_text(encoding="utf-8"))
        unrecognized = [
            (lang_code, entry["name"], entry["latin"])
            for lang_code, block in db.items()
            for entry in block.get("poll_titles", [])
            if not script.english_name_for_latin(entry["latin"])
        ]
        assert unrecognized == []

    def test_needs_no_repair(self, script):
        db = json.loads(LANGUAGE_MAP.read_text(encoding="utf-8"))
        changes, warnings = script.repair_db(db)
        assert (changes, warnings) == ([], [])

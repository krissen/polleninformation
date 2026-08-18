"""Tests for scripts/generate_language_codes.py.

The script is not importable as a module (scripts/ is not a package and the
file name is not an identifier we import anywhere), so it is loaded from its
path. Loading it must stay free of side effects: it may not read API_KEY or
import requests at import time, which is why those live inside run_fetch.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from custom_components.polleninformation.sensor import (
    allergen_slug_for_item,
    english_name_for_latin,
)
from custom_components.polleninformation.utils import slugify

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

    @pytest.mark.parametrize("poll_title", [None, 123, ["Ragweed"], {"a": 1}])
    def test_a_title_that_is_not_a_string_reads_as_empty(self, script, poll_title):
        # Raising here would cost the language its other allergens.
        assert script.split_poll_title(poll_title) == ("", "")


class TestResolveLatin:
    """The validation step, over the shapes the API actually sends."""

    def test_known_latin_is_kept_without_a_warning(self, script):
        assert script.resolve_latin("Trávy", "Poaceae") == ("Poaceae", [])

    def test_genus_and_species_is_recorded_as_the_genus(self, script):
        # Every consumer of this file matches a latin name exactly, and the
        # one the restore path holds is the map's own key.
        latin, warnings = script.resolve_latin("Ambrosia", "Ambrosia artemisiifolia")
        assert latin == "Ambrosia"
        assert len(warnings) == 1

    @pytest.mark.parametrize("sent", ["poaceae", " Poaceae ", "POACEAE"])
    def test_a_recognized_latin_is_recorded_under_the_map_key(self, script, sent):
        latin, warnings = script.resolve_latin("Trávy", sent)
        assert latin == "Poaceae"
        assert len(warnings) == 1

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

    def test_a_blank_display_name_is_kept_and_warned_about(self, script):
        # "(Poaceae)" names its allergen, so dropping it would be the mistake,
        # but the file holds half a pairing and that is worth reporting.
        latin, warnings = script.resolve_latin("", "Poaceae")

        assert latin == "Poaceae"
        assert len(warnings) == 1
        assert "no display name" in warnings[0]
        assert "Poaceae" in warnings[0]

    def test_a_blank_name_beside_a_spelling_fix_warns_about_both(self, script):
        latin, warnings = script.resolve_latin("", "poaceae")

        assert latin == "Poaceae"
        assert len(warnings) == 2

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

    def test_one_malformed_entry_does_not_cost_the_others(self, script):
        contamination = [
            {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
            {"poll_title": 123, "poll_id": 6},
            {"poll_title": "Breza (Betula)", "poll_id": 2},
        ]
        poll_titles, warnings = script.poll_titles_from_contamination(contamination)

        assert [entry["poll_id"] for entry in poll_titles] == [5, 2]
        assert [entry["latin"] for entry in poll_titles] == ["Poaceae", "Betula"]
        assert len(warnings) == 1

    @pytest.mark.parametrize(
        "poll",
        [
            # Nothing to read at all.
            {"poll_id": 6},
            {"poll_title": 123},
            {"poll_title": ""},
            {"poll_title": "  "},
            # A non-blank title with nothing in either half of it, which
            # identifies an allergen exactly as little as the four above.
            {"poll_title": "()"},
            {"poll_title": "( )"},
            {"poll_title": "  (  )  "},
            {"poll_title": "()extra"},
        ],
    )
    def test_an_entry_that_identifies_nothing_is_skipped(self, script, poll):
        # An unknown latin name still names a real allergen and is kept. An
        # entry with neither a display name nor a latin name names nothing, so
        # recording it would manufacture a blank allergen and make a block of
        # them look like a language that has some.
        poll_titles, warnings = script.poll_titles_from_contamination([poll])

        assert poll_titles == []
        assert len(warnings) == 1
        assert "identifies no allergen" in warnings[0]

    @pytest.mark.parametrize(
        ("poll_title", "expected"),
        [
            ("(Poaceae)", {"name": "", "latin": "Poaceae"}),
            ("Trávy", {"name": "Trávy", "latin": ""}),
            ("Trávy (Poaceae)", {"name": "Trávy", "latin": "Poaceae"}),
        ],
    )
    def test_either_half_alone_is_enough_to_be_kept(self, script, poll_title, expected):
        # The rule is what the entry identifies, so one half is enough: a
        # latin name with no display name is an allergen this language has no
        # word for, and a display name with no latin name is one we may not be
        # able to classify. Both are kept.
        poll_titles, _ = script.poll_titles_from_contamination(
            [{"poll_title": poll_title, "poll_id": 5}]
        )

        assert poll_titles == [{**expected, "poll_id": 5}]

    @pytest.mark.parametrize("contamination", ["oops", None, {"poll_title": "x"}])
    def test_a_block_that_is_not_a_list_is_reported(self, script, contamination):
        poll_titles, warnings = script.poll_titles_from_contamination(contamination)
        assert poll_titles == []
        assert len(warnings) == 1

    def test_an_entry_that_is_not_an_object_is_reported(self, script):
        poll_titles, warnings = script.poll_titles_from_contamination(
            [{"poll_title": "Trávy (Poaceae)", "poll_id": 5}, "oops"]
        )
        assert len(poll_titles) == 1
        assert len(warnings) == 1

    def test_a_title_that_is_only_a_latin_name_is_kept(self, script):
        poll_titles, warnings = script.poll_titles_from_contamination(
            [{"poll_title": "(Poaceae)", "poll_id": 5}]
        )

        assert poll_titles == [{"name": "", "latin": "Poaceae", "poll_id": 5}]
        assert len(warnings) == 1
        assert "no display name" in warnings[0]

    def test_display_names_are_kept_as_the_api_sent_them(self, script):
        poll_titles, _ = script.poll_titles_from_contamination(
            [{"poll_title": "Ragweed (ambrózia)", "poll_id": 6}]
        )
        assert poll_titles[0]["name"] == "Ragweed"


class TestUnreadableEntryWarning:
    """The one path in this script that destroys something says so first."""

    @pytest.mark.parametrize("entry", ["oops", 42, ["sk"], True])
    def test_an_entry_that_cannot_be_read_is_announced(self, script, entry):
        warning = script.unreadable_entry_warning({"sk": entry}, "sk")

        assert warning is not None
        assert "overwriting" in warning
        # It is refetched, which is the behaviour being announced.
        assert script.needs_fetch({"sk": entry}, "sk")

    def test_a_language_that_is_absent_says_nothing(self, script):
        assert script.unreadable_entry_warning({}, "sk") is None

    def test_an_error_entry_says_nothing(self, script):
        db = {"sk": {"lang_code": "sk", "error": "request error: timeout"}}
        assert script.unreadable_entry_warning(db, "sk") is None

    def test_a_good_entry_says_nothing(self, script):
        db = {"sk": {"lang_code": "sk", "poll_titles": []}}
        assert script.unreadable_entry_warning(db, "sk") is None


class TestLanguageEntryFromResponse:
    """What one language's response is worth, before it reaches the file.

    A response no allergen can be read from is recorded as an error rather
    than as a language that has none, because only an error entry is fetched
    again. An empty response and a malformed one are not told apart here: for
    this file they are the same defect, a language with no allergen names.
    """

    def test_a_good_response_records_its_allergens(self, script):
        entry, warnings = script.language_entry_from_response(
            "sk",
            {"contamination": [{"poll_title": "Trávy (Poaceae)", "poll_id": 5}]},
        )

        assert entry["lang_code"] == "sk"
        assert entry["lang"] == "Slovak"
        assert entry["poll_titles"] == [
            {"name": "Trávy", "latin": "Poaceae", "poll_id": 5}
        ]
        assert warnings == []

    def test_a_top_level_that_is_not_an_object_is_an_error_entry(self, script):
        # An array is what an upstream error looks like, and recording it as a
        # language with no allergens would be permanent.
        entry, _ = script.language_entry_from_response("sk", [])
        assert "error" in entry
        assert "top level" in entry["error"]

    @pytest.mark.parametrize("data", [[], "oops", None, 42])
    def test_no_malformed_top_level_is_recorded_as_a_success(self, script, data):
        entry, _ = script.language_entry_from_response("sk", data)
        assert "error" in entry
        assert "poll_titles" not in entry

    def test_a_missing_contamination_block_is_an_error_entry(self, script):
        entry, _ = script.language_entry_from_response("sk", {"allergyrisk": {}})
        assert "error" in entry

    def test_an_empty_contamination_block_is_an_error_entry(self, script):
        entry, _ = script.language_entry_from_response("sk", {"contamination": []})
        assert "error" in entry

    def test_a_contamination_block_that_is_not_a_list_is_an_error_entry(self, script):
        entry, warnings = script.language_entry_from_response(
            "sk", {"contamination": "oops"}
        )
        assert "error" in entry
        assert len(warnings) == 1

    def test_a_block_of_unreadable_entries_is_an_error_entry(self, script):
        entry, warnings = script.language_entry_from_response(
            "sk", {"contamination": ["oops", "also oops"]}
        )
        assert "error" in entry
        assert len(warnings) == 2

    def test_a_block_of_title_less_entries_is_an_error_entry(self, script):
        # The chain end to end: every entry is skipped for naming nothing,
        # which leaves no allergens, which is an error entry, which
        # needs_fetch comes back for.
        entry, warnings = script.language_entry_from_response(
            "sk", {"contamination": [{"poll_id": 5}, {"poll_id": 6}]}
        )

        assert "error" in entry
        assert len(warnings) == 2
        assert script.needs_fetch({"sk": entry}, "sk")

    def test_a_readable_entry_beside_an_unreadable_one_is_kept(self, script):
        entry, warnings = script.language_entry_from_response(
            "sk",
            {
                "contamination": [
                    "oops",
                    {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
                ]
            },
        )
        assert [poll["latin"] for poll in entry["poll_titles"]] == ["Poaceae"]
        # One for the entry that was dropped, one for the language being left
        # incomplete because of it.
        assert len(warnings) == 2

    def test_a_response_that_lost_an_entry_is_marked_incomplete(self, script):
        entry, warnings = script.language_entry_from_response(
            "sk",
            {
                "contamination": [
                    {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
                    {"poll_title": "()", "poll_id": 6},
                ]
            },
        )

        assert entry["incomplete"] is True
        assert [poll["latin"] for poll in entry["poll_titles"]] == ["Poaceae"]
        assert any("incomplete" in w for w in warnings)

    def test_an_incomplete_language_is_fetched_again(self, script):
        # The property that matters: nothing else would ever come back for the
        # entry that was lost, since a saved language is skipped and --repair
        # cannot invent an entry that was never recorded.
        entry, _ = script.language_entry_from_response(
            "sk",
            {
                "contamination": [
                    {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
                    {"poll_title": "()", "poll_id": 6},
                ]
            },
        )

        assert script.needs_fetch({"sk": entry}, "sk")

    def test_a_complete_response_is_not_marked(self, script):
        entry, _ = script.language_entry_from_response(
            "sk", {"contamination": [{"poll_title": "Trávy (Poaceae)", "poll_id": 5}]}
        )

        assert "incomplete" not in entry
        assert not script.needs_fetch({"sk": entry}, "sk")


# A language the file already holds names for, marked for another try. What a
# failed retry must not be allowed to take away.
PARTIAL_ENTRY = {
    "lang_code": "sk",
    "lang": "Slovak",
    "poll_titles": [{"name": "Trávy", "latin": "Poaceae", "poll_id": 5}],
    "incomplete": True,
}

PARTIAL_DB = {"sk": PARTIAL_ENTRY}


class TestARetryNeverImpoverishesAnEntry:
    """A retry may improve what the file holds and may not take from it.

    The incomplete marker exists because eleven localized names are worth
    more to a sensor than none. The retry it schedules must not then do the
    thing the marker refused: a failed or malformed retry that replaced the
    entry with an error object would drop those names and send every allergen
    in that language back to its English name.
    """

    @pytest.mark.parametrize(
        "failure",
        [
            {"error": "request error: timeout", "lang_code": "sk"},
            {"error": "malformed response: no contamination block", "lang_code": "sk"},
            {"error": "the response carries no allergens", "lang_code": "sk"},
        ],
    )
    def test_a_failed_retry_keeps_the_names(self, script, failure):
        kept = script.entry_after_retry(PARTIAL_ENTRY, failure)

        assert kept["poll_titles"] == PARTIAL_ENTRY["poll_titles"]

    def test_a_failed_retry_says_the_names_are_old(self, script):
        # The record may not read as a clean partial when it is a partial
        # plus a failure.
        kept = script.entry_after_retry(
            PARTIAL_ENTRY, {"error": "request error: timeout", "lang_code": "sk"}
        )

        assert "earlier fetch" in kept["retry_error"]
        assert "request error: timeout" in kept["retry_error"]

    def test_a_failed_retry_stays_retryable(self, script):
        kept = script.entry_after_retry(
            PARTIAL_ENTRY, {"error": "request error: timeout", "lang_code": "sk"}
        )

        assert script.needs_fetch({"sk": kept}, "sk")

    def test_a_clean_retry_replaces_the_entry(self, script):
        fresh = {
            "lang_code": "sk",
            "lang": "Slovak",
            "poll_titles": [
                {"name": "Trávy", "latin": "Poaceae", "poll_id": 5},
                {"name": "Breza", "latin": "Betula", "poll_id": 2},
            ],
        }
        got = script.entry_after_retry(PARTIAL_ENTRY, fresh)

        assert got == fresh
        assert "incomplete" not in got
        assert "retry_error" not in got
        assert not script.needs_fetch({"sk": got}, "sk")

    @pytest.mark.parametrize(
        "previous",
        [
            None,
            "oops",
            {"lang_code": "sk", "error": "request error: timeout"},
            {"lang_code": "sk", "poll_titles": []},
        ],
    )
    def test_nothing_to_keep_records_the_error_as_before(self, script, previous):
        failure = {"error": "request error: timeout", "lang_code": "sk"}
        assert script.entry_after_retry(previous, failure) == failure

    def test_a_complete_entry_is_never_retried_and_so_never_clobbered(self, script):
        # The answer to whether a transient failure can cost a COMPLETE
        # language its names: it is not reachable, because such an entry is
        # never fetched again. Pinned both ways, so neither half can drift.
        complete = {
            "lang_code": "sk",
            "lang": "Slovak",
            "poll_titles": [{"name": "Trávy", "latin": "Poaceae", "poll_id": 5}],
        }
        assert not script.needs_fetch({"sk": complete}, "sk")
        kept = script.entry_after_retry(
            complete, {"error": "request error: timeout", "lang_code": "sk"}
        )
        assert kept["poll_titles"] == complete["poll_titles"]


class TestRunFetchWritesThroughTheRetryRule:
    """The rule where it actually lands: the two lines that write the file.

    Both failure paths in run_fetch assign to db[lang_code], and either one
    could drop an entry's allergen names. Exercised end to end, with the
    network and the environment stubbed, because a helper that gets this
    right is worth nothing if the caller writes past it.
    """

    @staticmethod
    def _run(script, monkeypatch, tmp_path, existing, responder):
        db_file = tmp_path / "language_map.json"
        db_file.write_text(json.dumps(existing), encoding="utf-8")
        monkeypatch.setattr(script, "DB_FILE", str(db_file))
        monkeypatch.setattr(script, "LANG_CODES", ["sk"])
        monkeypatch.setattr(script, "DELAY_SEC", 0)
        monkeypatch.setenv("API_KEY", "test-key")
        monkeypatch.setitem(
            sys.modules, "requests", types.SimpleNamespace(get=responder)
        )
        monkeypatch.setitem(
            sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda **kw: None)
        )
        script.run_fetch()
        return json.loads(db_file.read_text(encoding="utf-8"))

    @staticmethod
    def _answer(payload):
        def responder(*args, **kwargs):
            return types.SimpleNamespace(
                raise_for_status=lambda: None, json=lambda: payload
            )

        return responder

    def test_a_request_failure_keeps_the_names_on_disk(
        self, script, monkeypatch, tmp_path
    ):
        def boom(*args, **kwargs):
            raise RuntimeError("timeout")

        db = self._run(script, monkeypatch, tmp_path, PARTIAL_DB, boom)

        assert db["sk"]["poll_titles"] == PARTIAL_ENTRY["poll_titles"]
        assert "earlier fetch" in db["sk"]["retry_error"]
        assert script.needs_fetch(db, "sk")

    def test_a_malformed_response_keeps_the_names_on_disk(
        self, script, monkeypatch, tmp_path
    ):
        db = self._run(
            script, monkeypatch, tmp_path, PARTIAL_DB, self._answer({"nope": 1})
        )

        assert db["sk"]["poll_titles"] == PARTIAL_ENTRY["poll_titles"]
        assert "earlier fetch" in db["sk"]["retry_error"]

    def test_a_clean_retry_replaces_what_was_there(self, script, monkeypatch, tmp_path):
        payload = {
            "contamination": [
                {"poll_title": "Trávy (Poaceae)", "poll_id": 5},
                {"poll_title": "Breza (Betula)", "poll_id": 2},
            ]
        }
        db = self._run(script, monkeypatch, tmp_path, PARTIAL_DB, self._answer(payload))

        assert len(db["sk"]["poll_titles"]) == 2
        assert "incomplete" not in db["sk"]
        assert "retry_error" not in db["sk"]
        assert not script.needs_fetch(db, "sk")

    def test_a_language_with_nothing_to_lose_records_the_error(
        self, script, monkeypatch, tmp_path
    ):
        def boom(*args, **kwargs):
            raise RuntimeError("timeout")

        db = self._run(script, monkeypatch, tmp_path, {}, boom)

        assert "error" in db["sk"]
        assert "poll_titles" not in db["sk"]


class TestNeedsFetch:
    """Which languages the next run goes back for."""

    def test_a_language_that_is_not_there_is_fetched(self, script):
        assert script.needs_fetch({}, "sk")

    def test_a_recorded_language_is_not_refetched(self, script):
        db = {"sk": {"lang_code": "sk", "poll_titles": []}}
        assert not script.needs_fetch(db, "sk")

    def test_an_incomplete_entry_is_retried(self, script):
        db = {"sk": {"lang_code": "sk", "poll_titles": [], "incomplete": True}}
        assert script.needs_fetch(db, "sk")

    def test_an_error_entry_is_retried(self, script):
        db = {"sk": {"lang_code": "sk", "error": "request error: timeout"}}
        assert script.needs_fetch(db, "sk")

    def test_a_malformed_response_is_retried_on_the_next_run(self, script):
        # The two halves together: a response that cannot be read is recorded
        # as an error, and an error is what the next run comes back for.
        entry, _ = script.language_entry_from_response("sk", [])
        assert script.needs_fetch({"sk": entry}, "sk")

    def test_a_language_that_is_not_an_object_is_refetched(self, script):
        assert script.needs_fetch({"sk": "oops"}, "sk")


class TestDbFilePath:
    """The map's path is a property of the repo, not of the shell.

    Relative, it resolved against the working directory, so a run from
    anywhere else read no file, found no languages, fetched all sixteen and
    wrote a new map into that directory. Nothing downstream can catch it: a
    file that is merely absent looks exactly like an empty database.
    """

    def test_the_path_is_absolute(self, script):
        assert Path(script.DB_FILE).is_absolute()

    def test_it_points_at_the_map_in_this_repo(self, script):
        assert Path(script.DB_FILE) == LANGUAGE_MAP

    def test_the_map_is_found_from_another_directory(
        self, script, tmp_path, monkeypatch
    ):
        monkeypatch.chdir(tmp_path)
        assert len(script.load_db()) == 16


class TestLoadDb:
    """The level above the root: the file may not be JSON at all."""

    def test_a_missing_file_is_an_empty_db(self, script, tmp_path):
        with patch.object(script, "DB_FILE", str(tmp_path / "nothing.json")):
            assert script.load_db() == {}

    def test_a_file_that_is_not_json_stops_the_run(self, script, tmp_path):
        # Reading it as an empty db would be the destructive answer: the fetch
        # would refetch every language and write over whatever is in there.
        broken = tmp_path / "language_map.json"
        broken.write_text('{"sk": ', encoding="utf-8")
        with (
            patch.object(script, "DB_FILE", str(broken)),
            pytest.raises(SystemExit) as excinfo,
        ):
            script.load_db()
        assert "not valid JSON" in str(excinfo.value)


class TestRunRepairReachesTheValidator:
    """The entry point may not decide what the validator gets to see.

    `if not db` sent every falsy root down the "nothing to repair" path: a
    file holding [], "", 0, false or null was reported as an empty database,
    which is the one answer that is certainly wrong for the mode whose job is
    to diagnose a malformed file.
    """

    @staticmethod
    def _run(script, monkeypatch, capsys, db):
        monkeypatch.setattr(script, "load_db", lambda: db)
        script.run_repair()
        return capsys.readouterr().out

    @pytest.mark.parametrize("db", [[], "", 0, False, None, ["sk"], "oops", 42])
    def test_a_non_dict_root_reaches_the_validator(
        self, script, monkeypatch, capsys, db
    ):
        out = self._run(script, monkeypatch, capsys, db)

        assert "root" in out
        assert "No languages" not in out

    def test_an_empty_database_is_not_a_malformed_one(
        self, script, monkeypatch, capsys
    ):
        # A missing file reads as {} too, and that is the ordinary first run.
        out = self._run(script, monkeypatch, capsys, {})

        assert "No languages" in out
        assert "root" not in out

    def test_a_good_database_is_repaired_as_before(self, script, monkeypatch, capsys):
        db = {
            "sk": {
                "lang_code": "sk",
                "poll_titles": [{"name": "Trávy", "latin": "Poaceae"}],
            }
        }
        out = self._run(script, monkeypatch, capsys, db)

        assert "Nothing to repair" in out


class TestRepairDbRoot:
    """The level above the per-language checks: the file's own root."""

    @pytest.mark.parametrize(
        "db",
        # Truthy and falsy alike: the validator never saw the falsy ones,
        # because the entry point above returned before calling it.
        [["sk"], "oops", 42, True, [], "", 0, False, None],
    )
    def test_a_root_that_is_not_an_object_is_reported(self, script, db):
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert len(warnings) == 1
        assert "root" in warnings[0]

    def test_an_empty_root_is_not_a_complaint(self, script):
        assert script.repair_db({}) == ([], [])


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

    @pytest.mark.parametrize("poll_titles", [0, False, "", {}])
    def test_a_falsy_poll_titles_of_the_wrong_type_is_reported(
        self, script, poll_titles
    ):
        # The third `or` default, found in the same sweep: these read as an
        # empty list and were skipped in silence.
        db = {"x": {"lang_code": "x", "poll_titles": poll_titles}}
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert len(warnings) == 1
        assert warnings[0].startswith("x: ")
        assert db["x"]["poll_titles"] == poll_titles

    def test_a_missing_poll_titles_is_not_a_complaint(self, script):
        # The one default that is deliberate: an error entry has no allergens
        # and never had any.
        assert script.repair_db({"x": {"lang_code": "x"}}) == ([], [])

    def test_a_null_poll_titles_is_not_a_complaint(self, script):
        assert script.repair_db({"x": {"poll_titles": None}}) == ([], [])

    def test_tolerates_an_error_entry(self, script):
        db = {"tr": {"lang_code": "tr", "error": "request error: timeout"}}
        assert script.repair_db(db) == ([], [])

    @pytest.mark.parametrize(
        "poll",
        [
            # Truthy non-strings: these reached canonical_latin and raised.
            {"name": "Trávy", "latin": 5},
            {"name": 5, "latin": ""},
            {"name": ["Trávy"], "latin": "Poaceae"},
            # Falsy non-strings: these walked past the type check, because
            # `or ""` had already turned them into a valid-looking empty
            # string. The latin ones were then REWRITTEN from the display
            # name, which is the malformed entry being turned into a
            # well-formed record rather than reported.
            {"name": "Artemisia", "latin": 0},
            {"name": "Artemisia", "latin": False},
            {"name": "Artemisia", "latin": []},
            {"name": 0, "latin": "Poaceae"},
            {"name": False, "latin": ""},
        ],
    )
    def test_a_scalar_that_is_not_a_string_does_not_abort_the_run(self, script, poll):
        # canonical_latin strips, so a truthy non-string used to raise and
        # take every remaining language with it.
        db = {"x": {"poll_titles": [poll, {"name": "Breza", "latin": "Betula"}]}}
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert len(warnings) == 1
        assert warnings[0].startswith("x: ")
        # Reported AS a type error, not as some downstream consequence of a
        # value that was quietly defaulted before the check could see it.
        assert "not a string" in warnings[0]
        # The entry is left exactly as it was: a defect is reported, never
        # quietly rewritten into a well-formed record.
        assert db["x"]["poll_titles"][0] == poll

    @pytest.mark.parametrize(
        "db",
        [
            {"x": {"poll_titles": [{"name": None, "latin": "Nonexistentia"}]}},
            {"x": {"poll_titles": [{"name": "Trávy", "latin": None}]}},
            {"x": {"poll_titles": ["oops"]}},
            {"x": {"poll_titles": "oops"}},
            {"x": "oops"},
        ],
    )
    def test_reports_a_shape_it_did_not_expect_instead_of_raising(self, script, db):
        # --repair is the tool you reach for when the file is wrong, so a
        # wrong file has to come back as a warning naming the language.
        changes, warnings = script.repair_db(db)

        assert changes == []
        assert len(warnings) == 1
        assert warnings[0].startswith("x: ")


class TestTheFileAndTheRuntimeAgree:
    """The invariant the individual fixes keep failing to hold.

    An entry the generator records and the same entry as the API sends it
    must identify the SAME allergen, or nothing, in the same cases. When they
    disagree the file files an allergen under an identity the sensors refuse
    to read it as, and the restore path then attaches the wrong localized
    name to it during an outage.

    "Ambrosia hojas" is the input that has caused this three times, from
    three different directions: the setup path read it as ragweed, then a
    reverse English-name lookup would have, then the generator's genus
    fallback did. It is prose that begins with a genus, and neither side may
    treat that as an identity.
    """

    @staticmethod
    def _runtime_allergen(poll_title):
        """The allergen the sensors read this title as, or None."""
        return allergen_slug_for_item({"poll_title": poll_title})

    @staticmethod
    def _recorded_allergen(script, poll_title):
        """The allergen the map entry for this title identifies, or None."""
        poll_titles, _ = script.poll_titles_from_contamination(
            [{"poll_title": poll_title, "poll_id": 1}]
        )
        if not poll_titles:
            return None
        name_en = english_name_for_latin(poll_titles[0]["latin"])
        return slugify(name_en) if name_en else None

    @pytest.mark.parametrize(
        "poll_title",
        [
            "Ambrosia hojas",
            "Artemisia",
            "Ailanthus altissima",
            "Ambrosia artemisiifolia",
            "Ragweed (Ambrosia artemisiifolia)",
            "Ragweed (Ambrosia)",
            "Artemisia (Asteraceae)",
            "(Poaceae)",
            "Trávy (Poaceae)",
            "Ragweed (ambrózia)",
            "Nässlor (Nonexistentia)",
            "Något nytt",
            # Brackets with nothing in them: the API sent no latin name, so
            # both sides fall back to the display name. The runtime used to
            # read the empty brackets as a latin name it could not place and
            # resolve to nothing, while the file recorded Artemisia.
            "Artemisia ()",
        ],
    )
    def test_both_sides_resolve_the_same_input_the_same_way(self, script, poll_title):
        assert self._recorded_allergen(script, poll_title) == self._runtime_allergen(
            poll_title
        )

    def test_the_prose_case_resolves_to_nothing_on_both_sides(self, script):
        # Stated separately from the parametrize above, because "they agree"
        # would also be satisfied by both being wrong in the same way.
        assert self._runtime_allergen("Ambrosia hojas") is None
        assert self._recorded_allergen(script, "Ambrosia hojas") is None

    def test_a_display_name_that_is_a_latin_name_resolves_on_both_sides(self, script):
        assert self._runtime_allergen("Artemisia") == "mugwort"
        assert self._recorded_allergen(script, "Artemisia") == "mugwort"

    def test_empty_brackets_resolve_to_the_display_name_on_both_sides(self, script):
        assert self._runtime_allergen("Artemisia ()") == "mugwort"
        assert self._recorded_allergen(script, "Artemisia ()") == "mugwort"


class TestShippedLanguageMap:
    """The file itself, as shipped.

    The map may not carry an allergen the integration does not know. That is
    deliberate, and it is why these two fail rather than pass when the API
    adds one: the generator writes an unknown allergen through on purpose, so
    that it reaches a human. The fix when they go red is to add the allergen
    to LATIN_TO_ENGLISH_NAME in sensor.py, or its spelling to
    LATIN_NAME_ALIASES if that is what it turns out to be. It is never to
    relax the assertion, and never to delete the entry from the file.
    """

    def test_no_recorded_latin_name_is_a_known_bad_spelling(self, script):
        # The narrow half of the tripwire: whatever else the file holds, it
        # may not hold a spelling we have already established is not a latin
        # name, nor an entry with no latin name at all. This one stays true
        # even for an allergen the integration does not know yet.
        db = json.loads(LANGUAGE_MAP.read_text(encoding="utf-8"))
        bad = [
            (lang_code, entry["name"], entry["latin"])
            for lang_code, block in db.items()
            for entry in block.get("poll_titles", [])
            if not entry["latin"] or entry["latin"].lower() in script.LATIN_NAME_ALIASES
        ]
        assert bad == []

    def test_every_recorded_latin_name_is_recognized(self, script):
        db = json.loads(LANGUAGE_MAP.read_text(encoding="utf-8"))
        unrecognized = [
            (lang_code, entry["name"], entry["latin"])
            for lang_code, block in db.items()
            for entry in block.get("poll_titles", [])
            if not script.canonical_latin(entry["latin"])
        ]
        assert unrecognized == []

    def test_needs_no_repair(self, script):
        db = json.loads(LANGUAGE_MAP.read_text(encoding="utf-8"))
        changes, warnings = script.repair_db(db)
        assert (changes, warnings) == ([], [])

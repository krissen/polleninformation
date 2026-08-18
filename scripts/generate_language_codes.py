"""Generate custom_components/polleninformation/language_map.json.

Two modes, both run from the repository root:

    python scripts/generate_language_codes.py           # fetch missing languages
    python scripts/generate_language_codes.py --repair  # revalidate, offline

The fetch mode asks the API for one forecast per interface language and
records the localized allergen names it answers with. It needs API_KEY (from
the environment or from .env) and network access, and it only fetches
languages the file does not already have.

The repair mode needs neither. It revalidates every latin name already in the
file with the same rules the fetch mode applies to a fresh response, which is
what lets an entry recorded before those rules existed correct itself. Run it
after changing the validation, and review the diff.

Both modes take their authority from the allergen maps in sensor.py, so
this script imports the integration and therefore needs Home Assistant
installed (the test venv has it).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from custom_components.polleninformation.sensor import (
    LATIN_NAME_ALIASES,
    canonical_latin,
    canonical_latin_for_display_name,
)

# ================================
# CONFIGURATION
# ================================

LAT = 48.2081743
LON = 16.3738189
COUNTRY = "AT"
LANG_CODES = [
    "de",
    "en",
    "fi",
    "sv",
    "fr",
    "it",
    "lv",
    "lt",
    "pl",
    "pt",
    "ru",
    "sk",
    "es",
    "tr",
    "uk",
    "hu",
]
# Anchored to the script rather than to the working directory. Relative, it
# resolved against wherever the shell happened to be, so a run from any other
# directory found no file, read no languages, fetched all sixteen and wrote a
# new map there. A file that is merely absent is indistinguishable from an
# empty database, so no guard downstream can catch that.
DB_FILE = str(
    REPO_ROOT / "custom_components" / "polleninformation" / "language_map.json"
)
DELAY_SEC = 2  # Polite delay between requests (adjust if needed)
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; polleninfo-script/1.0)",
}


def load_db():
    """Load the existing language_map.json, or return empty dict.

    A file that is not JSON at all stops the run. The rule this follows is
    not "unreadable stops, readable continues", it is narrower: a run that
    would REWRITE the file stops, a run that cannot damage it continues. The
    fetch writes, so it exits on JSON it cannot parse and on a root that is
    not an object. The repair only ever writes what it has read, so it
    reports those same roots and leaves the file byte for byte as it was.

    Treating an unreadable file as an empty db would be the destructive
    reading: the fetch would refetch every language and write over whatever
    was in there.
    """
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise SystemExit(
                f"{DB_FILE} is not valid JSON ({e}). Fix or remove it; this "
                f"script will not overwrite a file it cannot read."
            ) from e


def save_db(db):
    """Save the language_map.json file (pretty-printed, UTF-8)."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        # The file is checked in, so it ends with a newline like every other
        # source file. Without this every save shows up as a diff on the last
        # line.
        f.write("\n")


def get_language_name(lang_code):
    """Return the language name in English for a given ISO code."""
    # Minimal mapping; extend as needed.
    names = {
        "de": "German",
        "en": "English",
        "fi": "Finnish",
        "sv": "Swedish",
        "fr": "French",
        "it": "Italian",
        "lv": "Latvian",
        "lt": "Lithuanian",
        "pl": "Polish",
        "pt": "Portuguese",
        "ru": "Russian",
        "sk": "Slovak",
        "es": "Spanish",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "hu": "Hungarian",
    }
    return names.get(lang_code, lang_code)


def split_poll_title(poll_title):
    """Split a poll_title into its display name and its bracketed latin name.

    This is the transcription step only: whatever the API put between the
    brackets comes back as the latin name, and a title without brackets comes
    back with none. resolve_latin decides what that is worth.

    Total over whatever it is handed: a title that is not a string reads as an
    empty one. The caller rejects such an entry before it gets here, since a
    title that cannot be read names no allergen, but the split itself does not
    raise on one.
    """
    poll_title = poll_title if isinstance(poll_title, str) else ""
    if "(" in poll_title and ")" in poll_title:
        name = poll_title.split("(", 1)[0].strip()
        latin = poll_title.split("(", 1)[1].split(")", 1)[0].strip()
    else:
        name = poll_title.strip()
        latin = ""
    return name, latin


def resolve_latin(name, latin):
    """Return the latin name to record for an entry, plus any warnings.

    The API does not always put a latin name between the brackets, and does
    not always use brackets at all, so a transcribed latin name is checked
    against the integration's own maps before it is trusted:

    1. a latin name LATIN_TO_ENGLISH_NAME knows is recorded under that map's
       own key, so "poaceae" and "Ambrosia artemisiifolia" are recorded as
       "Poaceae" and "Ambrosia";
    2. a spelling LATIN_NAME_ALIASES declares, such as the Slovak "ambrózia",
       is recorded as the latin name it stands for;
    3. the display name is read as a latin name only when the API sent none,
       which is the shape reported in issue #71, and only on an exact match,
       because prose that begins with a genus is not an identity;
    4. anything else is warned about and recorded exactly as the API sent it.

    An entry whose display name is blank is warned about too, and kept: a
    title like "(Poaceae)" identifies its allergen, so dropping it would be
    the mistake, but it leaves the file holding half a pairing.

    Rungs 1 to 3 all record a key of LATIN_TO_ENGLISH_NAME, never the string
    the API happened to send, because every consumer of this file matches a
    latin name exactly: an entry recorded as "Ambrosia artemisiifolia" is not
    found again by the restore path, which holds "Ambrosia". The name field
    already preserves the API's own wording.

    A latin name the API did send is otherwise authoritative even when nothing
    resolves it, exactly as it is for the sensors: "Artemisia (Asteraceae)" is
    the composite family, not mugwort, and reading its display name as a latin
    name would record it as a different allergen. Only a spelling declared in
    the alias table overrides what the API sent, so an unknown latin name is
    never guessed at, and dropping it is never an option either: that would
    hide a genuinely new allergen, which is the one case where this file has
    something to tell us.
    """
    if latin and (canonical := canonical_latin(latin)):
        # A title like "(Poaceae)" names the allergen but not in this
        # language, so the entry is kept and the missing half is reported: the
        # file's whole job is the pairing, and half of one is worth knowing
        # about even though it identifies its allergen perfectly well.
        blank_name_warning = (
            f"the API sent {canonical!r} with no display name; recording the "
            f"entry, but this language has no name for that allergen"
        )
        blank_name = [] if name else [blank_name_warning]
        if canonical == latin:
            return latin, blank_name
        if latin.strip().lower() in LATIN_NAME_ALIASES:
            warning = (
                f"{name!r}: the API sent {latin!r} where the latin name goes, "
                f"which is a known spelling of {canonical!r}; recording that"
            )
        else:
            warning = (
                f"{name!r}: the API spells the latin name {latin!r}; recording "
                f"it as {canonical!r}, the spelling every lookup matches on"
            )
        return canonical, blank_name + [warning]

    sent = f"latin name {latin!r}" if latin else "no latin name"

    if not latin and (canonical := canonical_latin_for_display_name(name)):
        # The display name is itself a latin name, so record it as one. The
        # lookup is exact, with no genus fallback: "Ambrosia hojas" is prose
        # that begins with a genus, and recording it as Ambrosia would file
        # the entry under an allergen the sensors refuse to read it as.
        warning = (
            f"{name!r}: the API sent {sent} and a display name that is one; "
            f"recording {canonical!r}"
        )
        return canonical, [warning]

    if latin:
        warning = (
            f"{name!r}: the API sent {sent}, which no map knows. Keeping it: "
            f"a latin name the API sent identifies the allergen even when "
            f"nothing resolves it. If this is a new allergen it needs adding "
            f"to LATIN_TO_ENGLISH_NAME in sensor.py, and a spelling that is "
            f"not a latin name at all to LATIN_NAME_ALIASES; please open an "
            f"issue."
        )
    else:
        warning = (
            f"{name!r}: the API sent {sent} and a display name no map knows. "
            f"Recording it as sent. If this is a new allergen it needs adding "
            f"to LATIN_TO_ENGLISH_NAME in sensor.py; please open an issue."
        )
    return latin, [warning]


def poll_titles_from_contamination(contamination):
    """Return the poll_titles entries for a contamination block, plus warnings.

    Every entry the API sends produces exactly one entry here, whether or not
    its allergen is recognized: an unknown latin name still names a real
    allergen, and dropping it would hide a new one.

    Two shapes are the exception, and they are the opposite case. An entry
    that is not an object, and an entry that identifies no allergen, name
    nothing at all. The second is the parsed test rather than a test on the
    raw title: a title is kept when it has a display name or a latin name,
    so "(Poaceae)" is kept for its latin name and "()" is not, any more than
    a missing title is. Recording those would not preserve information, it
    would manufacture a well-formed record out of nothing, and a block of
    them would then look like a language that has allergens. Both are warned
    about rather than passed over, and a block left empty by them is a
    response with no allergens, which language_entry_from_response records as
    an error so the language is fetched again.
    """
    poll_titles = []
    warnings = []
    if not isinstance(contamination, list):
        return poll_titles, [
            f"the API sent a contamination block that is not a list: {contamination!r}"
        ]
    for poll in contamination:
        if not isinstance(poll, dict):
            warnings.append(
                f"skipping a contamination entry that is not an object: {poll!r}"
            )
            continue
        name, latin = split_poll_title(poll.get("poll_title"))
        if not name and not latin:
            # The test is what the entry identifies, not whether its title is
            # readable. "()" and "( )" are non-blank titles with nothing in
            # either half, and they name an allergen exactly as little as a
            # missing title does.
            warnings.append(
                f"skipping a contamination entry that identifies no allergen: {poll!r}"
            )
            continue
        latin, entry_warnings = resolve_latin(name, latin)
        warnings.extend(entry_warnings)
        poll_titles.append(
            {"name": name, "latin": latin, "poll_id": poll.get("poll_id")}
        )
    return poll_titles, warnings


def needs_fetch(db, lang_code):
    """Whether a language still has to be fetched.

    An entry that records an error is retried, which is the only reason the
    error is written to the file at all: a language whose response could not
    be read has to come back on the next run rather than sit there forever.

    So is an entry that is incomplete. A response can be readable and still
    have lost an allergen to a malformed entry, and nothing else would ever
    revisit it: this skips a saved language, and --repair cannot invent an
    entry that was never recorded. Left alone it would be permanently missing
    one allergen with nothing to say so.
    """
    entry = db.get(lang_code)
    if not isinstance(entry, dict):
        return True
    return "error" in entry or bool(entry.get("incomplete"))


def unreadable_entry_warning(db, lang_code):
    """Warn about a language entry that will be refetched and overwritten.

    needs_fetch treats an entry it cannot read as one to fetch again, which
    is right: an entry that is not an object holds nothing worth keeping. But
    it is the one place in this script that destroys something, so it says
    so first rather than doing it quietly. An entry that is simply absent, or
    one that records an error, is the ordinary case and says nothing.
    """
    entry = db.get(lang_code)
    if entry is None or isinstance(entry, dict):
        return None
    return (
        f"the file holds {entry!r} for this language, which is not an entry "
        f"this can read; refetching and overwriting it"
    )


def entry_after_retry(previous, entry):
    """Return the entry to store, given what the file already held.

    A retry may improve an entry and may not impoverish it. An entry marked
    incomplete is fetched again, and that retry can fail or come back
    malformed; storing the error entry it produces would drop allergen names
    the file already had, which is the trade the incomplete marker exists to
    refuse. Eleven localized names beside a failure are worth more to a sensor
    than none, exactly as they were worth more than an error entry.

    So a failure keeps what was there, records that the retry failed, and
    leaves the language retryable. The stored message says the names are from
    an earlier fetch, because an entry carrying both names and a failure
    should not read as a clean partial.
    """
    if "error" not in entry:
        return entry
    if not isinstance(previous, dict) or not previous.get("poll_titles"):
        return entry

    kept = dict(previous)
    kept["incomplete"] = True
    kept["retry_error"] = (
        f"the last retry failed ({entry['error']}); the allergen names in this "
        f"entry are from an earlier fetch"
    )
    return kept


def language_entry_from_response(lang_code, data):
    """Return the db entry for one language's response, plus warnings.

    A response this cannot take a single allergen from is recorded as an
    error, whatever shape caused it: a top level that is not an object, no
    contamination block, a block that is not a list, an empty block, or a
    block of entries none of which could be read.

    An empty response and a malformed one are not distinguishable here, and
    for this file they do not need to be. Both leave a language with no
    allergen names, which is the one thing the file exists to hold, so both
    have to be fetched again rather than saved as a language that legitimately
    has none. Recording either as a success would be permanent: needs_fetch
    only retries an entry that carries an error or is marked incomplete.

    A response that lost SOME of its entries is marked incomplete and keeps
    the ones it had. The entry is worth keeping, because eleven names are
    worth more to a sensor than none, and it may not be treated as finished,
    because nothing else would ever come back for the twelfth: this file is
    only fetched for languages it lacks, and --repair cannot invent an entry
    that was never recorded.
    """
    warnings = []
    poll_titles = []
    dropped = 0
    if not isinstance(data, dict):
        error = (
            f"malformed response: the top level is {type(data).__name__}, not an object"
        )
    elif "contamination" not in data:
        error = "malformed response: no contamination block"
    else:
        contamination = data["contamination"]
        poll_titles, warnings = poll_titles_from_contamination(contamination)
        error = "the response carries no allergens" if not poll_titles else None
        if isinstance(contamination, list):
            dropped = len(contamination) - len(poll_titles)

    if error:
        return {"error": error, "lang_code": lang_code}, warnings

    entry = {
        "lang_code": lang_code,
        "lang": get_language_name(lang_code),
        "poll_titles": poll_titles,
    }
    if dropped:
        entry["incomplete"] = True
        incomplete_warning = (
            f"{dropped} entry(ies) could not be read, so this language is "
            f"recorded as incomplete and will be fetched again"
        )
        warnings = [*warnings, incomplete_warning]
    return entry, warnings


def repair_db(db):
    """Revalidate every latin name already in the db, in place.

    Returns (changes, warnings), where a change is one corrected latin name.
    Entries are only ever rewritten, never removed: an allergen no map knows
    keeps what the API sent and is warned about again.

    Total over whatever the file holds, from the root down. This is the tool
    you reach for when the file is wrong, so a shape it did not expect is
    reported, with the language it sits in where there is one, rather than
    raised as a traceback that names neither. Nothing is rewritten on the way:
    a file this cannot read is left exactly as it is.
    """
    changes = []
    warnings = []
    if not isinstance(db, dict):
        warning = (
            f"the file does not hold an object at its root, but a "
            f"{type(db).__name__}; nothing to repair"
        )
        return changes, [warning]
    for lang_code, entry in db.items():
        if not isinstance(entry, dict):
            warnings.append(f"{lang_code}: not an object, skipping: {entry!r}")
            continue
        # Every field below is read raw and type-checked before anything is
        # defaulted. Defaulting first, with `or`, would convert a falsy value
        # of the wrong type into a valid-looking one and walk it past the
        # check: a latin of 0 would read as absent, the display name would
        # then be resolved in its place, and the malformed entry would be
        # rewritten instead of reported. Only a missing key or an explicit
        # null is defaulted, and that is a decision rather than a side effect.
        poll_titles = entry.get("poll_titles")
        if poll_titles is None:
            poll_titles = []
        if not isinstance(poll_titles, list):
            warnings.append(
                f"{lang_code}: poll_titles is not a list, skipping: {poll_titles!r}"
            )
            continue
        for poll in poll_titles:
            if not isinstance(poll, dict):
                warnings.append(
                    f"{lang_code}: entry is not an object, skipping: {poll!r}"
                )
                continue
            name = poll.get("name")
            latin = poll.get("latin")
            if name is None:
                name = ""
            if latin is None:
                latin = ""
            if not isinstance(name, str) or not isinstance(latin, str):
                warnings.append(
                    f"{lang_code}: name or latin is not a string, skipping: {poll!r}"
                )
                continue
            resolved, entry_warnings = resolve_latin(name, latin)
            warnings.extend(f"{lang_code}: {w}" for w in entry_warnings)
            if resolved != latin:
                poll["latin"] = resolved
                changes.append(f"{lang_code}: {name!r}: {latin!r} -> {resolved!r}")
    return changes, warnings


def run_repair():
    """Revalidate the whole db offline and save it if anything changed.

    The only thing decided here is the message for a database that is empty
    or absent. Everything else goes to repair_db unexamined, because an entry
    point that judges the data before the validator sees it can silently
    exclude the very shapes the validator exists to report: `if not db` sent
    every falsy root, a file holding [] or "" or 0 or false or null, down the
    "nothing to repair" path, which is the one answer that was certainly
    wrong.
    """
    db = load_db()
    if isinstance(db, dict) and not db:
        print(f"No languages in {DB_FILE} to repair.")
        return

    changes, warnings = repair_db(db)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for change in changes:
        print(f"Repaired {change}")

    if changes:
        save_db(db)
        print(f"Done. {len(changes)} latin name(s) repaired in {DB_FILE}")
    else:
        print(f"Done. Nothing to repair in {DB_FILE}")


def run_fetch():
    """Fetch every language missing from the db and record its allergen names."""
    import requests
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))
    api_key = os.environ["API_KEY"]

    db = load_db()
    if not isinstance(db, dict):
        raise SystemExit(
            f"{DB_FILE} does not hold an object at its root, but a "
            f"{type(db).__name__}. Fix or remove it; this script will not "
            f"overwrite a file it cannot read."
        )
    base_url = "https://www.polleninformation.at/api/forecast/public"

    for lang_code in LANG_CODES:
        if not needs_fetch(db, lang_code):
            print(f"{lang_code}: Already in db, skipping.")
            continue

        if warning := unreadable_entry_warning(db, lang_code):
            print(f"{lang_code}: WARNING: {warning}")

        params = {
            "country": COUNTRY,
            "lang": lang_code,
            "latitude": LAT,
            "longitude": LON,
            "apikey": api_key,
        }
        previous = db.get(lang_code)
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"{lang_code}: [request error: {e}]")
            db[lang_code] = entry_after_retry(
                previous, {"error": str(e), "lang_code": lang_code}
            )
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        # Parse forecast block for title/allergens. Total over anything the
        # API can send, so there is no parse error to catch: an entry that
        # cannot be read costs its own line and not the whole language, and a
        # bug here surfaces as a traceback rather than as an error entry
        # persisted in a file that is never refetched.
        entry, warnings = language_entry_from_response(lang_code, data)

        for warning in warnings:
            print(f"{lang_code}: WARNING: {warning}")

        entry = entry_after_retry(previous, entry)
        db[lang_code] = entry
        if "error" in entry:
            print(f"{lang_code}: [{entry['error']}]")
        elif "retry_error" in entry:
            print(f"{lang_code}: [{entry['retry_error']}]")
        else:
            print(f"{lang_code}: OK, {len(entry['poll_titles'])} allergens")
        save_db(db)
        time.sleep(DELAY_SEC)

    print(f"Done. See {DB_FILE}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "revalidate the latin names already in the file instead of "
            "fetching; needs no API key and no network"
        ),
    )
    args = parser.parse_args(argv)

    if args.repair:
        run_repair()
    else:
        run_fetch()


if __name__ == "__main__":
    main()

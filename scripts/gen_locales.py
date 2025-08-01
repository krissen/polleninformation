#!/usr/bin/env python3
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Anpassa vägen hit till rätt path i ditt repo!
TRANSLATIONS_DIR = (
    Path(__file__).parent.parent / "custom_components/polleninformation/translations"
)

MASTER = "en.json"

PY_FILES_TO_SCAN = [
    Path(__file__).parent.parent / "custom_components/polleninformation/config_flow.py",
    Path(__file__).parent.parent / "custom_components/polleninformation/sensor.py",
    Path(__file__).parent.parent
    / "custom_components/polleninformation/options_flow.py",
    Path(__file__).parent.parent / "custom_components/polleninformation/api.py",
]

ICON_OK = "✅"
ICON_WARN = "⚠️"
ICON_ADD = "➕"
ICON_DEL = "❌"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def flatten(d, parent_key="", sep="."):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten(v, new_key, sep=sep))
        else:
            items.append((new_key, v))
    return items


def unflatten(flat, sep="."):
    result = {}
    for key, value in flat.items():
        keys = key.split(sep)
        d = result
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
    return result


def find_missing_and_redundant():
    files = sorted([f for f in TRANSLATIONS_DIR.glob("*.json")])
    master_path = TRANSLATIONS_DIR / MASTER
    if not master_path.exists():
        print(f"{ICON_WARN} Master file {master_path} not found.")
        sys.exit(1)
    master = load_json(master_path)
    master_flat = dict(flatten(master))
    missing_per_lang = defaultdict(list)
    redundant_per_lang = defaultdict(list)
    for file in files:
        if file.name == MASTER:
            continue
        data = load_json(file)
        data_flat = dict(flatten(data))
        for key in master_flat:
            if key not in data_flat:
                missing_per_lang[file.stem].append(key)
        for key in data_flat:
            if key not in master_flat:
                redundant_per_lang[file.stem].append(key)
    return master, master_flat, missing_per_lang, redundant_per_lang


def find_used_keys_in_py():
    used_keys = set()
    _pattern = re.compile(r'["\']([a-zA-Z0-9_.-]+)["\']')
    for py_file in PY_FILES_TO_SCAN:
        if py_file.exists():
            content = py_file.read_text(encoding="utf-8")
            # Hämta alla översättningsnycklar (förenklat; använd vid behov en bättre regex)
            # Exempel: hass.config_entries.async_show_form(..., errors={"no_sensors_for_country": ...})
            found = re.findall(r'["\']([a-zA-Z0-9_.-]+)["\']', content)
            for match in found:
                # Vi antar att endast nycklar som innehåller punkt är translation keys
                if "." in match:
                    used_keys.add(match)
    return used_keys


def scan_missing():
    master, master_flat, missing_per_lang, redundant_per_lang = (
        find_missing_and_redundant()
    )

    # Kontroll mot keys i py-filer (om du skulle använda dem)
    used_keys = find_used_keys_in_py()
    missing_in_master = sorted(k for k in used_keys if k not in master_flat)
    if missing_in_master:
        print(f"{ICON_WARN} Nycklar som används i .py men saknas i {MASTER}:")
        for key in missing_in_master:
            print(f"  {ICON_WARN} '{key}' används i .py-filer men finns ej i {MASTER}")

    # Rapportera saknade per språk
    if not missing_per_lang:
        print(f"{ICON_OK} Alla språkfiler har alla nycklar från master.")
    else:
        print(f"{ICON_ADD} Saknade nycklar:")
        for key in master_flat:
            saknas_i = [lang for lang, keys in missing_per_lang.items() if key in keys]
            if saknas_i:
                print(
                    f"  {ICON_WARN} '{key}' (\"{master_flat[key]}\" i {MASTER}) saknas i:\n      {', '.join(saknas_i)}"
                )
    # Rapportera redundanta (överflödiga)
    all_redundant_keys = defaultdict(list)
    for lang, keys in redundant_per_lang.items():
        for key in keys:
            all_redundant_keys[key].append(lang)
    if all_redundant_keys:
        print(f"\n{ICON_DEL} Överflödiga nycklar (finns ej i {MASTER}):")
        for key, langs in all_redundant_keys.items():
            print(f"  {ICON_DEL} '{key}' finns i: {', '.join(langs)}")


def gen_translation_json():
    master, master_flat, missing_per_lang, _ = find_missing_and_redundant()
    output = defaultdict(dict)
    for lang, keys in missing_per_lang.items():
        for key in keys:
            output[lang][key] = master_flat[key]
    if output:
        output_text = (
            "\n# Översätt nedan till respektive språk:\n\n"
            + json.dumps(output, ensure_ascii=False, indent=2)
            + "\n\n---\n"
            + "Spara översättningarna till fil och kör:\n\n"
            + f"  python3 {Path(__file__).name} update path/till/oversattning.json\n"
        )
        print(output_text)
        try:
            subprocess.run("pbcopy", input=output_text, text=True, check=True)
            print(f"{ICON_OK} JSON + instruktion kopierad till clipboard (pbcopy)")
        except Exception as e:
            print(f"{ICON_WARN} Kunde inte kopiera till clipboard: {e}")
    else:
        print(f"{ICON_OK} Alla språkfiler har redan alla nycklar från master.")


def update_with_translation(json_path, force=False):
    with open(json_path, encoding="utf-8") as f:
        translation = json.load(f)
    for lang, keys in translation.items():
        loc_file = TRANSLATIONS_DIR / (lang + ".json")
        if not loc_file.exists():
            print(f"{ICON_WARN} Språkfil saknas: {loc_file}")
            continue
        data = load_json(loc_file)
        data_flat = dict(flatten(data))
        count_new = 0
        count_updated = 0
        for key, val in keys.items():
            if key not in data_flat:
                data_flat[key] = val
                count_new += 1
            elif force:
                if data_flat[key] != val:
                    data_flat[key] = val
                    count_updated += 1
        if count_new or (force and count_updated):
            # Spara som nested igen
            save_json(loc_file, unflatten(data_flat))
            msg = f"{ICON_OK} {lang}.json: {count_new} nya nycklar inlagda"
            if force and count_updated:
                msg += f", {count_updated} uppdaterade (force=True)"
            print(msg)
        else:
            msg = f"{ICON_OK} {lang}.json: inga nya nycklar inlagda"
            if force:
                msg += " (force=True)"
            print(msg)


def delete_redundant():
    _, master_flat, _, redundant_per_lang = find_missing_and_redundant()
    files = sorted([f for f in TRANSLATIONS_DIR.glob("*.json")])
    total_removed = 0
    for file in files:
        if file.name == MASTER:
            continue
        data = load_json(file)
        data_flat = dict(flatten(data))
        redundant = [key for key in data_flat if key not in master_flat]
        if redundant:
            for key in redundant:
                del data_flat[key]
            save_json(file, unflatten(data_flat))
            print(
                f"{ICON_DEL} {file.name}: tog bort {len(redundant)} överflödiga nycklar: {', '.join(redundant)}"
            )
            total_removed += len(redundant)
        else:
            print(f"{ICON_OK} {file.name}: inga överflödiga nycklar.")
    if total_removed == 0:
        print(f"{ICON_OK} Inga överflödiga nycklar att ta bort.")
    else:
        print(f"{ICON_DEL} Totalt borttagna nycklar: {total_removed}")


if __name__ == "__main__":
    cmds = []
    update_file = None
    force = False
    args = sys.argv[1:]

    for i, arg in enumerate(args):
        arg_l = arg.lower()
        if arg_l in ("scan", "gen", "update", "clean"):
            cmds.append(arg_l)
        elif arg_l in ("--force", "-f"):
            force = True
        elif arg.endswith(".json"):
            update_file = arg

    if not cmds:
        cmds = ["scan"]

    for cmd in cmds:
        if cmd == "scan":
            scan_missing()
        elif cmd == "gen":
            gen_translation_json()
        elif cmd == "update":
            if update_file:
                update_with_translation(update_file, force=force)
            else:
                print(f"{ICON_WARN} Ingen översättningsfil angiven till update.")
        elif cmd == "clean":
            delete_redundant()
        else:
            print(f"{ICON_WARN} Okänt kommando: {cmd}")

    if not cmds or all(cmd not in ("scan", "gen", "update", "clean") for cmd in cmds):
        print(
            "\nUsage:\n"
            f"  python3 {Path(__file__).name} scan\n"
            f"  python3 {Path(__file__).name} gen\n"
            f"  python3 {Path(__file__).name} update oversattning.json [--force|-f]\n"
            f"  python3 {Path(__file__).name} clean\n"
            "\nDu kan kombinera flera kommandon i valfri ordning, t.ex.:\n"
            f"  python3 {Path(__file__).name} update oversattning.json clean\n"
        )

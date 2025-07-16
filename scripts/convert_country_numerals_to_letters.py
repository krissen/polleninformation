import json

with open("language_map.json", encoding="utf-8") as f:
    data = json.load(f)

# Only keep entries that are dicts and have "lang_code"
new_data = {
    v["lang_code"]: v for v in data.values() if isinstance(v, dict) and "lang_code" in v
}

with open("language_map.json", "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)

"""Tests for utility functions (pure, no HA dependency)."""


from custom_components.polleninformation.utils import (
    extract_place_slug,
    find_best_lang_code_for_locale_sync,
    get_allergen_info_by_latin,
    get_country_code_map,
    get_country_options_sync,
    get_language_options_sync,
    normalize,
    slugify,
    split_location,
)


class TestNormalize:
    def test_basic(self):
        assert normalize("Stockholm") == "stockholm"

    def test_spaces(self):
        assert normalize("New York City") == "new_york_city"

    def test_swedish_chars(self):
        result = normalize("Göteborg")
        assert "o" in result
        assert "ö" not in result

    def test_parentheses(self):
        assert normalize("Hamburg (53.5, 10.0)") == "hamburg_53_5_10_0"

    def test_double_underscores(self):
        result = normalize("a  --  b")
        assert "__" not in result

    def test_leading_trailing(self):
        result = normalize("  hello  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_empty(self):
        assert normalize("") == ""


class TestSlugify:
    def test_basic(self):
        assert slugify("Birch") == "birch"

    def test_strips_parenthetical(self):
        assert slugify("Erle (Alnus)") == "erle"

    def test_dots(self):
        result = slugify("St. Pölten")
        assert "polten" in result
        assert result.startswith("st")

    def test_swedish_chars(self):
        result = slugify("Björk")
        assert "ö" not in result

    def test_no_trailing_underscore(self):
        result = slugify("test ")
        assert not result.endswith("_")


class TestExtractPlaceSlug:
    def test_with_zip(self):
        assert extract_place_slug("9020 Klagenfurt") == "klagenfurt"

    def test_without_zip(self):
        assert extract_place_slug("Stockholm") == "stockholm"

    def test_complex(self):
        result = extract_place_slug("1010 Wien Innere Stadt")
        assert result == "wien_innere_stadt"


class TestSplitLocation:
    def test_with_zip(self):
        z, name = split_location("9020 Klagenfurt")
        assert z == "9020"
        assert name == "Klagenfurt"

    def test_without_zip(self):
        z, name = split_location("Stockholm")
        assert z == ""
        assert name == "Stockholm"

    def test_whitespace(self):
        z, name = split_location("  Hamburg  ")
        assert name == "Hamburg"


class TestGetAllergenInfoByLatin:
    def test_found(self):
        block = {
            "poll_titles": [
                {"name": "Alder", "latin": "Alnus"},
                {"name": "Birch", "latin": "Betula"},
            ]
        }
        result = get_allergen_info_by_latin("Alnus", block)
        assert result is not None
        assert result["name"] == "Alder"

    def test_not_found(self):
        block = {"poll_titles": [{"name": "Alder", "latin": "Alnus"}]}
        assert get_allergen_info_by_latin("Unknown", block) is None

    def test_empty_block(self):
        assert get_allergen_info_by_latin("Alnus", {}) is None


class TestFindBestLangCode:
    def test_exact_match(self):
        assert find_best_lang_code_for_locale_sync("sv") == "sv"

    def test_prefix_match(self):
        assert find_best_lang_code_for_locale_sync("sv-SE") == "sv"

    def test_fallback_to_en(self):
        assert find_best_lang_code_for_locale_sync("xx") == "en"

    def test_case_insensitive(self):
        assert find_best_lang_code_for_locale_sync("SV") == "sv"


class TestGetCountryCodeMap:
    def test_returns_dict(self):
        result = get_country_code_map()
        assert isinstance(result, dict)
        assert result["Sweden"] == "SE"
        assert result["Austria"] == "AT"


class TestGetCountryOptionsSync:
    def test_all_supported_countries(self):
        from custom_components.polleninformation.const import SUPPORTED_COUNTRIES

        result = get_country_options_sync()
        for code in SUPPORTED_COUNTRIES:
            assert code in result


class TestGetLanguageOptionsSync:
    def test_all_supported_languages(self):
        from custom_components.polleninformation.const import SUPPORTED_LANGUAGES

        result = get_language_options_sync()
        for code in SUPPORTED_LANGUAGES:
            assert code in result

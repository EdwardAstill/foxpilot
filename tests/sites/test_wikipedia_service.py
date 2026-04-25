"""Unit tests for foxpilot.sites.wikipedia_service pure helpers."""

from __future__ import annotations

import unittest

from foxpilot.sites.wikipedia_service import (
    article_url,
    format_links,
    format_references,
    format_search_results,
    format_summary,
    is_wikipedia_url,
    lang_from_url,
    normalize_title,
    random_url,
    references_url,
    search_url,
    title_from_url,
)


class NormalizeTitleTests(unittest.TestCase):
    def test_replaces_spaces_with_underscores(self):
        self.assertEqual(normalize_title("Ada Lovelace"), "Ada_Lovelace")

    def test_strips_and_collapses_whitespace(self):
        self.assertEqual(normalize_title("  Ada   Lovelace  "), "Ada_Lovelace")

    def test_capitalises_first_character_only(self):
        self.assertEqual(normalize_title("ada lovelace"), "Ada_lovelace")
        # Already-uppercase later chars must stay uppercase.
        self.assertEqual(normalize_title("iPhone"), "IPhone")

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(normalize_title(""), "")
        self.assertEqual(normalize_title("   "), "")


class IsWikipediaUrlTests(unittest.TestCase):
    def test_recognises_english_subdomain(self):
        self.assertTrue(is_wikipedia_url("https://en.wikipedia.org/wiki/Ada_Lovelace"))

    def test_recognises_other_languages(self):
        self.assertTrue(is_wikipedia_url("https://fr.wikipedia.org/wiki/Ada_Lovelace"))
        self.assertTrue(is_wikipedia_url("https://ja.wikipedia.org/wiki/Tokyo"))

    def test_recognises_mobile_subdomain(self):
        self.assertTrue(is_wikipedia_url("https://en.m.wikipedia.org/wiki/Ada_Lovelace"))

    def test_rejects_other_hosts(self):
        self.assertFalse(is_wikipedia_url("https://example.com/wiki/Ada_Lovelace"))
        self.assertFalse(is_wikipedia_url("https://wikipedia.org/wiki/Ada_Lovelace"))
        self.assertFalse(is_wikipedia_url("Ada Lovelace"))


class LangFromUrlTests(unittest.TestCase):
    def test_extracts_lang_from_url(self):
        self.assertEqual(
            lang_from_url("https://fr.wikipedia.org/wiki/Tour_Eiffel"),
            "fr",
        )
        self.assertEqual(
            lang_from_url("https://en.wikipedia.org/wiki/Ada_Lovelace"),
            "en",
        )

    def test_returns_none_for_non_wikipedia(self):
        self.assertIsNone(lang_from_url("https://example.com/foo"))


class ArticleUrlTests(unittest.TestCase):
    def test_default_lang_is_en(self):
        self.assertEqual(
            article_url("Ada Lovelace"),
            "https://en.wikipedia.org/wiki/Ada_Lovelace",
        )

    def test_other_language_subdomain(self):
        self.assertEqual(
            article_url("Tour Eiffel", lang="fr"),
            "https://fr.wikipedia.org/wiki/Tour_Eiffel",
        )
        self.assertEqual(
            article_url("Tokyo", lang="ja"),
            "https://ja.wikipedia.org/wiki/Tokyo",
        )

    def test_passthrough_for_existing_wikipedia_url(self):
        self.assertEqual(
            article_url("https://en.wikipedia.org/wiki/Ada_Lovelace"),
            "https://en.wikipedia.org/wiki/Ada_Lovelace",
        )

    def test_passthrough_preserves_lang_subdomain(self):
        # Even if the user passes --lang en, an explicit fr URL must win.
        self.assertEqual(
            article_url("https://fr.wikipedia.org/wiki/Tour_Eiffel", lang="en"),
            "https://fr.wikipedia.org/wiki/Tour_Eiffel",
        )

    def test_titles_with_punctuation_keep_safe_chars(self):
        # Parentheses and underscores are common in disambiguated article
        # titles and must round-trip without percent-encoding.
        self.assertEqual(
            article_url("Mercury (planet)"),
            "https://en.wikipedia.org/wiki/Mercury_(planet)",
        )

    def test_empty_title_raises(self):
        with self.assertRaises(ValueError):
            article_url("")
        with self.assertRaises(ValueError):
            article_url("   ")

    def test_invalid_lang_raises(self):
        with self.assertRaises(ValueError):
            article_url("Ada Lovelace", lang="english")
        with self.assertRaises(ValueError):
            article_url("Ada Lovelace", lang="123")

    def test_compound_lang_code_accepted(self):
        # Wikipedia hosts sub-language variants such as zh-yue.
        self.assertEqual(
            article_url("Hello", lang="zh-yue"),
            "https://zh-yue.wikipedia.org/wiki/Hello",
        )


class SearchUrlTests(unittest.TestCase):
    def test_search_url_default_lang(self):
        self.assertEqual(
            search_url("rust programming language"),
            "https://en.wikipedia.org/w/index.php?search=rust+programming+language",
        )

    def test_search_url_per_language(self):
        self.assertEqual(
            search_url("Tour Eiffel", lang="fr"),
            "https://fr.wikipedia.org/w/index.php?search=Tour+Eiffel",
        )

    def test_search_url_encodes_special_chars(self):
        url = search_url("a&b c")
        self.assertIn("a%26b+c", url)
        self.assertTrue(url.startswith("https://en.wikipedia.org/w/index.php?"))


class RandomUrlTests(unittest.TestCase):
    def test_random_url_default_lang(self):
        self.assertEqual(
            random_url(),
            "https://en.wikipedia.org/wiki/Special:Random",
        )

    def test_random_url_per_language(self):
        self.assertEqual(
            random_url(lang="de"),
            "https://de.wikipedia.org/wiki/Special:Random",
        )


class ReferencesUrlTests(unittest.TestCase):
    def test_appends_references_fragment(self):
        self.assertEqual(
            references_url("Ada Lovelace"),
            "https://en.wikipedia.org/wiki/Ada_Lovelace#References",
        )


class TitleFromUrlTests(unittest.TestCase):
    def test_extracts_title_from_article_url(self):
        self.assertEqual(
            title_from_url("https://en.wikipedia.org/wiki/Ada_Lovelace"),
            "Ada_Lovelace",
        )

    def test_decodes_percent_encoding(self):
        self.assertEqual(
            title_from_url("https://en.wikipedia.org/wiki/Mercury_%28planet%29"),
            "Mercury_(planet)",
        )

    def test_returns_empty_when_no_wiki_segment(self):
        self.assertEqual(title_from_url("https://en.wikipedia.org/"), "")


class FormattersTests(unittest.TestCase):
    def test_format_search_results_handles_empty(self):
        self.assertEqual(format_search_results([]), "No Wikipedia results found.")

    def test_format_search_results_renders_entries(self):
        out = format_search_results(
            [
                {
                    "title": "Ada Lovelace",
                    "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
                    "snippet": "Mathematician and writer.",
                }
            ]
        )
        self.assertIn("[1] Ada Lovelace", out)
        self.assertIn("https://en.wikipedia.org/wiki/Ada_Lovelace", out)
        self.assertIn("Mathematician and writer.", out)

    def test_format_summary_includes_infobox_keys(self):
        out = format_summary(
            {
                "title": "Ada Lovelace",
                "url": "https://en.wikipedia.org/wiki/Ada_Lovelace",
                "lang": "en",
                "lead": "Augusta Ada King ...",
                "infobox": {"Born": "1815", "Died": "1852"},
            }
        )
        self.assertIn("title: Ada Lovelace", out)
        self.assertIn("lang: en", out)
        self.assertIn("Born: 1815", out)
        self.assertIn("Died: 1852", out)
        self.assertIn("Augusta Ada King ...", out)

    def test_format_summary_handles_empty(self):
        self.assertEqual(format_summary({}), "No Wikipedia summary found.")

    def test_format_links_handles_empty_and_renders(self):
        self.assertEqual(format_links([]), "No internal links found.")
        out = format_links(
            [{"title": "Charles Babbage", "url": "https://en.wikipedia.org/wiki/Charles_Babbage"}]
        )
        self.assertIn("[1] Charles Babbage", out)
        self.assertIn("https://en.wikipedia.org/wiki/Charles_Babbage", out)

    def test_format_references_handles_empty_and_renders(self):
        self.assertEqual(format_references([]), "No references found.")
        out = format_references(
            [{"text": "Smith, J. (1999).", "urls": ["https://example.org/a"]}]
        )
        self.assertIn("[1] Smith, J. (1999).", out)
        self.assertIn("https://example.org/a", out)


if __name__ == "__main__":
    unittest.main()

import json
import unittest

from typer.testing import CliRunner

from foxpilot.sites import page as page_cli
from foxpilot.sites.page_service import (
    extract_links,
    format_buttons,
    format_forms,
    format_inputs,
    format_landmarks,
    format_links,
    format_metadata,
    format_outline,
)


class FakeBrowser:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.title = "Example Page"
        self.current_url = "https://example.com/about"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_script(self, script, *args):
        self.calls.append((script, args))
        return self.response


class PageSiteTests(unittest.TestCase):
    def test_outline_formatter_shows_heading_levels(self):
        output = format_outline(
            [
                {"level": 1, "text": "Welcome", "id": "welcome"},
                {"level": 2, "text": "Details", "selector": "main h2:nth-of-type(1)"},
            ]
        )

        self.assertIn("H1 Welcome #welcome", output)
        self.assertIn("  H2 Details main h2:nth-of-type(1)", output)

    def test_links_formatter_marks_internal_and_external_links(self):
        output = format_links(
            [
                {"text": "Home", "href": "https://example.com/", "is_internal": True},
                {"text": "Docs", "href": "https://docs.example.net/", "is_internal": False},
            ]
        )

        self.assertIn("[internal] Home", output)
        self.assertIn("https://example.com/", output)
        self.assertIn("[external] Docs", output)

    def test_links_extraction_passes_filter_and_limit_to_browser_script(self):
        browser = FakeBrowser(
            [
                {"text": "Docs", "href": "https://docs.example.net/", "is_internal": False},
            ]
        )

        links = extract_links(browser, link_filter="external", limit=3)

        self.assertEqual(links[0]["text"], "Docs")
        self.assertEqual(browser.calls[0][1], ("external", 3))

    def test_form_input_button_landmark_formatters_are_stable(self):
        self.assertIn(
            "GET /search",
            format_forms(
                [
                    {
                        "method": "GET",
                        "action": "/search",
                        "label": "Search",
                        "fields": [{"label": "Query", "type": "search", "name": "q"}],
                    }
                ]
            ),
        )
        self.assertIn(
            "email Email address",
            format_inputs(
                [
                    {
                        "type": "email",
                        "label": "Email address",
                        "name": "email",
                        "required": True,
                    }
                ]
            ),
        )
        self.assertIn(
            "submit Save",
            format_buttons([{"type": "submit", "text": "Save", "disabled": False}]),
        )
        self.assertIn(
            "navigation Primary",
            format_landmarks([{"role": "navigation", "label": "Primary", "tag": "nav"}]),
        )

    def test_metadata_formatter_includes_core_and_social_metadata(self):
        output = format_metadata(
            {
                "title": "Example Page",
                "url": "https://example.com/about",
                "description": "An example page.",
                "canonical": "https://example.com/about",
                "open_graph": {"og:title": "Open Graph Title"},
            }
        )

        self.assertIn("title: Example Page", output)
        self.assertIn("description: An example page.", output)
        self.assertIn("og:title: Open Graph Title", output)

    def test_page_app_registers_expected_commands(self):
        source = page_cli.app.registered_commands
        names = {command.name for command in source}

        self.assertEqual(
            {"help", "outline", "links", "forms", "buttons", "inputs", "metadata", "landmarks", "understand"},
            names,
        )

    def test_outline_command_emits_json_from_injected_browser(self):
        page_cli.set_browser_factory(
            lambda: FakeBrowser([{"level": 1, "text": "Welcome", "id": "welcome"}])
        )
        result = CliRunner().invoke(page_cli.app, ["outline", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)[0]["text"], "Welcome")


if __name__ == "__main__":
    unittest.main()

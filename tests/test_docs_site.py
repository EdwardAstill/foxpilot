import inspect
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from typer.testing import CliRunner

from foxpilot.sites.docs import app
from foxpilot.sites.docs_service import (
    DOCS_SITE_REGISTRY,
    detect_docs_site,
    docs_search_url,
    format_examples,
    format_links,
    format_page_read,
    format_search_results,
    normalize_docs_target,
    resolve_docs_site,
)


class DocsSiteTests(unittest.TestCase):
    def test_registry_includes_known_docs_sites(self):
        self.assertEqual(
            set(DOCS_SITE_REGISTRY),
            {"python", "mdn", "react", "typescript", "typer", "selenium"},
        )
        self.assertEqual(DOCS_SITE_REGISTRY["python"].base_url, "https://docs.python.org/3/")
        self.assertEqual(DOCS_SITE_REGISTRY["mdn"].base_url, "https://developer.mozilla.org/en-US/docs/Web")
        self.assertEqual(DOCS_SITE_REGISTRY["react"].base_url, "https://react.dev/reference/react")
        self.assertEqual(DOCS_SITE_REGISTRY["typescript"].base_url, "https://www.typescriptlang.org/docs/")
        self.assertEqual(DOCS_SITE_REGISTRY["typer"].base_url, "https://typer.tiangolo.com/")
        self.assertEqual(DOCS_SITE_REGISTRY["selenium"].base_url, "https://www.selenium.dev/documentation/")

    def test_search_url_scopes_known_site_queries(self):
        url = docs_search_url("pathlib Path glob", site_key="python")
        parsed = urlparse(url)
        query = parse_qs(parsed.query)["q"][0]

        self.assertEqual(parsed.netloc, "duckduckgo.com")
        self.assertIn("pathlib Path glob", query)
        self.assertIn("site:docs.python.org/3", query)

    def test_search_url_scopes_all_registry_sites_when_site_omitted(self):
        query = parse_qs(urlparse(docs_search_url("query selector")).query)["q"][0]

        self.assertIn("query selector", query)
        self.assertIn("site:docs.python.org/3", query)
        self.assertIn("site:developer.mozilla.org/en-US/docs/Web", query)
        self.assertIn("site:react.dev", query)

    def test_unknown_site_is_clear_error(self):
        with self.assertRaisesRegex(ValueError, "unknown docs site"):
            resolve_docs_site("rust")

    def test_normalize_docs_target_handles_urls_paths_and_queries(self):
        self.assertEqual(
            normalize_docs_target("developer.mozilla.org/en-US/docs/Web/API", None),
            "https://developer.mozilla.org/en-US/docs/Web/API",
        )
        self.assertEqual(
            normalize_docs_target("/3/library/pathlib.html", "python"),
            "https://docs.python.org/3/library/pathlib.html",
        )
        self.assertEqual(
            normalize_docs_target("/library/pathlib.html", "python"),
            "https://docs.python.org/3/library/pathlib.html",
        )
        self.assertEqual(
            normalize_docs_target("/API/Document/querySelector", "mdn"),
            "https://developer.mozilla.org/en-US/docs/Web/API/Document/querySelector",
        )
        self.assertIn(
            "site:react.dev",
            parse_qs(urlparse(normalize_docs_target("useEffect cleanup", "react")).query)["q"][0],
        )
        self.assertIn(
            "pathlib.Path glob",
            parse_qs(urlparse(normalize_docs_target("pathlib.Path glob", "python")).query)["q"][0],
        )

    def test_detect_docs_site_handles_www_hosts_and_path_scopes(self):
        self.assertEqual(detect_docs_site("https://www.typescriptlang.org/docs/handbook/intro.html"), "typescript")
        self.assertEqual(detect_docs_site("https://www.selenium.dev/documentation/webdriver/"), "selenium")
        self.assertEqual(detect_docs_site("https://developer.mozilla.org/en-US/docs/Web/API"), "mdn")
        self.assertEqual(detect_docs_site("https://developer.mozilla.org/en-US/"), "")

    def test_format_search_results_is_stable_for_agents(self):
        output = format_search_results(
            [
                {
                    "title": "pathlib - Object-oriented filesystem paths",
                    "url": "https://docs.python.org/3/library/pathlib.html",
                    "site": "python",
                    "snippet": "Classes representing filesystem paths.",
                }
            ]
        )

        self.assertIn("[1] pathlib - Object-oriented filesystem paths", output)
        self.assertIn("https://docs.python.org/3/library/pathlib.html", output)
        self.assertIn("site: python", output)
        self.assertIn("Classes representing filesystem paths.", output)

    def test_format_links_and_examples(self):
        links = format_links(
            [
                {
                    "text": "API reference",
                    "url": "https://react.dev/reference/react",
                    "site": "react",
                }
            ]
        )
        examples = format_examples(
            [
                {
                    "language": "python",
                    "text": "from pathlib import Path\nPath('.').glob('*.py')",
                }
            ]
        )

        self.assertIn("[1] API reference", links)
        self.assertIn("site: react", links)
        self.assertIn("```python", examples)
        self.assertIn("Path('.').glob('*.py')", examples)

    def test_format_page_read_includes_page_state(self):
        output = format_page_read(
            {
                "title": "pathlib",
                "url": "https://docs.python.org/3/library/pathlib.html",
                "site": "python",
                "text": "Object-oriented filesystem paths",
            }
        )

        self.assertIn("[pathlib]", output)
        self.assertIn("https://docs.python.org/3/library/pathlib.html", output)
        self.assertIn("site: python", output)
        self.assertIn("Object-oriented filesystem paths", output)

    def test_docs_typer_commands_are_registered(self):
        runner = CliRunner()

        for command in ("help", "search", "open", "read", "links", "examples"):
            with self.subTest(command=command):
                result = runner.invoke(app, [command, "--help"])
                self.assertEqual(result.exit_code, 0, result.output)
                self.assertIn("Usage:", result.output)

    def test_selenium_imports_stay_inside_browser_extraction_functions(self):
        source = Path("src/foxpilot/sites/docs_service.py").read_text()
        module_import_block = source.split("DOCS_SITE_REGISTRY", 1)[0]

        self.assertNotIn("selenium", module_import_block)
        self.assertIn("selenium", inspect.getsource(__import__("foxpilot.sites.docs_service").sites.docs_service.extract_links))


if __name__ == "__main__":
    unittest.main()

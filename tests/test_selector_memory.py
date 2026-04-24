import json
import tempfile
import unittest
from pathlib import Path

from foxpilot.selector_memory import (
    SelectorMemory,
    SelectorRecord,
    domain_matches,
    normalize_domain,
)


class SelectorMemoryTests(unittest.TestCase):
    def test_record_success_appends_redacted_jsonl_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "selectors.jsonl")
            memory = SelectorMemory(path)

            record = memory.record_success(
                url="https://github.com/acme/repo?token=secret-token",
                action="click",
                description="Merge pull request token=secret",
                tag="button",
                role="button",
                text="Merge pull request",
                aria_label="Merge pull request",
                css_path="button.merge",
                xpath="//button[1]",
                nearby_label_text="Pull request actions",
            )

            self.assertEqual(record.domain, "github.com")
            lines = path.read_text().splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["action"], "click")
            self.assertNotIn("secret-token", lines[0])
            self.assertNotIn("token=secret", lines[0])
            self.assertIn("[REDACTED]", lines[0])

    def test_find_candidates_prefers_recent_semantic_same_domain_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            memory = SelectorMemory(Path(tmp, "selectors.jsonl"))
            memory.record_success(
                url="https://github.com/acme/repo/issues",
                action="click",
                description="Open settings",
                text="Settings",
                css_path="a.old-settings",
            )
            memory.record_success(
                url="https://github.com/acme/repo/settings",
                action="click",
                description="Open settings",
                text="Repository settings",
                aria_label="Settings",
                css_path="a.settings",
            )
            memory.record_success(
                url="https://example.com/settings",
                action="click",
                description="Open settings",
                text="Settings",
                css_path="a.other",
            )

            candidates = memory.find_candidates(
                domain="github.com",
                url="https://github.com/acme/repo/pulls",
                action="click",
                description="settings",
            )

            self.assertEqual([item.css_path for item in candidates], ["a.settings", "a.old-settings"])

    def test_domain_helpers_match_subdomains_without_matching_suffix_tricks(self):
        self.assertEqual(normalize_domain("https://www.github.com/acme"), "github.com")
        self.assertTrue(domain_matches("docs.github.com", "github.com"))
        self.assertFalse(domain_matches("notgithub.com", "github.com"))

    def test_selector_record_round_trips_with_defaults(self):
        record = SelectorRecord.from_dict(
            {
                "url": "https://example.com",
                "domain": "example.com",
                "action": "fill",
                "description": "Email",
                "text": "Email",
            }
        )

        self.assertEqual(record.tag, "")
        self.assertEqual(record.to_dict()["action"], "fill")


if __name__ == "__main__":
    unittest.main()

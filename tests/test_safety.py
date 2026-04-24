import unittest

from foxpilot.safety import (
    classify_action,
    detect_dangerous_actions,
    is_domain_allowed,
    redact_secrets,
)


class SafetyTests(unittest.TestCase):
    def test_classifies_dangerous_action_labels(self):
        cases = {
            "Delete repository": "delete",
            "Buy now": "purchase",
            "Send email": "send",
            "Publish release": "publish",
            "Merge pull request": "merge",
            "Transfer ownership": "transfer",
            "Submit payment": "payment",
        }

        for label, category in cases.items():
            with self.subTest(label=label):
                self.assertEqual(classify_action(label), category)

    def test_detect_dangerous_actions_returns_categories_and_labels(self):
        findings = detect_dangerous_actions(
            ["Cancel", "Delete project", "Merge pull request", "Save draft"]
        )

        self.assertEqual(
            findings,
            [
                {
                    "label": "Delete project",
                    "category": "delete",
                    "reason": "destructive or externally visible action",
                },
                {
                    "label": "Merge pull request",
                    "category": "merge",
                    "reason": "destructive or externally visible action",
                },
            ],
        )

    def test_domain_allowlist_supports_hosts_and_wildcards(self):
        allowlist = ["example.com", "*.trusted.test"]

        self.assertTrue(is_domain_allowed("https://example.com/path", allowlist))
        self.assertTrue(is_domain_allowed("https://app.trusted.test", allowlist))
        self.assertFalse(is_domain_allowed("https://evil-example.com", allowlist))
        self.assertFalse(is_domain_allowed("not a url", allowlist))

    def test_redacts_common_secret_patterns(self):
        text = (
            "Authorization: Bearer abc.def.ghi\n"
            "api_key=sk-test1234567890\n"
            "password: hunter2\n"
            "token=ghp_abcdefghijklmnopqrstuvwxyz123456"
        )

        redacted = redact_secrets(text)

        self.assertNotIn("abc.def.ghi", redacted)
        self.assertNotIn("sk-test1234567890", redacted)
        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz123456", redacted)
        self.assertIn("[REDACTED]", redacted)


if __name__ == "__main__":
    unittest.main()

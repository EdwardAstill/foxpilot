import unittest
from pathlib import Path

from foxpilot.sites.wait_expect import (
    CheckResult,
    pattern_matches,
    wait_app,
    wait_until,
    expect_app,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class WaitExpectSiteTests(unittest.TestCase):
    def test_pattern_matches_substrings_case_insensitively_by_default(self):
        self.assertTrue(
            pattern_matches(
                "https://example.test/dashboard?tab=settings",
                "DASHBOARD",
            )
        )
        self.assertFalse(pattern_matches("https://example.test/dashboard", "missing"))

    def test_pattern_matches_regex_when_requested(self):
        self.assertTrue(
            pattern_matches(
                "https://example.test/items/123",
                r"/items/\d+$",
                regex=True,
            )
        )
        self.assertFalse(
            pattern_matches(
                "https://example.test/items/abc",
                r"/items/\d+$",
                regex=True,
            )
        )

    def test_pattern_matches_invalid_regex_as_false(self):
        self.assertFalse(pattern_matches("Example title", "(", regex=True))

    def test_wait_until_returns_when_condition_becomes_true(self):
        clock = FakeClock()
        attempts = []

        def condition():
            attempts.append(clock.now)
            return CheckResult(
                ok=len(attempts) == 3,
                message="ready" if len(attempts) == 3 else "not ready",
            )

        result = wait_until(
            condition,
            timeout_s=5.0,
            poll_s=0.5,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 3)
        self.assertEqual(clock.sleeps, [0.5, 0.5])
        self.assertEqual(result.message, "ready")

    def test_wait_until_reports_timeout_with_last_condition_message(self):
        clock = FakeClock()

        result = wait_until(
            lambda: CheckResult(ok=False, message="still loading"),
            timeout_s=1.0,
            poll_s=0.4,
            monotonic=clock.monotonic,
            sleeper=clock.sleep,
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 4)
        self.assertIn("timed out after 1.0s", result.message)
        self.assertIn("still loading", result.message)
        self.assertEqual(clock.sleeps, [0.4, 0.4, 0.19999999999999996])

    def test_wait_subcommands_are_registered(self):
        names = {command.name for command in wait_app.registered_commands}

        self.assertEqual(names, {"help", "text", "selector", "url", "gone", "idle"})

    def test_expect_subcommands_are_registered(self):
        names = {command.name for command in expect_app.registered_commands}

        self.assertEqual(names, {"help", "text", "selector", "url", "title"})

    def test_wait_expect_source_exports_subapps(self):
        source = Path("src/foxpilot/sites/wait_expect.py").read_text()

        self.assertIn("wait_app = typer.Typer", source)
        self.assertIn("expect_app = typer.Typer", source)
        self.assertIn("@wait_app.command(name=\"text\")", source)
        self.assertIn("@expect_app.command(name=\"title\")", source)

    def test_wait_expect_docs_cover_commands(self):
        docs = Path("docs/commands/wait-expect.md").read_text()

        for command in (
            "foxpilot wait text",
            "foxpilot wait selector",
            "foxpilot wait url",
            "foxpilot wait gone",
            "foxpilot wait idle",
            "foxpilot expect text",
            "foxpilot expect selector",
            "foxpilot expect url",
            "foxpilot expect title",
        ):
            with self.subTest(command=command):
                self.assertIn(command, docs)


if __name__ == "__main__":
    unittest.main()

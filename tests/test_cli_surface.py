import subprocess
import sys
import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from foxpilot import cli


class CliSurfaceTests(unittest.TestCase):
    def test_module_execution_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "foxpilot.cli", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)

    def test_browser_startup_errors_are_clean(self):
        runner = CliRunner()

        with patch("foxpilot.cli.browser") as browser_factory:
            browser_factory.side_effect = RuntimeError("cannot bind socket")
            result = runner.invoke(cli.app, ["url"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("x cannot bind socket", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_github_browser_startup_errors_keep_branch_context(self):
        runner = CliRunner()

        with patch("foxpilot.cli.browser") as browser_factory:
            browser_factory.side_effect = RuntimeError("cannot bind socket")
            result = runner.invoke(cli.app, ["github", "repo"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("browser unavailable: cannot bind socket", result.output)
        self.assertIn("foxpilot doctor", result.output)
        self.assertNotIn("browser unavailable: 1", result.output)
        self.assertNotIn("Traceback", result.output)


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from foxpilot import cli


class FakeBrowser:
    title = "Fixture"
    current_url = "https://fixture.test"
    page_source = "<html><body>Fixture body</body></html>"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_script(self, script):
        if "outerHTML" in script:
            return self.page_source
        if "document.body.innerText" in script or "innerText" in script:
            return "Fixture body"
        if "document.images" in script:
            return []
        return ""

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")
        return True

    def set_window_size(self, width, height):
        self.size = (width, height)

    def get(self, url):
        self.current_url = url

    def get_log(self, name):
        return []


class ExpansionCliSurfaceTests(unittest.TestCase):
    def test_mission_run_creates_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = CliRunner().invoke(
                cli.app,
                ["mission", "run", "download latest invoice", "--root", tmp, "--json"],
            )
            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertEqual(payload["status"], "planned")
            self.assertTrue((Path(tmp) / f"{payload['mission_id']}.json").exists())

    def test_evidence_bundle_uses_current_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("foxpilot.cli.browser", return_value=FakeBrowser()):
                result = CliRunner().invoke(cli.app, ["evidence", "bundle", tmp, "--json"])

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertIn("bundle.json", payload["artifacts"])
            self.assertTrue((Path(tmp) / "bundle.json").exists())

    def test_qa_command_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("foxpilot.cli.browser", return_value=FakeBrowser()):
                result = CliRunner().invoke(
                    cli.app,
                    ["qa", "https://fixture.test", "--out", tmp, "--json"],
                )

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.output)
            self.assertIn("artifacts", payload)
            self.assertTrue((Path(tmp) / "qa-report.json").exists())


if __name__ == "__main__":
    unittest.main()

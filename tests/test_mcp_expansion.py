import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from foxpilot import mcp_server


class FakeBrowser:
    title = "Fixture"
    current_url = "https://fixture.test"
    page_source = "<html><body><button>Save</button></body></html>"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute_script(self, script, *args):
        if "querySelectorAll" in script:
            return {
                "title": "Fixture",
                "url": self.current_url,
                "buttons": [{"text": "Save", "selector": "button"}],
            }
        if "outerHTML" in script:
            return self.page_source
        if "innerText" in script:
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


class McpExpansionTests(unittest.TestCase):
    def test_plugin_list_returns_builtin_names(self):
        payload = json.loads(mcp_server.plugins_list())

        self.assertIn("youtube", {plugin["name"] for plugin in payload})
        self.assertIn("github", {plugin["name"] for plugin in payload})

    def test_evidence_bundle_tool_writes_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("foxpilot.mcp_server.browser", return_value=FakeBrowser()):
                payload = json.loads(mcp_server.evidence_bundle(tmp))

            self.assertIn("bundle.json", payload["artifacts"])
            self.assertTrue((Path(tmp) / "bundle.json").exists())

    def test_page_understand_tool_returns_json(self):
        with patch("foxpilot.mcp_server.browser", return_value=FakeBrowser()):
            payload = json.loads(mcp_server.page_understand())

        self.assertEqual(payload["title"], "Fixture")
        self.assertEqual(payload["buttons"][0]["text"], "Save")

    def test_mission_run_tool_creates_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = json.loads(mcp_server.mission_run("download invoice", root=tmp))

            self.assertEqual(payload["status"], "planned")
            self.assertTrue((Path(tmp) / f"{payload['mission_id']}.json").exists())


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from foxpilot.sites.onedrive import app
from foxpilot.sites.onedrive_service import (
    ONEDRIVE_VIEWS,
    build_onedrive_url,
    format_download_result,
    format_items,
    format_open_result,
    format_path,
    normalize_account,
    normalize_view,
    open_item,
    select_item,
    snapshot_download_dir,
    wait_for_download,
)


class OneDriveSiteTests(unittest.TestCase):
    def test_known_views_are_registered(self):
        self.assertEqual(
            set(ONEDRIVE_VIEWS),
            {"home", "files", "recent", "shared", "photos", "recycle"},
        )

    def test_build_onedrive_url_supports_personal_and_work_accounts(self):
        self.assertEqual(build_onedrive_url("home", account="personal"), "https://onedrive.live.com/")
        self.assertEqual(
            build_onedrive_url("recent", account="personal"),
            "https://onedrive.live.com/?v=recent",
        )
        self.assertEqual(
            build_onedrive_url("home", account="work"),
            "https://www.microsoft365.com/onedrive",
        )

    def test_account_and_view_aliases_are_normalized(self):
        self.assertEqual(normalize_account("business"), "work")
        self.assertEqual(normalize_account("school"), "work")
        self.assertEqual(normalize_view("my-files"), "files")
        self.assertEqual(normalize_view("trash"), "recycle")

    def test_unknown_view_is_clear_error(self):
        with self.assertRaisesRegex(ValueError, "unknown OneDrive view"):
            normalize_view("archive")

    def test_format_items_is_agent_friendly(self):
        output = format_items(
            [
                {
                    "name": "Budget.xlsx",
                    "kind": "file",
                    "url": "https://onedrive.live.com/edit.aspx?id=1",
                    "modified": "Yesterday",
                    "size": "12 KB",
                },
                {
                    "name": "Projects",
                    "kind": "folder",
                    "url": "https://onedrive.live.com/?id=folder",
                },
            ]
        )

        self.assertIn("[1] Budget.xlsx", output)
        self.assertIn("kind: file", output)
        self.assertIn("size: 12 KB", output)
        self.assertIn("[2] Projects", output)

    def test_format_open_result_and_path(self):
        open_output = format_open_result(
            {
                "title": "OneDrive",
                "url": "https://onedrive.live.com/?v=recent",
                "view": "recent",
                "account": "personal",
                "name": "Budget.xlsx",
            }
        )
        self.assertIn(
            "view: recent",
            open_output,
        )
        self.assertIn("name: Budget.xlsx", open_output)
        self.assertEqual(format_path(["My files", "Projects"]), "My files / Projects")
        self.assertEqual(format_path([]), "(path unavailable)")

    def test_onedrive_subapp_registers_commands(self):
        result = CliRunner().invoke(app, ["help"])

        self.assertEqual(result.exit_code, 0)
        for text in (
            "foxpilot onedrive open recent",
            "foxpilot onedrive files",
            "foxpilot onedrive search",
            "foxpilot onedrive select",
            "foxpilot onedrive download",
            "foxpilot onedrive download-selected",
            "foxpilot onedrive wait-download",
            "foxpilot onedrive open-item",
            "foxpilot onedrive path",
        ):
            self.assertIn(text, result.stdout)

    def test_files_command_emits_json_from_injected_browser(self):
        from foxpilot.sites import onedrive

        class FakeBrowser:
            title = "OneDrive"
            current_url = "https://onedrive.live.com/"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute_script(self, script, *args):
                return [{"name": "Budget.xlsx", "kind": "file", "url": "https://example.test"}]

        onedrive.set_browser_factory(lambda: FakeBrowser())
        try:
            result = CliRunner().invoke(app, ["files", "--json"])
        finally:
            onedrive.set_browser_factory(onedrive._default_browser)

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(json.loads(result.output)[0]["name"], "Budget.xlsx")

    def test_browser_startup_failure_is_clear_error(self):
        from foxpilot.sites import onedrive

        def broken_browser():
            raise RuntimeError("Marionette port never opened")

        onedrive.set_browser_factory(broken_browser)
        try:
            result = CliRunner().invoke(app, ["files"])
        finally:
            onedrive.set_browser_factory(onedrive._default_browser)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("browser unavailable: Marionette port never opened", result.output)
        self.assertIn("foxpilot doctor", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_in_page_runtime_error_is_not_mislabeled_as_browser_failure(self):
        from foxpilot.sites import onedrive

        class FakeBrowser:
            title = "OneDrive"
            current_url = "https://onedrive.live.com/"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def execute_script(self, script, *args):
                return {"ok": False, "message": "no visible OneDrive item matching 'Missing.xlsx'"}

        onedrive.set_browser_factory(lambda: FakeBrowser())
        try:
            result = CliRunner().invoke(app, ["select", "Missing.xlsx"])
        finally:
            onedrive.set_browser_factory(onedrive._default_browser)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("no visible OneDrive item matching", result.output)
        self.assertNotIn("browser unavailable", result.output)

    def test_download_command_selects_clicks_and_waits(self):
        from foxpilot.sites import onedrive

        with tempfile.TemporaryDirectory() as tmp:
            download_dir = Path(tmp)

            class DownloadButton:
                def is_displayed(self):
                    return True

                def get_attribute(self, name):
                    return ""

                def click(self):
                    (download_dir / "Budget.xlsx").write_text("done")

            class FakeBrowser:
                title = "OneDrive"
                current_url = "https://onedrive.live.com/"

                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def execute_script(self, script, *args):
                    if args == ("Budget.xlsx",):
                        return {
                            "ok": True,
                            "name": "Budget.xlsx",
                            "selected": True,
                            "method": "checkbox",
                        }
                    return None

                def find_elements(self, by, xpath):
                    if "Download" in xpath:
                        return [DownloadButton()]
                    return []

            onedrive.set_browser_factory(lambda: FakeBrowser())
            try:
                result = CliRunner().invoke(
                    app,
                    [
                        "download",
                        "Budget.xlsx",
                        "--dir",
                        str(download_dir),
                        "--timeout",
                        "0.2",
                        "--json",
                    ],
                )
            finally:
                onedrive.set_browser_factory(onedrive._default_browser)

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["status"], "downloaded")
        self.assertEqual(payload["name"], "Budget.xlsx")
        self.assertEqual(Path(payload["files"][0]).name, "Budget.xlsx")

    def test_open_item_uses_valid_attribute_fallback_xpaths(self):
        class FakeElement:
            def is_displayed(self):
                return True

            def click(self):
                return None

        class FakeDriver:
            current_url = "https://onedrive.live.com/"

            def __init__(self):
                self.seen_xpaths = []

            def find_elements(self, by, xpath):
                self.seen_xpaths.append(xpath)
                if xpath == "//*[contains(@aria-label, 'Budget.xlsx')]":
                    return [FakeElement()]
                return []

        driver = FakeDriver()

        result = open_item(driver, "Budget.xlsx")

        self.assertEqual(result["name"], "Budget.xlsx")
        self.assertIn("//*[contains(@aria-label, 'Budget.xlsx')]", driver.seen_xpaths)
        self.assertNotIn("//*[@aria-label[contains(., 'Budget.xlsx')]]", driver.seen_xpaths)

    def test_select_item_uses_browser_script_and_reports_selection(self):
        class FakeDriver:
            current_url = "https://onedrive.live.com/"

            def __init__(self):
                self.calls = []

            def execute_script(self, script, name):
                self.calls.append((script, name))
                return {"ok": True, "name": name, "selected": True, "method": "checkbox"}

        driver = FakeDriver()

        result = select_item(driver, "Budget.xlsx")

        self.assertEqual(result["name"], "Budget.xlsx")
        self.assertTrue(result["selected"])
        self.assertEqual(driver.calls[0][1], "Budget.xlsx")

    def test_wait_for_download_returns_new_completed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_dir = Path(tmp)
            before = snapshot_download_dir(download_dir)
            (download_dir / "Budget.xlsx.part").write_text("partial")
            complete = download_dir / "Budget.xlsx"
            complete.write_text("done")

            result = wait_for_download(download_dir, before=before, timeout=0.2, poll_interval=0.01)

        self.assertEqual(result["status"], "downloaded")
        self.assertEqual(result["files"], [str(complete)])

    def test_wait_for_download_times_out_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            download_dir = Path(tmp)
            before = snapshot_download_dir(download_dir)

            with self.assertRaisesRegex(TimeoutError, "no completed download"):
                wait_for_download(download_dir, before=before, timeout=0.02, poll_interval=0.01)

    def test_format_download_result_is_agent_friendly(self):
        output = format_download_result(
            {
                "status": "downloaded",
                "name": "Budget.xlsx",
                "download_dir": "/tmp/downloads",
                "files": ["/tmp/downloads/Budget.xlsx"],
            }
        )

        self.assertIn("status: downloaded", output)
        self.assertIn("name: Budget.xlsx", output)
        self.assertIn("/tmp/downloads/Budget.xlsx", output)


if __name__ == "__main__":
    unittest.main()

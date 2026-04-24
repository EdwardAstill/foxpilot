import json
import tempfile
import unittest
from pathlib import Path

from foxpilot.qa import (
    build_qa_report,
    detect_blank_page,
    detect_missing_images,
    summarize_qa,
)


class FakeDriver:
    title = "Fixture App"
    current_url = "https://fixture.test/app"

    def __init__(self):
        self.window_sizes = []
        self.visited = []
        self.console_logs = [{"level": "SEVERE", "message": "boom"}]
        self.html = (
            "<html><body><h1>Fixture</h1>"
            "<img src='ok.png'><img src='missing.png' naturalWidth='0'>"
            "</body></html>"
        )

    def get(self, url):
        self.visited.append(url)
        self.current_url = url

    def set_window_size(self, width, height):
        self.window_sizes.append((width, height))

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png")
        return True

    def execute_script(self, script):
        if "outerHTML" in script:
            return self.html
        if "document.body.innerText" in script:
            return "Fixture"
        if "naturalWidth" in script:
            return [{"src": "missing.png", "alt": ""}]
        return None

    def get_log(self, kind):
        if kind == "browser":
            return self.console_logs
        return []


class QaTests(unittest.TestCase):
    def test_blank_page_detection(self):
        self.assertTrue(detect_blank_page(""))
        self.assertTrue(detect_blank_page("<html><body></body></html>"))
        self.assertFalse(detect_blank_page("<h1>Ready</h1>"))

    def test_missing_image_detection_accepts_driver_data(self):
        findings = detect_missing_images(
            [{"src": "missing.png", "alt": "Preview"}, {"src": "", "alt": ""}]
        )

        self.assertEqual(
            findings,
            [
                {
                    "type": "missing-image",
                    "severity": "warning",
                    "message": "Image failed to load: missing.png",
                    "src": "missing.png",
                    "alt": "Preview",
                }
            ],
        )

    def test_build_qa_report_writes_artifacts_with_fake_driver(self):
        driver = FakeDriver()

        with tempfile.TemporaryDirectory() as tmp:
            report = build_qa_report(driver, "https://fixture.test/app", tmp)
            report_path = Path(tmp) / "qa-report.json"

            self.assertTrue((Path(tmp) / "desktop.png").exists())
            self.assertTrue((Path(tmp) / "mobile.png").exists())
            self.assertTrue((Path(tmp) / "fullpage.png").exists())
            self.assertTrue((Path(tmp) / "summary.md").exists())
            self.assertEqual(json.loads(report_path.read_text())["title"], "Fixture App")

        self.assertEqual(driver.visited, ["https://fixture.test/app"])
        self.assertIn((1440, 900), driver.window_sizes)
        self.assertIn((390, 844), driver.window_sizes)
        self.assertEqual(report["console"], driver.console_logs)
        self.assertTrue(any(f["type"] == "console-error" for f in report["findings"]))

    def test_summarize_qa_reports_counts_and_artifacts(self):
        summary = summarize_qa(
            {
                "url": "https://fixture.test",
                "title": "Fixture",
                "findings": [{"severity": "warning"}, {"severity": "error"}],
                "artifacts": {"desktop": "desktop.png"},
            }
        )

        self.assertIn("# QA Report", summary)
        self.assertIn("Findings: 2", summary)
        self.assertIn("desktop.png", summary)


if __name__ == "__main__":
    unittest.main()

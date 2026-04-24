import json
import tempfile
import unittest
from pathlib import Path

from foxpilot.evidence import create_evidence_bundle, redact_text


class EvidenceDriver:
    title = "Secrets Page"
    current_url = "https://example.com/account?token=super-secret"
    page_source = "<html><body>password=hunter2 api_key=abc123</body></html>"

    def __init__(self):
        self.scripts = []

    def execute_script(self, script):
        self.scripts.append(script)
        return "Account\nAuthorization: Bearer shhh-secret\nDone"

    def save_screenshot(self, path):
        Path(path).write_bytes(b"png bytes")
        return True


class MinimalDriver:
    title = "Minimal"
    current_url = "https://example.com/minimal"


class EvidenceBundleTests(unittest.TestCase):
    def test_create_evidence_bundle_writes_redacted_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = create_evidence_bundle(
                EvidenceDriver(),
                tmp,
                command="github repo",
                plugin="github",
                mode="visible",
            )

            root = Path(tmp)
            self.assertEqual(bundle["command"], "github repo")
            self.assertEqual(bundle["plugin"], "github")
            self.assertEqual(bundle["mode"], "visible")
            self.assertEqual(bundle["title"], "Secrets Page")
            self.assertTrue(root.joinpath("bundle.json").exists())
            self.assertTrue(root.joinpath("screenshot.png").exists())

            metadata = json.loads(root.joinpath("bundle.json").read_text())
            self.assertIn("bundle.json", metadata["artifacts"])
            self.assertIn("screenshot.png", metadata["artifacts"])
            self.assertGreaterEqual(metadata["redactions"]["count"], 3)

            joined = "\n".join(
                root.joinpath(name).read_text(errors="ignore")
                for name in ("bundle.json", "url.txt", "readable.txt", "page.html")
            )
            self.assertNotIn("hunter2", joined)
            self.assertNotIn("abc123", joined)
            self.assertNotIn("shhh-secret", joined)
            self.assertIn("[REDACTED]", joined)

    def test_create_evidence_bundle_skips_unsupported_driver_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = create_evidence_bundle(MinimalDriver(), tmp)

            artifacts = set(bundle["artifacts"])
            self.assertIn("bundle.json", artifacts)
            self.assertIn("url.txt", artifacts)
            self.assertNotIn("screenshot.png", artifacts)
            self.assertNotIn("page.html", artifacts)
            self.assertFalse(Path(tmp, "screenshot.png").exists())

    def test_redact_text_masks_common_secret_shapes(self):
        redacted = redact_text(
            "password=hunter2 token: abc123 api_key=secret Authorization: Bearer abc.def"
        )

        self.assertNotIn("hunter2", redacted)
        self.assertNotIn("abc123", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("abc.def", redacted)
        self.assertEqual(redacted.count("[REDACTED]"), 4)


if __name__ == "__main__":
    unittest.main()

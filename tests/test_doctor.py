import unittest

import tempfile
from pathlib import Path

from foxpilot.doctor import run_diagnostics, run_safe_fixes


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_expected_checks(self):
        report = run_diagnostics()

        for key in (
            "python",
            "geckodriver",
            "firefox",
            "zen_browser",
            "socket_bind",
            "hyprctl",
            "claude_profile_parent",
        ):
            self.assertIn(key, report)
            self.assertIn("ok", report[key])
            self.assertIn("message", report[key])

    def test_safe_fixes_create_profile_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile_dir = Path(tmp) / "foxpilot" / "claude-profile"

            result = run_safe_fixes(profile_dir=profile_dir)

            self.assertTrue(profile_dir.parent.exists())
            self.assertTrue(result["claude_profile_parent"]["ok"])


if __name__ == "__main__":
    unittest.main()

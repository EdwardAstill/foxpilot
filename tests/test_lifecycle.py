import unittest
from unittest.mock import patch

from foxpilot.core import claude_hide, claude_show


class LifecycleTests(unittest.TestCase):
    def test_show_reports_not_running_when_no_window_exists(self):
        with patch("foxpilot.core._find_claude_window", return_value=None):
            result = claude_show()

        self.assertEqual(result["status"], "not_running")

    def test_hide_reports_already_hidden_for_special_workspace(self):
        win = {"address": "0x1", "workspace": {"name": "special:claude"}}

        with patch("foxpilot.core._find_claude_window", return_value=win):
            result = claude_hide()

        self.assertEqual(result["status"], "already_hidden")

    def test_show_reports_already_visible_for_normal_workspace(self):
        win = {"address": "0x1", "workspace": {"name": "1"}}

        with patch("foxpilot.core._find_claude_window", return_value=win):
            result = claude_show()

        self.assertEqual(result["status"], "already_visible")


if __name__ == "__main__":
    unittest.main()

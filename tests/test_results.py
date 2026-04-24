import unittest

from foxpilot.results import CommandResult


class CommandResultTests(unittest.TestCase):
    def test_text_includes_message_and_page_state(self):
        result = CommandResult(
            ok=True,
            message="clicked button",
            title="Example",
            url="https://example.test",
            visible_text="Done",
        )

        output = result.to_text()

        self.assertIn("OK clicked button", output)
        self.assertIn("url: https://example.test", output)
        self.assertIn("title: Example", output)
        self.assertIn("  Done", output)

    def test_failure_text_is_clear(self):
        result = CommandResult(ok=False, message="no input found")

        self.assertEqual(result.to_text(), "x no input found")


if __name__ == "__main__":
    unittest.main()

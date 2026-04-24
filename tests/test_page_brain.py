import unittest

from foxpilot.page_brain import understand_page


class BrainDriver:
    title = "Checkout"
    current_url = "https://shop.example.com/checkout"

    def __init__(self, response):
        self.response = response
        self.calls = []

    def execute_script(self, script, limit):
        self.calls.append((script, limit))
        return self.response


class NoScriptDriver:
    title = "Static"
    current_url = "https://example.com"


class PageBrainTests(unittest.TestCase):
    def test_understand_page_returns_agent_map_and_detects_dangerous_actions(self):
        driver = BrainDriver(
            {
                "headings": [{"level": 1, "text": "Checkout"}],
                "forms": [{"label": "Payment", "fields": [{"label": "Card number"}]}],
                "buttons": [
                    {"text": "Purchase now", "selector": "button.buy"},
                    {"text": "Delete account", "selector": "button.delete"},
                    {"text": "Continue", "selector": "button.continue"},
                ],
                "inputs": [{"label": "Email", "type": "email"}],
                "links": [{"text": "Terms", "href": "/terms"}],
                "visible_errors": ["Card number is required"],
            }
        )

        page = understand_page(driver, limit=25)

        self.assertEqual(driver.calls[0][1], 25)
        self.assertEqual(page["title"], "Checkout")
        self.assertEqual(page["url"], "https://shop.example.com/checkout")
        self.assertEqual(page["headings"][0]["text"], "Checkout")
        self.assertEqual(page["visible_errors"], ["Card number is required"])
        self.assertEqual(
            [item["label"] for item in page["dangerous_actions"]],
            ["Purchase now", "Delete account"],
        )
        self.assertIn("Fill Payment form", page["suggested_next_actions"])
        self.assertIn("Click Continue", page["suggested_next_actions"])

    def test_understand_page_falls_back_without_execute_script(self):
        page = understand_page(NoScriptDriver())

        self.assertEqual(page["title"], "Static")
        self.assertEqual(page["url"], "https://example.com")
        for key in ("headings", "forms", "buttons", "inputs", "links"):
            self.assertEqual(page[key], [])
        self.assertEqual(page["dangerous_actions"], [])

    def test_dangerous_detection_catches_merge_send_and_transfer(self):
        page = understand_page(
            BrainDriver(
                {
                    "buttons": [
                        {"text": "Merge pull request"},
                        {"text": "Send invite"},
                        {"aria_label": "Transfer ownership"},
                    ],
                    "links": [{"text": "Publish release"}],
                }
            )
        )

        self.assertEqual(
            [item["label"] for item in page["dangerous_actions"]],
            ["Merge pull request", "Send invite", "Transfer ownership", "Publish release"],
        )


if __name__ == "__main__":
    unittest.main()

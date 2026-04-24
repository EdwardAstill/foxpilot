import unittest
from unittest.mock import patch

from foxpilot.actions import click_action, fill_action


class FakeElement:
    tag_name = "button"

    def __init__(self, text="Submit", fail_click=False):
        self.text = text
        self.fail_click = fail_click
        self.clicked = False
        self.value = ""
        self.keys = []

    def click(self):
        if self.fail_click:
            raise RuntimeError("intercepted")
        self.clicked = True

    def clear(self):
        self.value = ""

    def send_keys(self, value):
        self.keys.append(value)
        self.value += str(value)

    def get_attribute(self, name):
        values = {
            "role": "button",
            "aria-label": "Submit form",
            "placeholder": "",
            "name": "submit",
            "id": "submit-button",
        }
        return values.get(name, "")


class FakeDriver:
    title = "Fixture"
    current_url = "https://fixture.test"

    def __init__(self):
        self.scripts = []

    def execute_script(self, script, *args):
        self.scripts.append(script)


class ActionTests(unittest.TestCase):
    def test_click_uses_js_fallback_when_native_click_fails(self):
        driver = FakeDriver()
        element = FakeElement(fail_click=True)

        with (
            patch("foxpilot.actions.find_element", return_value=element),
            patch("foxpilot.actions.read_page", return_value=""),
            patch("foxpilot.actions.time.sleep"),
        ):
            result = click_action(driver, "Submit")

        self.assertTrue(result.ok)
        self.assertEqual(driver.scripts, ["arguments[0].click();"])

    def test_fill_uses_input_specific_lookup(self):
        driver = FakeDriver()
        element = FakeElement(text="")
        element.tag_name = "input"

        with (
            patch("foxpilot.actions.find_input_element", return_value=element) as finder,
            patch("foxpilot.actions.read_page", return_value=""),
        ):
            result = fill_action(driver, "Username", "alice")

        self.assertTrue(result.ok)
        finder.assert_called_once_with(driver, "Username")
        self.assertEqual(element.value, "alice")

    def test_click_failure_returns_result_instead_of_raising(self):
        driver = FakeDriver()

        with patch("foxpilot.actions.find_element", return_value=None):
            result = click_action(driver, "Missing")

        self.assertFalse(result.ok)
        self.assertIn("no element found", result.message)

    def test_click_records_selector_memory_when_store_is_provided(self):
        driver = FakeDriver()
        element = FakeElement()

        class Memory:
            def __init__(self):
                self.calls = []

            def record_success(self, **kwargs):
                self.calls.append(kwargs)

        memory = Memory()

        with (
            patch("foxpilot.actions.find_element", return_value=element),
            patch("foxpilot.actions.read_page", return_value=""),
            patch("foxpilot.actions.time.sleep"),
        ):
            result = click_action(driver, "Submit", selector_memory=memory)

        self.assertTrue(result.ok)
        self.assertEqual(memory.calls[0]["action"], "click")
        self.assertEqual(memory.calls[0]["description"], "Submit")
        self.assertEqual(memory.calls[0]["element_id"], "submit-button")


if __name__ == "__main__":
    unittest.main()

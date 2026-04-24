from pathlib import Path
import unittest

from foxpilot.actions import click_action, fill_action
from foxpilot.core import browser


def fixture_url(name: str) -> str:
    return Path("tests/fixtures", name).resolve().as_uri()


class BrowserSmokeTests(unittest.TestCase):
    def test_headless_fill_and_click_fixture(self):
        try:
            ctx = browser(mode="headless")
            driver = ctx.__enter__()
        except RuntimeError as exc:
            if "Unable to bind" in str(exc) or "Can't find free port" in str(exc):
                self.skipTest(f"local WebDriver socket unavailable: {exc}")
            raise

        try:
            driver.get(fixture_url("browser_form.html"))
            fill = fill_action(driver, "Username", "alice")
            click = click_action(driver, "Submit", tag="button")

            self.assertTrue(fill.ok)
            self.assertTrue(click.ok)
            self.assertEqual(
                driver.find_element("id", "username").get_attribute("value"),
                "alice",
            )
            self.assertEqual(
                driver.execute_script("return document.body.dataset.clicked"),
                "yes",
            )
        finally:
            ctx.__exit__(None, None, None)


if __name__ == "__main__":
    unittest.main()

"""foxpilot.core — browser connection and shared automation logic."""

import json
import urllib.request
from contextlib import contextmanager
from typing import Optional

MARIONETTE_PORT = 2828
REMOTE_DEBUG_PORT = 9222


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_driver_zen():
    """Connect to running Zen via geckodriver --connect-existing."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service

    opts = Options()
    service = Service(
        service_args=[
            "--connect-existing",
            "--marionette-port", str(MARIONETTE_PORT),
        ]
    )
    try:
        driver = webdriver.Firefox(options=opts, service=service)
    except Exception as e:
        raise RuntimeError(
            f"Can't connect to Zen on Marionette port {MARIONETTE_PORT}.\n"
            f"Is Zen running with --marionette? Error: {e}"
        ) from e

    # Suppress webdriver flag to reduce bot detection
    try:
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
    except Exception:
        pass

    return driver


def _get_driver_headless():
    """Launch a headless Firefox instance."""
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options

    opts = Options()
    opts.add_argument("--headless")
    try:
        driver = webdriver.Firefox(options=opts)
    except Exception as e:
        raise RuntimeError(f"Can't launch headless Firefox: {e}") from e

    return driver


@contextmanager
def browser(mode: str = "headless"):
    """Yield a WebDriver; close it on exit.

    mode="zen"      — connect to user's running Zen browser
    mode="headless" — launch ephemeral headless Firefox
    """
    driver = None
    try:
        if mode == "zen":
            driver = _get_driver_zen()
        else:
            driver = _get_driver_headless()
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tab listing — uses Firefox remote debug HTTP (port 9222), not geckodriver
# This is the only way to list ALL Zen tabs; geckodriver --connect-existing
# only exposes the single window it attaches to.
# ---------------------------------------------------------------------------

def list_tabs(port: int = REMOTE_DEBUG_PORT) -> list[dict]:
    """List all open tabs via Firefox remote debugging HTTP endpoint."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/json", timeout=3
        ) as resp:
            data = json.loads(resp.read())
        return [t for t in data if t.get("type") == "tab"]
    except Exception as e:
        raise RuntimeError(
            f"Can't reach Firefox remote debug on port {port}. "
            f"Is Zen running with --remote-debugging-port={port}? Error: {e}"
        ) from e


def activate_tab(tab_id: str, port: int = REMOTE_DEBUG_PORT) -> None:
    """Activate a tab in the browser UI by its debugger ID."""
    try:
        req = urllib.request.Request(
            f"http://localhost:{port}/json/activate/{tab_id}",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3):
            pass
    except Exception as e:
        raise RuntimeError(f"Can't activate tab {tab_id}: {e}") from e


def get_active_url(port: int = REMOTE_DEBUG_PORT) -> str:
    """Return URL of the currently active tab via remote debug."""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/json", timeout=3
        ) as resp:
            data = json.loads(resp.read())
        # The active tab is usually the first one that isn't a background page
        tabs = [t for t in data if t.get("type") == "tab"]
        if tabs:
            return tabs[0].get("url", "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Element finding
# ---------------------------------------------------------------------------

def find_element(driver, text: str, role: Optional[str] = None, tag: Optional[str] = None):
    """Find a visible element by text, aria-label, placeholder, or title."""
    from selenium.webdriver.common.by import By

    # Escape single quotes for XPath
    escaped = text.replace("'", "\\'")
    candidates = []

    if tag:
        candidates.append(f"//{tag}[contains(., '{escaped}')]")

    if role:
        candidates += [
            f"//*[@role='{role}'][contains(., '{escaped}')]",
            f"//*[@role='{role}'][@aria-label[contains(., '{escaped}')]]",
        ]
    else:
        # Interactive elements take priority
        candidates += [
            f"//button[contains(., '{escaped}')]",
            f"//a[contains(., '{escaped}')]",
            f"//input[@placeholder[contains(., '{escaped}')]]",
            f"//textarea[@placeholder[contains(., '{escaped}')]]",
            f"//select[contains(., '{escaped}')]",
            f"//*[@aria-label[contains(., '{escaped}')]]",
            f"//*[@title[contains(., '{escaped}')]]",
            f"//*[contains(text(), '{escaped}')]",
        ]

    for xpath in candidates:
        try:
            els = driver.find_elements(By.XPATH, xpath)
            visible = [e for e in els if e.is_displayed()]
            if visible:
                return visible[0]
        except Exception:
            continue

    return None


def describe_element(el) -> str:
    """Short human-readable description of an element."""
    tag = el.tag_name
    text = (el.text or "")[:60].strip()
    role = el.get_attribute("role") or ""
    label = el.get_attribute("aria-label") or ""
    placeholder = el.get_attribute("placeholder") or ""

    parts = [f"<{tag}>"]
    if role:
        parts.append(f'role="{role}"')
    if label:
        parts.append(f'aria-label="{label}"')
    elif placeholder:
        parts.append(f'placeholder="{placeholder}"')
    elif text:
        parts.append(f'"{text}"')
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Page reading
# ---------------------------------------------------------------------------

def read_page(driver, selector: Optional[str] = None, max_chars: int = 3000) -> str:
    """Extract visible text from current page or a scoped element."""
    from selenium.webdriver.common.by import By
    from foxpilot.readability import extract_main_content

    if selector:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            text = el.text
        except Exception:
            return f"(selector '{selector}' not found)"
    else:
        text = extract_main_content(driver)

    if not text:
        return "(no visible text)"

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result = "\n".join(lines)

    if len(result) > max_chars:
        result = result[:max_chars] + f"\n... [truncated — {len(result)} total chars]"

    return result


def feedback(driver, action_msg: str, selector: Optional[str] = None, max_lines: int = 20) -> str:
    """Return action result + current page state as a formatted string."""
    lines = [action_msg, f"url: {driver.current_url}", f"title: {driver.title}"]

    text = read_page(driver, selector, max_chars=1200)
    if text and text != "(no visible text)":
        lines.append("visible:")
        content_lines = text.splitlines()
        for line in content_lines[:max_lines]:
            lines.append(f"  {line}")
        if len(content_lines) > max_lines:
            lines.append(f"  ... (+{len(content_lines) - max_lines} more lines)")

    return "\n".join(lines)

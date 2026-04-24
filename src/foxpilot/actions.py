"""Shared browser command implementations.

CLI and MCP adapters call these functions so their behavior cannot drift.
"""

from __future__ import annotations

import time

from selenium.webdriver.common.keys import Keys

from foxpilot.core import describe_element, find_element, find_input_element, read_page
from foxpilot.results import CommandResult


def page_state(driver) -> dict[str, str]:
    visible_text = read_page(driver, max_chars=1200)
    if visible_text == "(no visible text)":
        visible_text = ""
    return {
        "title": driver.title,
        "url": driver.current_url,
        "visible_text": visible_text,
    }


def click_action(
    driver,
    description: str,
    role: str | None = None,
    tag: str | None = None,
    settle_seconds: float = 0.8,
    selector_memory=None,
) -> CommandResult:
    el = find_element(driver, description, role=role, tag=tag)
    if not el:
        return CommandResult(
            ok=False,
            message=f"no element found matching '{description}'",
        )

    desc = describe_element(el)
    try:
        el.click()
    except Exception:
        driver.execute_script("arguments[0].click();", el)

    if settle_seconds:
        time.sleep(settle_seconds)
    _record_selector_success(
        selector_memory,
        driver=driver,
        element=el,
        action="click",
        description=description,
    )
    return CommandResult(ok=True, message=f"clicked {desc}", **page_state(driver))


def fill_action(
    driver,
    description: str,
    value: str,
    submit: bool = False,
    settle_seconds: float = 0.8,
    selector_memory=None,
) -> CommandResult:
    el = find_input_element(driver, description)
    if not el:
        return CommandResult(ok=False, message=f"no input found for '{description}'")

    desc = describe_element(el)
    el.clear()
    el.send_keys(value)

    if submit:
        el.send_keys(Keys.RETURN)
        if settle_seconds:
            time.sleep(settle_seconds)
        _record_selector_success(
            selector_memory,
            driver=driver,
            element=el,
            action="fill",
            description=description,
        )
        return CommandResult(
            ok=True,
            message=f"filled {desc} + submitted",
            **page_state(driver),
        )
    _record_selector_success(
        selector_memory,
        driver=driver,
        element=el,
        action="fill",
        description=description,
    )
    return CommandResult(
        ok=True,
        message=f"filled {desc} with '{value}'",
        **page_state(driver),
    )


def _record_selector_success(
    selector_memory,
    *,
    driver,
    element,
    action: str,
    description: str,
) -> None:
    if selector_memory is None:
        return
    try:
        selector_memory.record_success(
            url=getattr(driver, "current_url", ""),
            action=action,
            description=description,
            tag=getattr(element, "tag_name", ""),
            role=_attribute(element, "role"),
            text=getattr(element, "text", ""),
            aria_label=_attribute(element, "aria-label"),
            placeholder=_attribute(element, "placeholder"),
            name=_attribute(element, "name"),
            element_id=_attribute(element, "id"),
        )
    except Exception:
        return


def _attribute(element, name: str) -> str:
    try:
        value = element.get_attribute(name)
    except Exception:
        return ""
    return "" if value is None else str(value)

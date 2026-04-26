"""Shared DOM extraction helpers for site service modules.

Every site service module needs the same handful of "try a list of selectors,
return the first match (or its text/attribute)" primitives. This module owns
the canonical implementations so service files do not each carry their own
copies. Selenium imports stay deferred — Selenium is an optional runtime
dependency for unit-tested URL/format helpers.
"""

from __future__ import annotations

from typing import Iterable


def find_one_css(driver, selectors: Iterable[str]):
    """Return the first element matching any CSS selector, or ``None``."""
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            return driver.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
    return None


def find_one_xpath(driver, xpaths: Iterable[str]):
    """Return the first element matching any XPath, or ``None``."""
    from selenium.webdriver.common.by import By

    for xpath in xpaths:
        try:
            return driver.find_element(By.XPATH, xpath)
        except Exception:
            continue
    return None


def find_all_css(driver, selectors: Iterable[str]) -> list:
    """Return the first non-empty list of matches for any CSS selector, or ``[]``."""
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            if els:
                return els
        except Exception:
            continue
    return []


def text_first(driver, selectors: Iterable[str]) -> str:
    """Return the stripped text of the first matching element, or ``""``."""
    el = find_one_css(driver, selectors)
    if el is None:
        return ""
    try:
        return (el.text or "").strip()
    except Exception:
        return ""


def list_texts(driver, selectors: Iterable[str], limit: int = 50) -> list[str]:
    """Return the unique stripped texts of all matching elements, capped at ``limit``."""
    els = find_all_css(driver, selectors)
    out: list[str] = []
    for el in els:
        if len(out) >= limit:
            break
        try:
            text = (el.text or "").strip()
        except Exception:
            continue
        if text and text not in out:
            out.append(text)
    return out


def child_el(parent, selectors: Iterable[str]):
    """Return the first descendant element matching any CSS selector, or ``None``."""
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            return parent.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
    return None


def child_text(parent, selectors: Iterable[str]) -> str:
    """Return the stripped text of the first descendant matching any CSS selector."""
    el = child_el(parent, selectors)
    if el is None:
        return ""
    try:
        return (el.text or "").strip()
    except Exception:
        return ""


def child_attr(parent, selectors: Iterable[str], attr: str) -> str:
    """Return the named attribute of the first descendant matching any CSS selector."""
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            el = parent.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        try:
            value = el.get_attribute(attr)
        except Exception:
            continue
        if value:
            return value
    return ""


def safe_url(driver) -> str:
    """Return ``driver.current_url`` or ``""`` if it raises."""
    try:
        return driver.current_url
    except Exception:
        return ""


__all__ = [
    "child_attr",
    "child_el",
    "child_text",
    "find_all_css",
    "find_one_css",
    "find_one_xpath",
    "list_texts",
    "safe_url",
    "text_first",
]

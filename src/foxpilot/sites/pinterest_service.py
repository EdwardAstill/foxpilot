"""Service layer for Pinterest (pinterest.com) browser workflows.

Pinterest is moderately hostile to automation: login walls, lazy-loaded
masonry grids, and occasional bot-challenge redirects. The recommended
foxpilot mode is `--zen` (reuse the user's already-signed-in session).
This module exposes URL helpers, username/pin normalization, formatters,
and best-effort DOM extraction stubs. Selenium imports stay local-to-
function. Selectors live behind private `_find_*` helpers so a single
edit re-tunes the plugin when Pinterest changes its markup.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
from typing import Any

from foxpilot.sites._dom import (
    child_attr as _child_attr,
    find_all_css as _find_all_css,
    find_one_xpath as _find_one_xpath,
    safe_url as _safe_url,
    text_first as _text_first,
)


PINTEREST_HOST = "www.pinterest.com"
PINTEREST_HOME = f"https://{PINTEREST_HOST}/"

SECTIONS = {
    "home": "",
    "today": "ideas/",
    "explore": "ideas/",
    "following": "following/",
    "notifications": "news/",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,75}$")
_PIN_ID_RE = re.compile(r"^\d+$")


def is_pinterest_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("pinterest.com")


def home_url() -> str:
    return PINTEREST_HOME


def section_url(section: str) -> str:
    key = (section or "").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown Pinterest section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTIONS))})"
        )
    return f"{PINTEREST_HOME}{SECTIONS[key]}"


def normalize_username(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty Pinterest username")
    if "://" in raw or raw.startswith("www.") or raw.startswith("pinterest.com"):
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            raw = parts[0]
    raw = raw.lstrip("@").strip("/")
    if not _USERNAME_RE.match(raw):
        raise ValueError(f"invalid Pinterest username: {value!r}")
    return raw


def profile_url(username_or_url: str) -> str:
    username = normalize_username(username_or_url)
    return f"{PINTEREST_HOME}{username}/"


def board_url(username_or_url: str, board_slug: str) -> str:
    username = normalize_username(username_or_url)
    slug = (board_slug or "").strip().strip("/")
    if not slug:
        raise ValueError("empty board slug")
    return f"{PINTEREST_HOME}{username}/{urllib.parse.quote(slug, safe='-_')}/"


def pin_url(pin_id: str) -> str:
    raw = (pin_id or "").strip().strip("/")
    if not raw:
        raise ValueError("empty pin id")
    return f"{PINTEREST_HOME}pin/{urllib.parse.quote(raw, safe='')}/"


def search_url(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    encoded = urllib.parse.urlencode({"q": query.strip()})
    return f"{PINTEREST_HOME}search/pins/?{encoded}"


def normalize_pin_target(target: str) -> str:
    """Accept a pin id, /pin/<id>/ path, or full URL and return a full URL."""
    raw = (target or "").strip()
    if not raw:
        raise ValueError("empty pin target")
    if "://" in raw:
        return raw
    if raw.startswith("/pin/") or raw.startswith("pin/"):
        pin_id = raw.strip("/").split("/")[-1]
        return pin_url(pin_id)
    if _PIN_ID_RE.match(raw):
        return pin_url(raw)
    raise ValueError(f"cannot resolve pin target: {target!r} — expected a numeric id or /pin/<id>/ URL")


# ---------------------------------------------------------------------------
# Politeness jitter
# ---------------------------------------------------------------------------

def polite_jitter(min_secs: float = 0.5, spread: float = 0.8) -> None:
    time.sleep(min_secs + random.random() * spread)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join([
        f"title: {data.get('title', '')}",
        f"url: {data.get('url', '')}",
        f"section: {data.get('section', '')}",
    ])


def format_profile(data: dict[str, Any]) -> str:
    if not data:
        return "(no profile data)"
    lines = []
    for key in ("username", "name", "bio", "pins", "followers", "following", "url"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_pins(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no pins)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('title') or item.get('pin_id') or '(no title)'}")
        for key in ("description", "board", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_boards(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no boards)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('title') or '(no title)'}")
        for key in ("pin_count", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no search results)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('title') or '(no title)'}")
        for key in ("description", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

def extract_profile(driver) -> dict[str, Any]:
    """Read username, display name, bio, and counts from a profile page."""
    username = ""
    try:
        url = driver.current_url or ""
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            username = parts[0]
    except Exception:
        username = ""

    name = _text_first(driver, [
        "h1[data-test-id='profile-name']",
        "div[data-test-id='profile-name'] h1",
        "h1",
    ])
    bio = _text_first(driver, [
        "div[data-test-id='profile-bio']",
        "span[data-test-id='profile-bio']",
        "div[class*='bio']",
    ])
    followers = _text_first(driver, [
        "a[href*='followers'] span",
        "button[data-test-id='followers'] span",
        "[data-test-id='profile-followers-count']",
    ])
    following = _text_first(driver, [
        "a[href*='following'] span",
        "button[data-test-id='following'] span",
        "[data-test-id='profile-following-count']",
    ])
    pins = _text_first(driver, [
        "[data-test-id='profile-pins-count']",
        "a[href*='/pins/'] span",
    ])
    return {
        "username": username,
        "name": name,
        "bio": bio,
        "pins": pins,
        "followers": followers,
        "following": following,
        "url": _safe_url(driver),
    }


def extract_pins(driver, limit: int = 12) -> list[dict[str, Any]]:
    """Extract pins from a profile or board page. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _find_all_css(driver, [
        "div[data-test-id='pin'] a[href*='/pin/']",
        "div[data-test-id='pinWrapper'] a[href*='/pin/']",
        "a[href*='/pin/']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        href = ""
        try:
            href = card.get_attribute("href") or ""
        except Exception:
            href = ""
        if not href or href in seen:
            continue
        seen.add(href)
        pin_id = _pin_id_from_url(href)
        title = ""
        description = ""
        try:
            title = (card.get_attribute("aria-label") or "").strip()
        except Exception:
            title = ""
        if not title:
            img = _child_attr(card, ["img"], "alt")
            title = img
        board = _board_from_url(href)
        results.append({
            "pin_id": pin_id,
            "title": title,
            "description": description,
            "board": board,
            "url": href,
        })
        if len(results) % 4 == 0:
            polite_jitter()
    return results


def extract_boards(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Extract boards from a profile page. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    username = ""
    try:
        url = driver.current_url or ""
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            username = parts[0]
    except Exception:
        username = ""

    cards = _find_all_css(driver, [
        "div[data-test-id='board'] a[href]",
        "div[data-test-id='boardCard'] a[href]",
        f"a[href^='/{username}/'][href$='/']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        href = ""
        try:
            href = card.get_attribute("href") or ""
        except Exception:
            href = ""
        if not href or href in seen:
            continue
        parsed = urllib.parse.urlparse(href)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) != 2:
            continue
        seen.add(href)
        title = ""
        try:
            title = (card.text or "").strip().splitlines()[0]
        except Exception:
            title = ""
        pin_count = ""
        try:
            all_lines = (card.text or "").strip().splitlines()
            for line in all_lines[1:]:
                if "pin" in line.lower() or line.strip().isdigit():
                    pin_count = line.strip()
                    break
        except Exception:
            pin_count = ""
        results.append({
            "title": title,
            "slug": parts[1],
            "pin_count": pin_count,
            "url": href,
        })
    return results


def extract_search_results(driver, limit: int = 12) -> list[dict[str, Any]]:
    """Extract pins from a search-results page. Best effort."""
    return extract_pins(driver, limit=limit)


def click_follow_button(driver) -> bool:
    """Click the Follow button on a profile page. Returns True on click."""
    btn = _find_one_xpath(driver, [
        "//button[normalize-space()='Follow']",
        "//button[@data-test-id='follow-button']",
        "//div[@data-test-id='follow-button']",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def click_save_button(driver) -> bool:
    """Click the Save button on an open pin page. Returns True on click."""
    btn = _find_one_xpath(driver, [
        "//button[normalize-space()='Save']",
        "//button[@data-test-id='save-button']",
        "//div[@data-test-id='save-button']",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def select_board_for_save(driver, board_name: str) -> bool:
    """After the save dialog opens, pick a board by name. Best effort."""
    polite_jitter(0.5, 0.3)
    board = _find_one_xpath(driver, [
        f"//div[@data-test-id='board-row' and contains(., '{board_name}')]",
        f"//button[contains(., '{board_name}')]",
        f"//div[@role='button' and contains(., '{board_name}')]",
    ])
    if board is None:
        return False
    try:
        board.click()
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# URL parsing helpers
# ---------------------------------------------------------------------------

def _pin_id_from_url(url: str) -> str:
    if not url or "/pin/" not in url:
        return ""
    try:
        return url.rstrip("/").split("/pin/")[1].split("/")[0]
    except Exception:
        return ""


def _board_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] != "pin":
            return parts[1]
    except Exception:
        pass
    return ""


__all__ = [
    "PINTEREST_HOME",
    "PINTEREST_HOST",
    "SECTIONS",
    "board_url",
    "click_follow_button",
    "click_save_button",
    "extract_boards",
    "extract_pins",
    "extract_profile",
    "extract_search_results",
    "format_boards",
    "format_open_result",
    "format_pins",
    "format_profile",
    "format_search_results",
    "home_url",
    "is_pinterest_url",
    "normalize_pin_target",
    "normalize_username",
    "pin_url",
    "polite_jitter",
    "profile_url",
    "search_url",
    "section_url",
    "select_board_for_save",
]

"""Service layer for Figma (figma.com) browser workflows.

Figma is fully authenticated: all content requires a signed-in session.
The recommended foxpilot mode is `--zen`. Foxpilot interacts with the
web app, not the Figma API — so this drives the browser UI. All actions
are read-only (open files, navigate, inspect). Selectors live behind
`_find_*` helpers.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
from typing import Any

from foxpilot.sites._dom import (
    child_el as _child_el,
    child_text as _child_text,
    find_all_css as _find_all_css,
    safe_url as _safe_url,
    text_first as _text_first,
)


FIGMA_HOST = "www.figma.com"
FIGMA_HOME = f"https://{FIGMA_HOST}/"

_FILE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{10,50}$")


def is_figma_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("figma.com")


def home_url() -> str:
    return FIGMA_HOME


def files_url() -> str:
    return f"{FIGMA_HOME}files/recents-and-sharing"


def file_url(key_or_url: str) -> str:
    raw = (key_or_url or "").strip()
    if not raw:
        raise ValueError("empty file key or URL")
    if "://" in raw:
        return raw
    if raw.startswith("/"):
        return f"https://{FIGMA_HOST}{raw}"
    if _FILE_KEY_RE.match(raw):
        return f"{FIGMA_HOME}file/{raw}/"
    raise ValueError(f"cannot resolve Figma file target: {key_or_url!r} — expected a file key or full URL")


def search_url(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    encoded = urllib.parse.urlencode({"q": query.strip()})
    return f"{FIGMA_HOME}search?{encoded}"


def polite_jitter(min_secs: float = 0.3, spread: float = 0.5) -> None:
    time.sleep(min_secs + random.random() * spread)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join([
        f"title: {data.get('title', '')}",
        f"url: {data.get('url', '')}",
    ])


def format_file(data: dict[str, Any]) -> str:
    if not data:
        return "(no file data)"
    lines = []
    for key in ("name", "team", "project", "last_modified", "url"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_files(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no files)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('name', '(no name)')}")
        for key in ("team", "project", "last_modified", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_search_results(results: list[dict[str, Any]]) -> str:
    return format_files(results)


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

def extract_file_metadata(driver) -> dict[str, Any]:
    """Extract title and metadata from an open Figma file. Best effort."""
    name = _text_first(driver, [
        "span[class*='filename']",
        "title",
        "div[class*='title-editor']",
    ])
    if not name:
        try:
            title = driver.title or ""
            name = title.split("–")[0].strip() or title.split("-")[0].strip()
        except Exception:
            name = ""
    return {
        "name": name,
        "url": _safe_url(driver),
    }


def extract_files_list(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Extract recent/shared files from the Figma files dashboard. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _find_all_css(driver, [
        "div[class*='thumbnail_grid'] a[href*='/file/']",
        "div[class*='thumbnail_grid'] a[href*='/design/']",
        "a[data-testid*='file-thumbnail']",
        "a[href*='/file/']",
        "a[href*='/design/']",
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
        name = ""
        try:
            name_el = _child_el(card, [
                "span[class*='name']",
                "div[class*='name']",
                "p",
            ])
            if name_el:
                name = (name_el.text or "").strip()
        except Exception:
            name = ""
        if not name:
            try:
                name = (card.get_attribute("aria-label") or "").strip()
            except Exception:
                name = ""
        last_modified = _child_text(card, [
            "span[class*='modified']",
            "div[class*='modified']",
        ])
        results.append({
            "name": name,
            "last_modified": last_modified,
            "url": href,
        })
    return results


def extract_search_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract search results from Figma search page. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _find_all_css(driver, [
        "div[class*='search'] a[href*='/file/']",
        "div[class*='search'] a[href*='/design/']",
        "a[href*='/file/']",
        "a[href*='/design/']",
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
        name = ""
        try:
            name = (card.text or "").strip().splitlines()[0]
        except Exception:
            name = ""
        results.append({
            "name": name,
            "url": href,
        })
    return results


__all__ = [
    "FIGMA_HOME",
    "FIGMA_HOST",
    "extract_file_metadata",
    "extract_files_list",
    "extract_search_results",
    "file_url",
    "files_url",
    "format_file",
    "format_files",
    "format_open_result",
    "format_search_results",
    "home_url",
    "is_figma_url",
    "polite_jitter",
    "search_url",
]

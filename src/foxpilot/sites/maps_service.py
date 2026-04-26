"""Service layer for Google Maps (google.com/maps) browser workflows.

Google Maps is mostly read-only for foxpilot use cases: search, directions,
and place lookups. No login required for basic usage. The DOM is
JavaScript-heavy and changes frequently; extraction is best-effort.
Selectors live behind `_find_*` helpers.
"""

from __future__ import annotations

import random
import time
import urllib.parse
from typing import Any

from foxpilot.sites._dom import (
    child_text as _child_text,
    find_all_css as _find_all_css,
    find_one_css as _find_one_css,
    safe_url as _safe_url,
    text_first as _text_first,
)


MAPS_HOST = "www.google.com"
MAPS_HOME = "https://www.google.com/maps"

TRAVEL_MODES = {
    "driving": "0",
    "transit": "3",
    "walking": "2",
    "cycling": "1",
    "bicycling": "1",
}


def is_maps_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("google.com") and "/maps" in (parsed.path or "")


def home_url() -> str:
    return MAPS_HOME


def search_url(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    encoded = urllib.parse.quote_plus(query.strip())
    return f"https://www.google.com/maps/search/{encoded}/"


def directions_url(origin: str, destination: str, mode: str = "driving") -> str:
    if not origin or not origin.strip():
        raise ValueError("empty origin")
    if not destination or not destination.strip():
        raise ValueError("empty destination")
    mode_key = (mode or "driving").lower().strip()
    if mode_key not in TRAVEL_MODES:
        raise ValueError(
            f"invalid travel mode: {mode!r} "
            f"(expected one of: {', '.join(sorted(TRAVEL_MODES))})"
        )
    enc_origin = urllib.parse.quote_plus(origin.strip())
    enc_dest = urllib.parse.quote_plus(destination.strip())
    travelmode = TRAVEL_MODES[mode_key]
    return f"https://www.google.com/maps/dir/{enc_origin}/{enc_dest}/@?travelmode={travelmode}"


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


def format_place(data: dict[str, Any]) -> str:
    if not data:
        return "(no place data)"
    lines = []
    for key in ("name", "address", "rating", "reviews", "phone", "hours", "website", "url"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_places(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no results)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('name', '(no name)')}")
        for key in ("address", "rating", "reviews", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_directions(data: dict[str, Any]) -> str:
    if not data:
        return "(no directions data)"
    lines = []
    for key in ("origin", "destination", "mode", "duration", "distance", "summary"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    steps = data.get("steps") or []
    if steps:
        lines.append("steps:")
        for i, step in enumerate(steps, 1):
            lines.append(f"  [{i}] {step}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

def extract_place(driver) -> dict[str, Any]:
    """Extract place details from a Maps place panel. Best effort."""
    name = _text_first(driver, [
        "h1.DUwDvf",
        "h1[class*='fontHeadlineLarge']",
        "div[role='main'] h1",
    ])
    address = _text_first(driver, [
        "button[data-item-id='address'] div[class*='fontBodyMedium']",
        "div[data-item-id='address']",
        "button[aria-label*='Address']",
    ])
    rating = _text_first(driver, [
        "div[class*='fontDisplayLarge']",
        "span[aria-label*='stars']",
        "div[role='img'][aria-label*='stars']",
    ])
    reviews = _text_first(driver, [
        "button[aria-label*='review']",
        "span[aria-label*='review']",
    ])
    phone = _text_first(driver, [
        "button[data-item-id*='phone'] div[class*='fontBodyMedium']",
        "button[aria-label*='Phone']",
    ])
    hours = _text_first(driver, [
        "div[data-item-id='oh'] div[class*='fontBodyMedium']",
        "div[aria-label*='hours']",
    ])
    website = ""
    try:
        website_el = _find_one_css(driver, [
            "a[data-item-id='authority']",
            "a[aria-label*='website']",
        ])
        if website_el:
            website = website_el.get_attribute("href") or ""
    except Exception:
        website = ""
    return {
        "name": name,
        "address": address,
        "rating": rating,
        "reviews": reviews,
        "phone": phone,
        "hours": hours,
        "website": website,
        "url": _safe_url(driver),
    }


def extract_search_results(driver, limit: int = 5) -> list[dict[str, Any]]:
    """Extract place cards from a Maps search result list. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _find_all_css(driver, [
        "div[role='feed'] > div > div[jsaction]",
        "div[class*='Nv2PK']",
        "div[class*='THOPZb']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        name = _child_text(card, [
            "div[class*='fontHeadlineSmall']",
            "span[class*='fontBodyLarge']",
            "div[role='heading']",
        ])
        if not name or name in seen:
            continue
        seen.add(name)
        address = _child_text(card, [
            "div[class*='W4Efsd'] span",
            "span[class*='fontBodyMedium']",
        ])
        rating = _child_text(card, [
            "span[role='img']",
            "span[aria-label*='stars']",
        ])
        url = _safe_url(driver)
        results.append({
            "name": name,
            "address": address,
            "rating": rating,
            "url": url,
        })
    return results


def extract_directions(driver) -> dict[str, Any]:
    """Extract route summary from a Maps directions page. Best effort."""
    duration = _text_first(driver, [
        "div[class*='fontHeadlineSmall'][jstcache]",
        "div[id='section-directions-trip-0'] div[class*='duration']",
        "div[class*='trip'] div[class*='duration']",
    ])
    distance = _text_first(driver, [
        "div[class*='trip'] div[class*='distance']",
        "div[id='section-directions-trip-0'] div[class*='distance']",
    ])
    summary = _text_first(driver, [
        "div[class*='trip'] h2",
        "div[data-trip-index='0'] div[class*='trip-title']",
    ])
    steps: list[str] = []
    step_els = _find_all_css(driver, [
        "div[class*='step-directions'] div[class*='step-text']",
        "div[data-guide-step] div[class*='step-description']",
    ])
    for el in step_els[:15]:
        try:
            text = (el.text or "").strip()
            if text:
                steps.append(text)
        except Exception:
            continue
    return {
        "duration": duration,
        "distance": distance,
        "summary": summary,
        "steps": steps,
        "url": _safe_url(driver),
    }


__all__ = [
    "MAPS_HOME",
    "MAPS_HOST",
    "TRAVEL_MODES",
    "directions_url",
    "extract_directions",
    "extract_place",
    "extract_search_results",
    "format_directions",
    "format_open_result",
    "format_place",
    "format_places",
    "home_url",
    "is_maps_url",
    "polite_jitter",
    "search_url",
]

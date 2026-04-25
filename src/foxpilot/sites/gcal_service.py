"""Service layer for Google Calendar (calendar.google.com) browser workflows.

Holds URL helpers (view URLs, date-range query strings), formatters for
human/JSON output, and best-effort DOM extraction stubs. All Selenium imports
are local-to-function so this module can be unit-tested without a live driver.
"""

from __future__ import annotations

import re
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Optional


GCAL_HOST = "calendar.google.com"
GCAL_HOME = f"https://{GCAL_HOST}/"
GCAL_RENDER = f"https://{GCAL_HOST}/calendar/u/0/r"

VALID_VIEWS: tuple[str, ...] = ("day", "week", "month", "agenda")

# Loose YYYY-MM-DD or YYYYMMDD or "today" / "tomorrow" / +N day offset.
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_COMPACT_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")
_OFFSET_RE = re.compile(r"^([+-]?\d+)d$")


def is_gcal_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host == GCAL_HOST or host.endswith("." + GCAL_HOST)


def home_url() -> str:
    return GCAL_HOME


def view_url(view: str, on: Optional[date] = None) -> str:
    """Return the calendar URL for a named view (`day`, `week`, `month`, `agenda`).

    When `on` is provided, append `?dates=YYYYMMDD` so Calendar lands on that
    date (Google Calendar honours this on /r/<view>/YYYY/MM/DD too, but the
    query-string form is the documented short hand).
    """
    if view not in VALID_VIEWS:
        raise ValueError(f"unknown view: {view!r} (expected one of {', '.join(VALID_VIEWS)})")
    base = f"{GCAL_RENDER}/{view}"
    if on is not None:
        return f"{base}?dates={format_compact_date(on)}"
    return base


def date_range_url(view: str, start: date, end: Optional[date] = None) -> str:
    """Return the calendar URL with `?dates=YYYYMMDD/YYYYMMDD` when end is set."""
    if view not in VALID_VIEWS:
        raise ValueError(f"unknown view: {view!r} (expected one of {', '.join(VALID_VIEWS)})")
    start_part = format_compact_date(start)
    if end is None:
        dates = start_part
    else:
        if end < start:
            raise ValueError("end date must not be before start date")
        dates = f"{start_part}/{format_compact_date(end)}"
    return f"{GCAL_RENDER}/{view}?dates={dates}"


def search_url(query: str) -> str:
    encoded = urllib.parse.urlencode({"q": query})
    return f"{GCAL_RENDER}/search?{encoded}"


def event_create_url(
    *,
    title: Optional[str] = None,
    when: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    invitees: Optional[Iterable[str]] = None,
    location: Optional[str] = None,
    details: Optional[str] = None,
) -> str:
    """Build a Google Calendar `eventedit` URL with prefilled fields.

    Google Calendar accepts the legacy `render?action=TEMPLATE` form which is
    universal across accounts; we emit that.
    """
    params: list[tuple[str, str]] = [("action", "TEMPLATE")]
    if title:
        params.append(("text", title))
    if when:
        start_dt = parse_when(when)
        end_dt = start_dt + timedelta(minutes=duration_minutes or 60)
        params.append(("dates", f"{format_compact_datetime(start_dt)}/{format_compact_datetime(end_dt)}"))
    if invitees:
        joined = ",".join(i.strip() for i in invitees if i and i.strip())
        if joined:
            params.append(("add", joined))
    if location:
        params.append(("location", location))
    if details:
        params.append(("details", details))
    encoded = urllib.parse.urlencode(params)
    return f"https://{GCAL_HOST}/calendar/render?{encoded}"


def format_compact_date(value: date) -> str:
    """Return `YYYYMMDD` — the form Google Calendar's `?dates=` expects."""
    return value.strftime("%Y%m%d")


def format_compact_datetime(value: datetime) -> str:
    """Return `YYYYMMDDTHHMMSS` for the `eventedit` `dates=` parameter."""
    return value.strftime("%Y%m%dT%H%M%S")


def parse_date(value: str, *, today: Optional[date] = None) -> date:
    """Parse a flexible date string used by --from / --to.

    Accepts `YYYY-MM-DD`, `YYYYMMDD`, `today`, `tomorrow`, `+Nd`, `-Nd`.
    """
    if not value:
        raise ValueError("empty date")
    raw = value.strip().lower()
    base = today or date.today()
    if raw == "today":
        return base
    if raw == "tomorrow":
        return base + timedelta(days=1)
    if raw == "yesterday":
        return base - timedelta(days=1)
    m = _OFFSET_RE.match(raw)
    if m:
        return base + timedelta(days=int(m.group(1)))
    m = _ISO_DATE_RE.match(raw)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return date(y, mo, d)
    m = _COMPACT_DATE_RE.match(raw)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return date(y, mo, d)
    raise ValueError(f"invalid date: {value!r} (expected YYYY-MM-DD, YYYYMMDD, today, tomorrow, +Nd)")


def parse_when(value: str) -> datetime:
    """Parse a `--when` string for event creation.

    Accepts `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM`, or just a date (start at 09:00).
    """
    raw = value.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        d = parse_date(raw)
    except ValueError as exc:
        raise ValueError(
            f"invalid datetime: {value!r} (expected YYYY-MM-DD HH:MM)"
        ) from exc
    return datetime(d.year, d.month, d.day, 9, 0)


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"view: {data.get('view', '')}",
        ]
    )


def format_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "(no events)"
    lines: list[str] = []
    for ev in events:
        when = ev.get("when") or ev.get("start") or ""
        title = ev.get("title") or "(untitled)"
        cal = ev.get("calendar") or ""
        loc = ev.get("location") or ""
        head = f"{when:<20} {title}"
        if cal:
            head += f"  [{cal}]"
        if loc:
            head += f"  @ {loc}"
        lines.append(head)
    return "\n".join(lines)


def format_event_detail(event: dict[str, Any]) -> str:
    keys = ("title", "when", "start", "end", "calendar", "location", "url", "description", "guests")
    lines: list[str] = []
    for key in keys:
        val = event.get(key)
        if val in (None, "", []):
            continue
        if isinstance(val, list):
            val = ", ".join(str(v) for v in val)
        lines.append(f"{key}: {val}")
    return "\n".join(lines) or "(no event detail)"


# --- DOM extraction stubs ---------------------------------------------------


def extract_events(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Best-effort scrape of visible event chips on the current view.

    Selectors are loose — Google Calendar markup changes often. Tune the
    private helpers below as needed.
    """
    nodes = _find_event_nodes(driver)
    events: list[dict[str, Any]] = []
    for node in nodes[: max(1, limit)]:
        title = _attr_or_text(node, "aria-label") or _attr_or_text(node, "title")
        if not title:
            continue
        events.append(
            {
                "title": title.strip(),
                "when": _attr_or_text(node, "data-start-time-str") or "",
                "calendar": _attr_or_text(node, "data-calendar-id") or "",
                "location": "",
            }
        )
    return events


def extract_event_detail(driver) -> dict[str, Any]:
    """Read the event detail panel currently open. Best effort."""
    title = _text_by_selectors(driver, ["[role='heading'][aria-level='1']", "[data-text]"])
    when = _text_by_selectors(driver, ["[data-key='when']", "[aria-label*='Time']"])
    where = _text_by_selectors(driver, ["[data-key='location']", "[aria-label*='Location']"])
    desc = _text_by_selectors(driver, ["[data-key='description']", "[aria-label*='Description']"])
    return {
        "title": title,
        "when": when,
        "location": where,
        "description": desc,
        "url": getattr(driver, "current_url", "") or "",
    }


def _find_event_nodes(driver):
    selectors = [
        "[data-eventid]",
        "div[role='button'][data-eventchip]",
        "div[role='button'][aria-label][jslog]",
    ]
    for selector in selectors:
        nodes = _find_all(driver, selector)
        if nodes:
            return nodes
    return []


def _attr_or_text(node, attr: str) -> str:
    try:
        v = node.get_attribute(attr)
    except Exception:
        v = None
    if v:
        return v
    try:
        return (node.text or "").strip()
    except Exception:
        return ""


def _text_by_selectors(driver, selectors: list[str]) -> str:
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            value = el.text or el.get_attribute("aria-label") or ""
            if value:
                return value.strip()
        except Exception:
            continue
    return ""


def _find_all(driver, selector: str):
    from selenium.webdriver.common.by import By

    try:
        return driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        return []


__all__ = [
    "GCAL_HOME",
    "GCAL_HOST",
    "GCAL_RENDER",
    "VALID_VIEWS",
    "date_range_url",
    "event_create_url",
    "extract_event_detail",
    "extract_events",
    "format_compact_date",
    "format_compact_datetime",
    "format_event_detail",
    "format_events",
    "format_open_result",
    "home_url",
    "is_gcal_url",
    "parse_date",
    "parse_when",
    "search_url",
    "view_url",
]

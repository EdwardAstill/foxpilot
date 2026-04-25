"""Service layer for UWA Blackboard Ultra (lms.uwa.edu.au) browser workflows.

Blackboard Ultra is a React-rendered SPA with mostly fragile class names.
This module exposes URL helpers, formatters, and DOM extraction stubs that
target stable-ish hooks (`data-testid`, `[role='grid']`, `aria-label`).

Selenium imports are local-to-function so this module imports cleanly in a
test environment without a browser installed.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional


LMS_HOST = "lms.uwa.edu.au"
LMS_BASE = f"https://{LMS_HOST}/ultra"
LMS_HOME = f"{LMS_BASE}/stream"

SECTION_PATHS: dict[str, str] = {
    "stream": "/ultra/stream",
    "courses": "/ultra/course",
    "course": "/ultra/course",
    "calendar": "/ultra/calendar",
    "grades": "/ultra/grades",
    "messages": "/ultra/messages",
}

# Keep limit / name validators conservative so service tests stay deterministic.
COURSE_ID_RE = re.compile(r"^[A-Za-z0-9._\- ]{1,128}$")
ASSIGNMENT_NAME_RE = re.compile(r"^[A-Za-z0-9._\-:#&()/, ]{1,200}$")


def is_lms_url(value: str) -> bool:
    """Return True when `value` is a UWA LMS URL Foxpilot understands."""
    if not value:
        return False
    parsed = _parse_url(value)
    host = (parsed.netloc or "").lower()
    return host == LMS_HOST or host.endswith(".lms.uwa.edu.au")


def is_sso_redirect_url(value: str) -> bool:
    """Return True when the URL looks like a UWA Pheme SSO interstitial."""
    if not value:
        return False
    parsed = _parse_url(value)
    host = (parsed.netloc or "").lower()
    return "auth.uwa.edu.au" in host or "sso.uwa.edu.au" in host


def build_lms_url(section: Optional[str] = None) -> str:
    """Build a canonical LMS URL for a known section, or LMS_HOME by default."""
    if section is None or section == "":
        return LMS_HOME
    key = section.strip().lower()
    if key not in SECTION_PATHS:
        raise ValueError(
            f"unknown lms section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTION_PATHS))})"
        )
    return f"https://{LMS_HOST}{SECTION_PATHS[key]}"


def normalize_section(value: Optional[str]) -> str:
    """Normalize a user-supplied section name; raises ValueError if invalid."""
    if value is None or value == "":
        return "stream"
    key = value.strip().lower()
    if key not in SECTION_PATHS:
        raise ValueError(
            f"unknown lms section: {value!r} "
            f"(expected one of: {', '.join(sorted(SECTION_PATHS))})"
        )
    return key


def normalize_course_id(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned or not COURSE_ID_RE.match(cleaned):
        raise ValueError(
            f"invalid course id-or-name: {value!r} "
            "(letters, digits, spaces, '.', '_', '-' only; max 128 chars)"
        )
    return cleaned


def normalize_assignment_name(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned or not ASSIGNMENT_NAME_RE.match(cleaned):
        raise ValueError(
            f"invalid assignment name: {value!r} "
            "(letters, digits, spaces, and common punctuation only; max 200 chars)"
        )
    return cleaned


def course_search_url(query: str) -> str:
    """Build a course-list URL with a search query parameter."""
    encoded = urllib.parse.urlencode({"query": query})
    return f"https://{LMS_HOST}/ultra/course?{encoded}"


# ---------- formatters ----------


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"section: {data.get('section', '')}",
        ]
    )


def format_stream(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no stream items found)"
    lines: list[str] = []
    for i, item in enumerate(items, 1):
        title = item.get("title") or "(no title)"
        lines.append(f"[{i}] {title}")
        for key in ("course", "kind", "timestamp", "url"):
            value = item.get(key)
            if value:
                if key == "url":
                    lines.append(f"    {value}")
                else:
                    lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_courses(courses: list[dict[str, Any]]) -> str:
    if not courses:
        return "(no courses found)"
    lines = []
    for c in courses:
        code = c.get("code") or ""
        title = c.get("title") or "(no title)"
        term = c.get("term") or ""
        prefix = f"{code} " if code else ""
        suffix = f" [{term}]" if term else ""
        lines.append(f"{prefix}{title}{suffix}")
        url = c.get("url")
        if url:
            lines.append(f"    {url}")
    return "\n".join(lines)


def format_assignments(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no assignments found)"
    lines = []
    for a in items:
        name = a.get("name") or "(no name)"
        course = a.get("course") or ""
        due = a.get("due") or ""
        status = a.get("status") or ""
        bits = [name]
        if course:
            bits.append(f"course={course}")
        if due:
            bits.append(f"due={due}")
        if status:
            bits.append(f"status={status}")
        lines.append("  ".join(bits))
    return "\n".join(lines)


def format_grades(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no grade items found)"
    lines = []
    for g in items:
        name = g.get("name") or "(no name)"
        score = g.get("score") or ""
        weight = g.get("weight") or ""
        posted = g.get("posted_at") or ""
        bits = [name]
        if score:
            bits.append(f"score={score}")
        if weight:
            bits.append(f"weight={weight}")
        if posted:
            bits.append(f"posted={posted}")
        lines.append("  ".join(bits))
    return "\n".join(lines)


def format_announcements(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no announcements found)"
    lines = []
    for a in items:
        title = a.get("title") or "(no title)"
        course = a.get("course") or ""
        posted = a.get("posted_at") or ""
        lines.append(f"{title}")
        meta_bits = []
        if course:
            meta_bits.append(f"course: {course}")
        if posted:
            meta_bits.append(f"posted: {posted}")
        if meta_bits:
            lines.append("    " + "  ".join(meta_bits))
    return "\n".join(lines)


# ---------- DOM extraction stubs ----------
# These target Ultra's React markup. Selectors are best-effort and live in
# clearly named private helpers so a single edit re-tunes them.


def extract_stream_items(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Pull recent stream cards from /ultra/stream. Best-effort."""
    items: list[dict[str, Any]] = []
    for node in _find_stream_items(driver):
        if len(items) >= limit:
            break
        title = _node_text(node, "[data-testid='stream-item-title'], h3, h4, .title")
        course = _node_text(node, "[data-testid='stream-item-course'], .course-name, .course")
        kind = _node_text(node, "[data-testid='stream-item-kind'], .kind, .stream-item-kind")
        ts = _node_text(node, "[data-testid='stream-item-timestamp'], time, .timestamp")
        url = _node_attr(node, "a", "href")
        if not title and not course:
            continue
        items.append(
            {
                "title": title,
                "course": course,
                "kind": kind,
                "timestamp": ts,
                "url": url,
            }
        )
    return items


def extract_courses(driver) -> list[dict[str, Any]]:
    """Pull enrolled course cards from /ultra/course. Best-effort.

    Blackboard Ultra renders course cards with an AngularJS directive whose
    data binding sometimes resolves to empty strings on the client (cards show
    "More info for undefined" and `data-course-id=""`). When the cards-on-page
    extraction returns nothing, fall back to navigating to /ultra/messages
    and scraping the per-course thread headers, which carry the unit code +
    title in a stable text format like:

        ID: GENG5514_SEM-1_2026
        & GENG5511_SEM-1_2026 Engineering Research Project Part 1 SEM-1 2026
        Finite Element Method SEM-1 2026
    """
    courses: list[dict[str, Any]] = []
    for node in _find_course_cards(driver):
        title = _node_text(node, "[data-testid='course-title'], .course-title, h3, h4")
        code = _node_text(node, "[data-testid='course-code'], .course-code, .code")
        term = _node_text(node, "[data-testid='course-term'], .term, .course-term")
        url = _node_attr(node, "a", "href")
        if not (title or code):
            continue
        courses.append({"title": title, "code": code, "term": term, "url": url})
    if courses:
        return courses
    return _extract_courses_from_messages(driver)


def _extract_courses_from_messages(driver) -> list[dict[str, Any]]:
    """Fallback: parse /ultra/messages thread headers for unit codes + titles."""
    import re
    current = (driver.current_url or "").rstrip("/")
    if not current.endswith("/ultra/messages"):
        try:
            driver.get("https://lms.uwa.edu.au/ultra/messages")
        except Exception:
            return []

    text = ""
    try:
        from selenium.webdriver.support.ui import WebDriverWait

        def _has_ids(d) -> bool:
            try:
                body = d.execute_script("return document.body.innerText || '';") or ""
            except Exception:
                return False
            return "ID:" in body

        WebDriverWait(driver, 15).until(_has_ids)
        text = driver.execute_script("return document.body.innerText || '';") or ""
    except Exception:
        try:
            text = driver.execute_script("return document.body.innerText || '';") or ""
        except Exception:
            return []
    if "ID:" not in text:
        return []

    courses: list[dict[str, Any]] = []
    seen: set[str] = set()
    id_re = re.compile(r"ID:\s*([A-Z]{3,5}\d{3,5}(?:_[A-Z0-9-]+)+)")
    lines = [line.rstrip() for line in text.splitlines()]
    for idx, line in enumerate(lines):
        match = id_re.search(line)
        if not match:
            continue
        raw_id = match.group(1)
        unit_code = raw_id.split("_", 1)[0]
        if unit_code in seen:
            continue
        seen.add(unit_code)
        term = ""
        title = ""
        # Look ahead for sibling code (combined offerings) and title line.
        ahead = lines[idx + 1 : idx + 4]
        for sibling in ahead:
            if "_" in sibling and "SEM" in sibling and not title:
                # Combined-offering header like:
                # "& GENG5511_SEM-1_2026 Engineering Research Project Part 1 SEM-1 2026"
                stripped = sibling.lstrip("& ").strip()
                # Drop leading sibling code, keep title up to trailing term.
                pieces = stripped.split(" ", 1)
                title_candidate = pieces[1] if len(pieces) == 2 else stripped
                title_candidate = re.sub(
                    r"\s+SEM-\d(?:[A-Z]+)?[\s_-]\d{4}\s*$", "", title_candidate
                ).strip()
                if title_candidate:
                    title = title_candidate
            elif sibling and not title and "unread" not in sibling.lower():
                title = re.sub(
                    r"\s+SEM-\d(?:[A-Z]+)?[\s_-]\d{4}\s*$", "", sibling
                ).strip()
        term_match = re.search(r"SEM-\d(?:[A-Z]+)?[\s_-]\d{4}", raw_id)
        if term_match:
            term = term_match.group(0).replace("_", "-").replace(" ", "-")
        courses.append(
            {
                "title": title,
                "code": unit_code,
                "term": term,
                "url": "",
                "source": "messages",
            }
        )
    return courses


def extract_assignments(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Pull assignment rows from a course or global assignments list."""
    rows: list[dict[str, Any]] = []
    for node in _find_assignment_rows(driver):
        if len(rows) >= limit:
            break
        name = _node_text(node, "[data-testid='assignment-name'], .name, h3, h4")
        course = _node_text(node, "[data-testid='assignment-course'], .course")
        due = _node_text(node, "[data-testid='assignment-due'], .due-date, time")
        status = _node_text(node, "[data-testid='assignment-status'], .status")
        if not name:
            continue
        rows.append({"name": name, "course": course, "due": due, "status": status})
    return rows


def extract_grades(driver) -> list[dict[str, Any]]:
    """Pull grade rows from /ultra/grades or a course grades surface."""
    rows: list[dict[str, Any]] = []
    for node in _find_grade_rows(driver):
        name = _node_text(node, "[data-testid='grade-name'], .name, .grade-name")
        score = _node_text(node, "[data-testid='grade-score'], .score, .grade-score")
        weight = _node_text(node, "[data-testid='grade-weight'], .weight")
        posted = _node_text(node, "[data-testid='grade-posted'], .posted-at, time")
        if not name and not score:
            continue
        rows.append(
            {"name": name, "score": score, "weight": weight, "posted_at": posted}
        )
    return rows


def extract_announcements(driver, limit: int = 20) -> list[dict[str, Any]]:
    """Pull announcement entries. Best-effort."""
    items: list[dict[str, Any]] = []
    for node in _find_announcement_rows(driver):
        if len(items) >= limit:
            break
        title = _node_text(node, "[data-testid='announcement-title'], h3, h4, .title")
        course = _node_text(node, "[data-testid='announcement-course'], .course")
        posted = _node_text(node, "[data-testid='announcement-posted'], time, .posted-at")
        if not title:
            continue
        items.append({"title": title, "course": course, "posted_at": posted})
    return items


# ---------- private DOM-fragile finders (one-edit tuning targets) ----------


def _find_stream_items(driver):
    return _find_all_first_match(
        driver,
        [
            "[data-testid='stream-item']",
            ".stream-item",
            "[role='listitem'] article",
        ],
    )


def _find_course_cards(driver):
    return _find_all_first_match(
        driver,
        [
            "[data-testid='course-link']",
            ".js-course-card",
            ".course-card",
            "[data-analytics-id='course-card']",
        ],
    )


def _find_assignment_rows(driver):
    return _find_all_first_match(
        driver,
        [
            "[data-testid='assignment-row']",
            ".assignment-row",
            "[role='grid'] [role='row']",
        ],
    )


def _find_grade_rows(driver):
    return _find_all_first_match(
        driver,
        [
            "[data-testid='grade-row']",
            "[role='grid'] [role='row']",
            ".grade-row",
        ],
    )


def _find_announcement_rows(driver):
    return _find_all_first_match(
        driver,
        [
            "[data-testid='announcement-item']",
            ".announcement-item",
            "[role='listitem'] article",
        ],
    )


# ---------- low-level helpers ----------


def _find_all_first_match(driver, selectors: list[str]):
    from selenium.webdriver.common.by import By

    for selector in selectors:
        try:
            nodes = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        if nodes:
            return nodes
    return []


def _node_text(node, selector: str) -> str:
    from selenium.webdriver.common.by import By

    for part in [s.strip() for s in selector.split(",") if s.strip()]:
        try:
            child = node.find_element(By.CSS_SELECTOR, part)
        except Exception:
            continue
        text = (child.text or "").strip()
        if text:
            return text
    return ""


def _node_attr(node, selector: str, attr: str) -> str:
    from selenium.webdriver.common.by import By

    try:
        child = node.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return ""
    return child.get_attribute(attr) or ""


def _parse_url(value: str) -> urllib.parse.ParseResult:
    value = (value or "").strip()
    if value.startswith("www."):
        value = "https://" + value
    return urllib.parse.urlparse(value)


__all__ = [
    "LMS_HOST",
    "LMS_BASE",
    "LMS_HOME",
    "SECTION_PATHS",
    "build_lms_url",
    "course_search_url",
    "extract_announcements",
    "extract_assignments",
    "extract_courses",
    "extract_grades",
    "extract_stream_items",
    "format_announcements",
    "format_assignments",
    "format_courses",
    "format_grades",
    "format_open_result",
    "format_stream",
    "is_lms_url",
    "is_sso_redirect_url",
    "normalize_assignment_name",
    "normalize_course_id",
    "normalize_section",
]

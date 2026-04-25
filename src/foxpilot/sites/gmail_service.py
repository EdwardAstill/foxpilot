"""Service layer for Gmail (mail.google.com) browser workflows.

Gmail uses dynamic class names heavily, so this layer routes lookups through
stable hooks like `[role='listitem']`, `[aria-label]`, and visible-text
matching where possible. DOM-fragile selectors live in `_find_*` helpers so
they can be retuned in one place.

Selenium is imported locally inside helpers (mirrors `excel_service.py`).
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Optional


GMAIL_HOST = "mail.google.com"
GMAIL_HOME = f"https://{GMAIL_HOST}/mail/u/0/#inbox"
GMAIL_ORIGIN = f"https://{GMAIL_HOST}/"

# Common Gmail "system" labels mapped to URL fragments.
GMAIL_LABELS = {
    "inbox": "#inbox",
    "starred": "#starred",
    "snoozed": "#snoozed",
    "important": "#imp",
    "sent": "#sent",
    "drafts": "#drafts",
    "scheduled": "#scheduled",
    "all": "#all",
    "spam": "#spam",
    "trash": "#trash",
    "chats": "#chats",
}

THREAD_ID_RE = re.compile(r"^[A-Za-z0-9]{8,}$")


def is_gmail_url(value: str) -> bool:
    """Return True when value looks like a Gmail URL."""
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host == GMAIL_HOST or host.endswith(".mail.google.com")


def home_url() -> str:
    return GMAIL_HOME


def label_url(label: Optional[str]) -> str:
    """Resolve a label name to a Gmail navigation URL.

    Known system labels map to their fragment; anything else is treated as a
    user label via `#label/<name>`.
    """
    if not label:
        return GMAIL_HOME
    key = label.strip().lower()
    if not key:
        return GMAIL_HOME
    base = f"https://{GMAIL_HOST}/mail/u/0/"
    if key in GMAIL_LABELS:
        return base + GMAIL_LABELS[key]
    # Preserve user-supplied case for nested labels (e.g. "Work/Reports").
    encoded = urllib.parse.quote(label.strip(), safe="/")
    return f"{base}#label/{encoded}"


def build_gmail_search_url(query: str) -> str:
    """Build a Gmail URL that runs a search using the `#search/` fragment."""
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("search query must not be empty")
    encoded = urllib.parse.quote(cleaned, safe="")
    return f"https://{GMAIL_HOST}/mail/u/0/#search/{encoded}"


def normalize_thread_id(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("thread id must not be empty")
    return cleaned


def looks_like_thread_id(value: str) -> bool:
    return bool(THREAD_ID_RE.match((value or "").strip()))


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"label: {data.get('label', '')}",
        ]
    )


def format_message_list(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "(no messages found)"
    lines: list[str] = []
    for i, msg in enumerate(messages, 1):
        sender = msg.get("from") or "(unknown)"
        subject = msg.get("subject") or "(no subject)"
        snippet = msg.get("snippet") or ""
        age = msg.get("age") or ""
        unread_mark = "*" if msg.get("unread") else " "
        lines.append(f"{unread_mark}[{i}] {sender} — {subject}")
        if snippet:
            lines.append(f"    {snippet}")
        if age:
            lines.append(f"    age: {age}")
        if msg.get("id"):
            lines.append(f"    id: {msg['id']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_message_detail(message: dict[str, Any]) -> str:
    headers = message.get("headers") or {}
    lines = [
        f"subject: {message.get('subject', '')}",
        f"from: {headers.get('from', message.get('from', ''))}",
        f"to: {headers.get('to', '')}",
        f"date: {headers.get('date', message.get('date', ''))}",
        f"url: {message.get('url', '')}",
        "",
        message.get("body", ""),
    ]
    return "\n".join(lines)


def format_compose_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"compose: {data.get('state', 'open')}",
            f"to: {data.get('to', '')}",
            f"subject: {data.get('subject', '')}",
            f"body_chars: {len(data.get('body', '') or '')}",
        ]
    )


def format_action_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"action: {data.get('action', '')}",
            f"target: {data.get('target', '')}",
            f"result: {data.get('result', '')}",
        ]
    )


# ---------------------------------------------------------------------------
# DOM extraction stubs (best-effort; tune selectors here as Gmail evolves)
# ---------------------------------------------------------------------------


def extract_message_rows(driver, limit: int = 25, unread_only: bool = False) -> list[dict[str, Any]]:
    """List visible message rows in the current Gmail list view."""
    rows = _find_message_rows(driver)
    out: list[dict[str, Any]] = []
    for row in rows:
        if len(out) >= limit:
            break
        try:
            if not row.is_displayed():
                continue
        except Exception:
            continue
        record = _row_to_record(row)
        if unread_only and not record.get("unread"):
            continue
        if not record.get("subject") and not record.get("from"):
            continue
        out.append(record)
    return out


def extract_open_message(driver) -> dict[str, Any]:
    """Read headers + body of the currently open message thread."""
    headers = _read_open_message_headers(driver)
    body = _read_open_message_body(driver)
    subject = headers.get("subject") or _read_open_subject(driver)
    return {
        "subject": subject,
        "from": headers.get("from", ""),
        "date": headers.get("date", ""),
        "headers": headers,
        "body": body,
        "url": getattr(driver, "current_url", ""),
    }


def fill_compose(driver, to: str, subject: str, body: str) -> dict[str, Any]:
    """Open a Gmail compose pane and fill the To / Subject / Body fields."""
    _open_compose(driver)
    _fill_field(driver, _find_compose_to, to)
    _fill_field(driver, _find_compose_subject, subject)
    _fill_field(driver, _find_compose_body, body)
    return {"state": "filled", "to": to, "subject": subject, "body": body}


def click_send(driver) -> dict[str, Any]:
    """Click the Send button on the currently open compose pane."""
    btn = _find_compose_send(driver)
    if btn is None:
        raise RuntimeError("could not find Send button in compose pane")
    btn.click()
    return {"action": "send", "target": "compose", "result": "clicked"}


def apply_thread_action(driver, action: str, target: str) -> dict[str, Any]:
    """Apply archive / delete / star to a thread by id, subject or current view."""
    if action not in {"archive", "delete", "star"}:
        raise ValueError(f"unknown thread action: {action!r}")
    btn = _find_thread_action_button(driver, action)
    if btn is None:
        raise RuntimeError(f"could not find Gmail toolbar button for {action!r}")
    btn.click()
    return {"action": action, "target": target, "result": "clicked"}


# ---------------------------------------------------------------------------
# Private DOM helpers — the brittle stuff lives below this line
# ---------------------------------------------------------------------------


def _row_to_record(row) -> dict[str, Any]:
    aria = (row.get_attribute("aria-label") or "").strip()
    text = (row.text or "").strip()
    record: dict[str, Any] = {
        "id": row.get_attribute("data-thread-id") or row.get_attribute("id") or "",
        "from": _row_field(row, ["[email]", "span[name]", ".yW span", ".zF"]),
        "subject": _row_field(row, [".bog", ".y6 span", "[data-thread-id] span"]),
        "snippet": _row_field(row, [".y2", ".bog + .y2"]),
        "age": _row_field(row, [".xW span", ".xY span"]),
        "unread": _row_is_unread(row),
        "aria": aria,
        "text": text,
    }
    return record


def _row_field(row, selectors: list[str]) -> str:
    from selenium.webdriver.common.by import By
    for sel in selectors:
        try:
            el = row.find_element(By.CSS_SELECTOR, sel)
        except Exception:
            continue
        value = (el.get_attribute("title") or el.text or "").strip()
        if value:
            return value
    return ""


def _row_is_unread(row) -> bool:
    cls = (row.get_attribute("class") or "").lower()
    if "zE" in (row.get_attribute("class") or ""):
        return True
    return "unread" in cls or "zE" in cls


def _find_message_rows(driver):
    selectors = [
        "tr.zA",  # Gmail's list row
        "[role='main'] [role='listitem']",
        "[role='list'] [role='listitem']",
    ]
    for sel in selectors:
        rows = _find_all(driver, sel)
        if rows:
            return rows
    return []


def _read_open_subject(driver) -> str:
    return _first_text(driver, ["h2.hP", "[data-thread-perm-id] h2"])


def _read_open_message_headers(driver) -> dict[str, str]:
    headers: dict[str, str] = {}
    headers["subject"] = _read_open_subject(driver)
    headers["from"] = _first_text(
        driver,
        [
            "[role='main'] .gD",
            "[role='main'] span[email]",
        ],
    )
    headers["date"] = _first_text(
        driver,
        [
            "[role='main'] .g3",
            "[role='main'] [aria-label*='at']",
        ],
    )
    headers["to"] = _first_text(
        driver,
        [
            "[role='main'] .hb",
            "[role='main'] [aria-label*='To']",
        ],
    )
    return headers


def _read_open_message_body(driver) -> str:
    selectors = [
        "[role='main'] .a3s.aiL",
        "[role='main'] div.ii.gt",
        "[role='main'] .adP",
    ]
    for sel in selectors:
        el = _find_one(driver, sel)
        if el is not None:
            text = (el.text or "").strip()
            if text:
                return text
    return ""


def _open_compose(driver) -> None:
    btn = _find_compose_button(driver)
    if btn is None:
        raise RuntimeError("could not find Gmail Compose button")
    btn.click()


def _fill_field(driver, finder, value: str) -> None:
    if value is None:
        return
    el = finder(driver)
    if el is None:
        raise RuntimeError("compose field not found")
    el.click()
    try:
        el.clear()
    except Exception:
        pass
    el.send_keys(value)


def _find_compose_button(driver):
    return _first_element(
        driver,
        [
            "div[gh='cm']",
            "div[role='button'][aria-label*='Compose']",
            "[aria-label='Compose']",
        ],
    )


def _find_compose_to(driver):
    return _first_element(
        driver,
        [
            "textarea[name='to']",
            "input[name='to']",
            "[aria-label='To recipients'] input",
            "[aria-label='To'] input",
        ],
    )


def _find_compose_subject(driver):
    return _first_element(
        driver,
        [
            "input[name='subjectbox']",
            "[aria-label='Subject']",
        ],
    )


def _find_compose_body(driver):
    return _first_element(
        driver,
        [
            "div[aria-label='Message Body']",
            "div[role='textbox'][aria-label*='Body']",
            "div[g_editable='true']",
        ],
    )


def _find_compose_send(driver):
    return _first_element(
        driver,
        [
            "div[role='button'][data-tooltip*='Send']",
            "div[aria-label*='Send'][role='button']",
            "[aria-label^='Send']",
        ],
    )


def _find_thread_action_button(driver, action: str):
    aria_map = {
        "archive": ["Archive"],
        "delete": ["Delete", "Move to Trash"],
        "star": ["Star", "Starred"],
    }
    labels = aria_map.get(action, [])
    selectors: list[str] = []
    for label in labels:
        selectors.extend(
            [
                f"div[role='button'][aria-label='{label}']",
                f"div[role='button'][data-tooltip='{label}']",
                f"[aria-label='{label}']",
            ]
        )
    return _first_element(driver, selectors)


# ---- low-level selenium wrappers -------------------------------------------


def _find_one(driver, selector: str):
    from selenium.webdriver.common.by import By
    try:
        return driver.find_element(By.CSS_SELECTOR, selector)
    except Exception:
        return None


def _find_all(driver, selector: str):
    from selenium.webdriver.common.by import By
    try:
        return driver.find_elements(By.CSS_SELECTOR, selector)
    except Exception:
        return []


def _first_element(driver, selectors: list[str]):
    for sel in selectors:
        el = _find_one(driver, sel)
        if el is not None:
            return el
    return None


def _first_text(driver, selectors: list[str]) -> str:
    el = _first_element(driver, selectors)
    if el is None:
        return ""
    return (el.text or "").strip()


__all__ = [
    "GMAIL_HOME",
    "GMAIL_HOST",
    "GMAIL_LABELS",
    "GMAIL_ORIGIN",
    "apply_thread_action",
    "build_gmail_search_url",
    "click_send",
    "extract_message_rows",
    "extract_open_message",
    "fill_compose",
    "format_action_result",
    "format_compose_result",
    "format_message_detail",
    "format_message_list",
    "format_open_result",
    "home_url",
    "is_gmail_url",
    "label_url",
    "looks_like_thread_id",
    "normalize_thread_id",
]

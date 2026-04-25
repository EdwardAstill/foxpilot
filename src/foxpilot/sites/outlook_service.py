"""Service layer for Microsoft 365 Outlook on the web.

URL helpers for the Outlook on the web folder views, calendar, search, and
DOM extraction stubs. Browser automation lives in `outlook.py`; this module
stays import-cheap and unit-testable.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Iterable, Literal, Optional


OUTLOOK_HOST = "outlook.office.com"
OUTLOOK_MAIL_HOME = f"https://{OUTLOOK_HOST}/mail/"
OUTLOOK_CALENDAR_HOME = f"https://{OUTLOOK_HOST}/calendar/"

Folder = Literal["inbox", "sent", "drafts", "archive"]

OUTLOOK_FOLDERS: dict[str, str] = {
    "inbox": "inbox",
    "sent": "sentitems",
    "drafts": "drafts",
    "archive": "archive",
}

_FOLDER_ALIASES: dict[str, str] = {
    "in": "inbox",
    "incoming": "inbox",
    "sent-items": "sent",
    "sentitems": "sent",
    "outbox": "sent",
    "draft": "drafts",
    "archived": "archive",
}


def normalize_folder(folder: str) -> Folder:
    value = (folder or "inbox").strip().lower()
    value = _FOLDER_ALIASES.get(value, value)
    if value not in OUTLOOK_FOLDERS:
        expected = ", ".join(sorted(OUTLOOK_FOLDERS))
        raise ValueError(f"unknown Outlook folder '{folder}' (expected: {expected})")
    return value  # type: ignore[return-value]


def build_folder_url(folder: str = "inbox") -> str:
    """Return the Outlook on the web URL for a high-level mail folder."""
    normalized = normalize_folder(folder)
    segment = OUTLOOK_FOLDERS[normalized]
    return f"{OUTLOOK_MAIL_HOME}{segment}"


def build_search_url(query: str, folder: str = "inbox") -> str:
    """Return the Outlook search URL for a folder + query string."""
    if not (query or "").strip():
        raise ValueError("search query is empty")
    normalized = normalize_folder(folder)
    segment = OUTLOOK_FOLDERS[normalized]
    encoded = urllib.parse.quote(query.strip())
    return f"{OUTLOOK_MAIL_HOME}{segment}/search/query={encoded}"


def build_calendar_url(view: str = "week") -> str:
    """Return the Outlook calendar URL for a view (day/week/month/workweek)."""
    value = (view or "week").strip().lower()
    valid = {"day", "week", "workweek", "month"}
    if value not in valid:
        expected = ", ".join(sorted(valid))
        raise ValueError(f"unknown calendar view '{view}' (expected: {expected})")
    return f"{OUTLOOK_CALENDAR_HOME}view/{value}"


def is_outlook_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(_ensure_url_scheme(value))
    host = (parsed.netloc or "").lower()
    return host.endswith("outlook.office.com") or host.endswith("outlook.office365.com") or host.endswith("outlook.live.com")


def normalize_outlook_target(target: str) -> str:
    """Resolve a folder name or URL to a navigable Outlook URL."""
    value = (target or "inbox").strip()
    if "://" in value or "." in value.split("/", 1)[0]:
        url = _ensure_url_scheme(value)
        if not is_outlook_url(url):
            raise ValueError(f"not an Outlook URL: {target}")
        return url
    return build_folder_url(value)


def format_open_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("title", "url", "folder", "view"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_messages(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No Outlook messages found."
    lines: list[str] = []
    for index, item in enumerate(items, 1):
        unread_marker = "*" if item.get("unread") else " "
        subject = item.get("subject") or "(no subject)"
        sender = item.get("from") or item.get("sender") or ""
        lines.append(f"{unread_marker} [{index}] {subject}")
        for key in ("from", "received", "snippet"):
            value = item.get(key)
            if value:
                lines.append(f"      {key}: {value}")
        lines.append("")
    if sender:
        pass
    return "\n".join(lines).rstrip()


def format_message_detail(data: dict[str, Any]) -> str:
    lines = []
    for key in ("subject", "from", "to", "cc", "received", "url"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    body = data.get("body")
    if body:
        lines.append("")
        lines.append(str(body))
    return "\n".join(lines)


def format_calendar(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No Outlook calendar events found."
    lines: list[str] = []
    for index, event in enumerate(events, 1):
        title = event.get("title") or "(untitled event)"
        lines.append(f"[{index}] {title}")
        for key in ("when", "start", "end", "location", "organizer"):
            value = event.get(key)
            if value:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_compose_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("status", "to", "cc", "bcc", "subject", "url"):
        value = data.get(key)
        if value not in (None, "", []):
            if isinstance(value, list):
                value = ", ".join(value)
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_send_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("status", "subject", "to", "url"):
        value = data.get(key)
        if value not in (None, "", []):
            if isinstance(value, list):
                value = ", ".join(value)
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def parse_recipients(raw: Optional[str]) -> list[str]:
    """Split a comma/semicolon-separated recipient list into trimmed entries."""
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        cleaned = chunk.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


# --- DOM extraction stubs (selectors are best-effort, easy to retune) -------

_MESSAGE_ROW_SELECTOR = "div[role='option']"
_READING_PANE_SELECTOR = "[aria-label='Reading pane']"


def extract_messages(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract visible Outlook message rows (best-effort)."""
    items = driver.execute_script(_MESSAGES_SCRIPT, limit)
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def extract_reading_pane(driver) -> dict[str, Any]:
    """Extract subject/from/body of the message in the Reading pane."""
    data = driver.execute_script(_READING_PANE_SCRIPT)
    if not isinstance(data, dict):
        return {}
    return data


def extract_calendar_events(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract visible Outlook calendar events (best-effort)."""
    items = driver.execute_script(_CALENDAR_SCRIPT, limit)
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _ensure_url_scheme(value: str) -> str:
    return value if "://" in value else f"https://{value}"


_MESSAGES_SCRIPT = r"""
const limit = Number(arguments[arguments.length - 1]) || 50;
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const visible = (el) => {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden') return false;
  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
};
const rows = Array.from(document.querySelectorAll("div[role='option']")).filter(visible);
const items = [];
for (const row of rows) {
  if (items.length >= limit) break;
  const label = clean(row.getAttribute('aria-label') || '');
  const text = clean(row.innerText || row.textContent || label);
  const subjectEl = row.querySelector("[id*='subject'], [class*='Subject'], span[role='heading']");
  const senderEl = row.querySelector("[class*='From'], [id*='sender']");
  const subject = clean(subjectEl?.innerText || subjectEl?.textContent || '') || text.split('\n')[0] || label;
  const sender = clean(senderEl?.innerText || senderEl?.textContent || '');
  const unread = row.getAttribute('aria-selected') === 'false' && /unread/i.test(label);
  items.push({
    subject,
    from: sender,
    snippet: text,
    received: '',
    unread,
    aria_label: label,
  });
}
return items;
"""


_READING_PANE_SCRIPT = r"""
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const pane = document.querySelector("[aria-label='Reading pane']") || document.querySelector("[role='main']");
if (!pane) return {};
const subjectEl = pane.querySelector("div[role='heading'], h1, [class*='subject' i]");
const fromEl = pane.querySelector("[class*='From' i] a, [class*='sender' i]");
const bodyEl = pane.querySelector("[aria-label='Message body'], div[role='document'], [class*='ReadingPaneBody' i]");
return {
  subject: clean(subjectEl?.innerText || subjectEl?.textContent || ''),
  from: clean(fromEl?.innerText || fromEl?.textContent || ''),
  body: clean(bodyEl?.innerText || bodyEl?.textContent || pane.innerText || ''),
  url: location.href,
};
"""


_CALENDAR_SCRIPT = r"""
const limit = Number(arguments[arguments.length - 1]) || 50;
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const visible = (el) => {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden') return false;
  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
};
const cells = Array.from(document.querySelectorAll("[role='button'][aria-label], [role='gridcell'][aria-label]"))
  .filter(visible)
  .filter((el) => /(\d{1,2}:\d{2}|AM|PM)/i.test(el.getAttribute('aria-label') || ''));
const items = [];
const seen = new Set();
for (const cell of cells) {
  if (items.length >= limit) break;
  const label = clean(cell.getAttribute('aria-label'));
  if (!label || seen.has(label)) continue;
  seen.add(label);
  items.push({
    title: label.split(',')[0] || label,
    when: label,
    location: '',
    organizer: '',
  });
}
return items;
"""

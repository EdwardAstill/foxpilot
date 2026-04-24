"""OneDrive Online URL, formatting, and browser extraction helpers."""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Literal, Optional


Account = Literal["personal", "work"]
View = Literal["home", "files", "recent", "shared", "photos", "recycle"]

ONEDRIVE_PERSONAL_URL = "https://onedrive.live.com/"
ONEDRIVE_WORK_URL = "https://www.microsoft365.com/onedrive"

ONEDRIVE_VIEWS: dict[str, str] = {
    "home": "",
    "files": "files",
    "recent": "recent",
    "shared": "shared",
    "photos": "photos",
    "recycle": "recyclebin",
}

_VIEW_ALIASES = {
    "my-files": "files",
    "myfiles": "files",
    "root": "files",
    "all": "files",
    "photo": "photos",
    "pictures": "photos",
    "recycle-bin": "recycle",
    "recyclebin": "recycle",
    "trash": "recycle",
    "deleted": "recycle",
}

_ACCOUNT_ALIASES = {
    "personal": "personal",
    "consumer": "personal",
    "live": "personal",
    "work": "work",
    "business": "work",
    "school": "work",
    "m365": "work",
    "office": "work",
}


def normalize_account(account: str) -> Account:
    value = (account or "personal").strip().lower()
    normalized = _ACCOUNT_ALIASES.get(value)
    if normalized not in {"personal", "work"}:
        expected = ", ".join(sorted(_ACCOUNT_ALIASES))
        raise ValueError(f"unknown OneDrive account '{account}' (expected: {expected})")
    return normalized  # type: ignore[return-value]


def normalize_view(view: str) -> View:
    value = (view or "home").strip().lower()
    value = _VIEW_ALIASES.get(value, value)
    if value not in ONEDRIVE_VIEWS:
        expected = ", ".join(sorted(ONEDRIVE_VIEWS))
        raise ValueError(f"unknown OneDrive view '{view}' (expected: {expected})")
    return value  # type: ignore[return-value]


def build_onedrive_url(view: str = "home", account: str = "personal") -> str:
    """Build a stable OneDrive landing URL for a high-level view."""
    normalized_account = normalize_account(account)
    normalized_view = normalize_view(view)
    if normalized_account == "work":
        return ONEDRIVE_WORK_URL

    target = ONEDRIVE_VIEWS[normalized_view]
    if not target:
        return ONEDRIVE_PERSONAL_URL
    return f"{ONEDRIVE_PERSONAL_URL}?v={urllib.parse.quote(target)}"


def is_onedrive_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(_ensure_url_scheme(value))
    host = parsed.netloc.lower()
    return host in {
        "onedrive.live.com",
        "www.onedrive.com",
        "onedrive.com",
        "www.microsoft365.com",
        "microsoft365.com",
        "office.com",
        "www.office.com",
    } or host.endswith("-my.sharepoint.com")


def normalize_onedrive_target(target: str, account: str = "personal") -> str:
    """Return a navigable OneDrive URL from a URL or high-level view name."""
    value = (target or "home").strip()
    if _looks_like_url(value):
        url = _ensure_url_scheme(value)
        if not is_onedrive_url(url):
            raise ValueError(f"not a OneDrive URL: {target}")
        return url
    return build_onedrive_url(value, account=account)


def format_open_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("title", "name", "url", "view", "account"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_select_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("status", "name", "method", "url"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_download_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("status", "name", "download_dir", "url"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    files = data.get("files") or []
    if files:
        lines.append("files:")
        lines.extend(f"  - {path}" for path in files)
    return "\n".join(lines)


def format_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No OneDrive items found."

    lines: list[str] = []
    for index, item in enumerate(items, 1):
        lines.append(f"[{index}] {item.get('name') or '(unnamed item)'}")
        for key in ("url", "kind", "modified", "size", "shared", "owner"):
            value = item.get(key)
            if value not in (None, "", []):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_path(path: list[str]) -> str:
    if not path:
        return "(path unavailable)"
    return " / ".join(part for part in path if part)


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def extract_items(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract visible files and folders from the current OneDrive page."""
    return _list_result(driver.execute_script(_ITEMS_SCRIPT, limit))


def extract_path(driver) -> list[str]:
    """Extract the visible OneDrive breadcrumb path."""
    value = driver.execute_script(_PATH_SCRIPT)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def open_item(driver, name: str) -> dict[str, str]:
    """Open a visible OneDrive item by accessible text or label."""
    from selenium.webdriver.common.by import By

    candidates = _item_name_xpaths(name)
    for xpath in candidates:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                element.click()
                return {"name": name, "url": getattr(driver, "current_url", "")}
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    return {"name": name, "url": getattr(driver, "current_url", "")}
                except Exception:
                    continue
    raise RuntimeError(f"no visible OneDrive item matching '{name}'")


def select_item(driver, name: str) -> dict[str, Any]:
    """Select a visible OneDrive item without opening it."""
    value = driver.execute_script(_SELECT_ITEM_SCRIPT, name)
    if not isinstance(value, dict):
        raise RuntimeError(f"could not select OneDrive item '{name}'")
    if not value.get("ok"):
        message = value.get("message") or f"could not select OneDrive item '{name}'"
        raise RuntimeError(str(message))
    return {
        "status": "selected",
        "name": str(value.get("name") or name),
        "selected": bool(value.get("selected", True)),
        "method": str(value.get("method") or "unknown"),
        "url": getattr(driver, "current_url", ""),
    }


def download_selected(driver) -> dict[str, Any]:
    """Click OneDrive's visible Download action for the current selection."""
    from selenium.webdriver.common.by import By

    if _click_download_action(driver, By):
        return {"status": "started", "url": getattr(driver, "current_url", "")}

    if _click_more_actions(driver, By):
        time.sleep(0.4)
        if _click_download_action(driver, By):
            return {"status": "started", "url": getattr(driver, "current_url", "")}

    raise RuntimeError("could not find OneDrive Download action")


def snapshot_download_dir(download_dir: Path | str) -> dict[str, float]:
    """Snapshot completed files in a download directory by path and mtime."""
    directory = Path(download_dir).expanduser()
    if not directory.exists():
        return {}
    return {
        str(path): path.stat().st_mtime
        for path in directory.iterdir()
        if path.is_file() and not _is_partial_download(path)
    }


def wait_for_download(
    download_dir: Path | str,
    *,
    before: Optional[dict[str, float]] = None,
    timeout: float = 60.0,
    poll_interval: float = 0.25,
) -> dict[str, Any]:
    """Wait until a new completed file appears in the download directory."""
    directory = Path(download_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    baseline = before if before is not None else snapshot_download_dir(directory)
    deadline = time.monotonic() + max(timeout, 0)

    while True:
        files = _new_completed_downloads(directory, baseline)
        if files:
            return {
                "status": "downloaded",
                "download_dir": str(directory),
                "files": [str(path) for path in files],
            }
        if time.monotonic() >= deadline:
            raise TimeoutError(f"no completed download appeared in {directory}")
        time.sleep(max(poll_interval, 0.01))


def search_items(driver, query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search OneDrive through the web UI and return visible result items."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    search_box = _find_search_box(driver, By)
    if search_box is None:
        raise RuntimeError("could not find OneDrive search box")
    search_box.clear()
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)

    time.sleep(1.5)
    return extract_items(driver, limit=limit)


def _find_search_box(driver, by):
    selectors = [
        "input[type='search']",
        "input[aria-label*='Search' i]",
        "input[placeholder*='Search' i]",
        "[role='searchbox']",
        "[contenteditable='true'][aria-label*='Search' i]",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(by.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            try:
                if element.is_displayed():
                    return element
            except Exception:
                continue
    return None


def _click_download_action(driver, by) -> bool:
    labels = ["Download"]
    for label in labels:
        literal = _xpath_literal(label)
        xpaths = [
            f"//*[self::button or self::a or @role='button'][contains(normalize-space(.), {literal})]",
            f"//*[self::button or self::a or @role='button'][contains(@aria-label, {literal})]",
            f"//*[self::button or self::a or @role='button'][contains(@title, {literal})]",
        ]
        if _click_first_visible(driver, by, xpaths):
            return True
    return False


def _click_more_actions(driver, by) -> bool:
    labels = ["More", "More actions", "Show actions", "Actions"]
    for label in labels:
        literal = _xpath_literal(label)
        xpaths = [
            f"//*[self::button or @role='button'][normalize-space(.)={literal}]",
            f"//*[self::button or @role='button'][contains(@aria-label, {literal})]",
            f"//*[self::button or @role='button'][contains(@title, {literal})]",
        ]
        if _click_first_visible(driver, by, xpaths):
            return True
    return False


def _click_first_visible(driver, by, xpaths: list[str]) -> bool:
    for xpath in xpaths:
        try:
            elements = driver.find_elements(by.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                disabled = element.get_attribute("disabled") or element.get_attribute("aria-disabled")
                if str(disabled).lower() == "true":
                    continue
                element.click()
                return True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception:
                    continue
    return False


def _item_name_xpaths(name: str) -> list[str]:
    literal = _xpath_literal(name)
    return [
        f"//*[self::a or self::button or @role='row' or @role='gridcell' or @role='link'][contains(normalize-space(.), {literal})]",
        f"//*[contains(@aria-label, {literal})]",
        f"//*[contains(@title, {literal})]",
    ]


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


def _list_result(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _new_completed_downloads(directory: Path, before: dict[str, float]) -> list[Path]:
    if not directory.exists():
        return []
    files: list[Path] = []
    for path in directory.iterdir():
        if not path.is_file() or _is_partial_download(path):
            continue
        path_key = str(path)
        mtime = path.stat().st_mtime
        if path_key not in before or mtime > before[path_key]:
            files.append(path)
    files.sort(key=lambda item: item.stat().st_mtime)
    return files


def _is_partial_download(path: Path) -> bool:
    return path.name.endswith((".part", ".crdownload", ".tmp"))


def _looks_like_url(value: str) -> bool:
    value = value.strip()
    if not value or any(ch.isspace() for ch in value):
        return False
    return "://" in value or "." in value.split("/", 1)[0]


def _ensure_url_scheme(value: str) -> str:
    return value if "://" in value else f"https://{value}"


_COMMON_JS = r"""
const limit = Number(arguments[arguments.length - 1]) || 50;
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const visible = (el) => {
  if (!el) return false;
  const style = window.getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden') return false;
  return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
};
const closestLink = (el) => el.closest('a[href]') || el.querySelector?.('a[href]');
const inferKind = (text, label) => {
  const joined = `${text} ${label}`.toLowerCase();
  if (joined.includes('folder')) return 'folder';
  if (joined.includes('shortcut')) return 'shortcut';
  if (joined.includes('notebook')) return 'notebook';
  return 'file';
};
"""


_ITEMS_SCRIPT = _COMMON_JS + r"""
const rows = Array.from(document.querySelectorAll(
  "[role='row'], [role='listitem'], [data-automationid*='DetailsRow'], [data-testid*='row'], a[href*='onedrive'], a[href*='sharepoint']"
)).filter(visible);
const seen = new Set();
const items = [];

for (const row of rows) {
  if (items.length >= limit) break;
  const label = clean(row.getAttribute('aria-label') || row.getAttribute('title'));
  const nameEl = row.querySelector?.("[data-automationid='DetailsRowCell'], [role='gridcell'], a, button") || row;
  let name = clean(nameEl.innerText || nameEl.textContent || label);
  if (!name || name.length > 240) name = label;
  if (!name || seen.has(name)) continue;

  const link = closestLink(row);
  const text = clean(row.innerText || row.textContent);
  const modifiedMatch = text.match(/\b(today|yesterday|\d{1,2}\/\d{1,2}\/\d{2,4}|[A-Z][a-z]+ \d{1,2})\b/i);
  const sizeMatch = text.match(/\b\d+(?:\.\d+)?\s*(?:B|KB|MB|GB|TB)\b/i);
  seen.add(name);
  items.push({
    name,
    url: link ? link.href : '',
    kind: inferKind(text, label),
    modified: modifiedMatch ? modifiedMatch[0] : '',
    size: sizeMatch ? sizeMatch[0] : '',
    shared: /shared/i.test(text),
    owner: '',
  });
}

return items;
"""


_SELECT_ITEM_SCRIPT = _COMMON_JS + r"""
const target = clean(arguments[0]).toLowerCase();
const rows = Array.from(document.querySelectorAll(
  "[role='row'], [role='listitem'], [data-automationid*='DetailsRow'], [data-testid*='row']"
)).filter(visible);

const matches = (row) => {
  const label = clean(row.getAttribute('aria-label') || row.getAttribute('title'));
  const text = clean(row.innerText || row.textContent || label);
  return label.toLowerCase().includes(target) || text.toLowerCase().includes(target);
};

const row = rows.find(matches);
if (!row) {
  return {ok: false, message: `no visible OneDrive item matching '${arguments[0]}'`};
}

row.scrollIntoView({block: 'center', inline: 'nearest'});
row.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
row.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));

const checkboxSelectors = [
  "input[type='checkbox']",
  "[role='checkbox']",
  "button[aria-checked]",
  "button[aria-label*='Select' i]",
  "[aria-label*='Select' i][role='button']"
];

for (const selector of checkboxSelectors) {
  const control = row.querySelector(selector);
  if (!control || !visible(control)) continue;
  const checked = control.checked === true || control.getAttribute('aria-checked') === 'true';
  if (!checked) control.click();
  return {
    ok: true,
    name: clean(row.getAttribute('aria-label') || row.innerText || row.textContent || arguments[0]),
    selected: true,
    method: selector
  };
}

return {
  ok: false,
  message: `found '${arguments[0]}' but could not find a visible select checkbox`
};
"""


_PATH_SCRIPT = r"""
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const crumbs = Array.from(document.querySelectorAll(
  "[aria-label*='Breadcrumb' i] a, [aria-label*='Breadcrumb' i] button, nav[aria-label*='breadcrumb' i] a, nav[aria-label*='breadcrumb' i] button"
));
return crumbs.map((el) => clean(el.innerText || el.textContent || el.getAttribute('aria-label'))).filter(Boolean);
"""

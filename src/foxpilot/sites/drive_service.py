"""Google Drive URL, formatting, and browser extraction helpers."""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Any, Literal, Optional


View = Literal["home", "recent", "starred", "shared", "trash"]

DRIVE_BASE_URL = "https://drive.google.com/"

DRIVE_VIEWS: dict[str, str] = {
    "home": "drive/my-drive",
    "recent": "drive/recent",
    "starred": "drive/starred",
    "shared": "drive/shared-with-me",
    "trash": "drive/trash",
}

_VIEW_ALIASES = {
    "my-drive": "home",
    "mydrive": "home",
    "my": "home",
    "root": "home",
    "all": "home",
    "shared-with-me": "shared",
    "sharedwithme": "shared",
    "shared-drives": "shared",
    "star": "starred",
    "favorites": "starred",
    "favourites": "starred",
    "bin": "trash",
    "deleted": "trash",
    "recycle": "trash",
    "recyclebin": "trash",
}


def normalize_view(view: str) -> View:
    value = (view or "home").strip().lower()
    value = _VIEW_ALIASES.get(value, value)
    if value not in DRIVE_VIEWS:
        expected = ", ".join(sorted(DRIVE_VIEWS))
        raise ValueError(f"unknown Drive view '{view}' (expected: {expected})")
    return value  # type: ignore[return-value]


def build_drive_url(view: str = "home") -> str:
    """Build a stable Google Drive landing URL for a high-level view."""
    normalized = normalize_view(view)
    path = DRIVE_VIEWS[normalized]
    return f"{DRIVE_BASE_URL}{path}"


def build_folder_url(folder_id: str) -> str:
    """Build the URL for a Google Drive folder by id."""
    value = (folder_id or "").strip()
    if not value:
        raise ValueError("folder id is required")
    return f"{DRIVE_BASE_URL}drive/folders/{urllib.parse.quote(value, safe='')}"


def build_search_url(query: str) -> str:
    """Build the URL for a Google Drive search."""
    value = (query or "").strip()
    if not value:
        raise ValueError("search query is required")
    return f"{DRIVE_BASE_URL}drive/search?q={urllib.parse.quote(value)}"


def is_drive_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(_ensure_url_scheme(value))
    host = parsed.netloc.lower()
    return host in {"drive.google.com", "docs.google.com"}


def normalize_drive_target(target: str) -> str:
    """Return a navigable Drive URL from a URL, folder id, or view name."""
    value = (target or "home").strip()
    if _looks_like_url(value):
        url = _ensure_url_scheme(value)
        if not is_drive_url(url):
            raise ValueError(f"not a Google Drive URL: {target}")
        return url
    return build_drive_url(value)


def format_open_result(data: dict[str, Any]) -> str:
    lines = []
    for key in ("title", "name", "url", "view"):
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
        return "No Drive items found."

    lines: list[str] = []
    for index, item in enumerate(items, 1):
        lines.append(f"[{index}] {item.get('name') or '(unnamed item)'}")
        for key in ("url", "kind", "owner", "modified", "size", "shared"):
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
    """Extract visible files and folders from the current Drive page."""
    return _list_result(driver.execute_script(_ITEMS_SCRIPT, limit))


def extract_path(driver) -> list[str]:
    """Extract the visible Drive breadcrumb path."""
    value = driver.execute_script(_PATH_SCRIPT)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def open_item(driver, name: str) -> dict[str, str]:
    """Open a visible Drive item by accessible text or label (double-click)."""
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
            except Exception:
                continue
            if _double_click(driver, element):
                return {"name": name, "url": getattr(driver, "current_url", "")}
    raise RuntimeError(f"no visible Drive item matching '{name}'")


def search_items(driver, query: str, limit: int = 50) -> list[dict[str, Any]]:
    """Search Drive through the web UI and return visible result items."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    search_box = _find_search_box(driver, By)
    if search_box is None:
        raise RuntimeError("could not find Drive search box")
    try:
        search_box.clear()
    except Exception:
        pass
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)

    time.sleep(1.5)
    return extract_items(driver, limit=limit)


def download_item(driver, name: str) -> dict[str, Any]:
    """Right-click a Drive item and click the Download menu entry."""
    from selenium.webdriver.common.by import By

    if not _open_context_menu(driver, By, name):
        raise RuntimeError(f"could not open context menu for Drive item '{name}'")
    time.sleep(0.4)
    if _click_menu_label(driver, By, "Download"):
        return {"status": "started", "name": name, "url": getattr(driver, "current_url", "")}
    raise RuntimeError(f"could not find Download menu entry for '{name}'")


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


# -- private helpers ----------------------------------------------------------


def _find_search_box(driver, by):
    selectors = [
        "input[aria-label*='Search' i]",
        "input[placeholder*='Search' i]",
        "input[type='search']",
        "[role='searchbox']",
        "[role='combobox'][aria-label*='Search' i]",
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


def _open_context_menu(driver, by, name: str) -> bool:
    candidates = _item_name_xpaths(name)
    for xpath in candidates:
        try:
            elements = driver.find_elements(by.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                from selenium.webdriver.common.action_chains import ActionChains

                ActionChains(driver).context_click(element).perform()
                return True
            except Exception:
                continue
    return False


def _click_menu_label(driver, by, label: str) -> bool:
    literal = _xpath_literal(label)
    xpaths = [
        f"//*[@role='menuitem'][contains(normalize-space(.), {literal})]",
        f"//*[@role='menuitem'][contains(@aria-label, {literal})]",
        f"//*[self::div or self::span][contains(@class, 'menu')][contains(normalize-space(.), {literal})]",
    ]
    for xpath in xpaths:
        try:
            elements = driver.find_elements(by.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            try:
                if not element.is_displayed():
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


def _double_click(driver, element) -> bool:
    try:
        from selenium.webdriver.common.action_chains import ActionChains

        ActionChains(driver).double_click(element).perform()
        return True
    except Exception:
        try:
            element.click()
            return True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False


def _item_name_xpaths(name: str) -> list[str]:
    literal = _xpath_literal(name)
    return [
        f"//*[@role='gridcell' or @role='row' or @role='link'][contains(normalize-space(.), {literal})]",
        f"//*[contains(@aria-label, {literal})]",
        f"//*[contains(@data-tooltip, {literal})]",
        f"//*[self::a or self::div][contains(normalize-space(.), {literal})]",
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
const closestLink = (el) => el.closest && (el.closest('a[href]') || (el.querySelector && el.querySelector('a[href]')));
const inferKind = (text, label) => {
  const joined = `${text} ${label}`.toLowerCase();
  if (joined.includes('folder')) return 'folder';
  if (joined.includes('shortcut')) return 'shortcut';
  if (joined.includes('google docs')) return 'doc';
  if (joined.includes('google sheets')) return 'sheet';
  if (joined.includes('google slides')) return 'slides';
  if (joined.includes('pdf')) return 'pdf';
  return 'file';
};
"""


_ITEMS_SCRIPT = _COMMON_JS + r"""
const rows = Array.from(document.querySelectorAll(
  "[role='row'], [role='gridcell'][data-id], [data-id][aria-label], c-wiz [role='listitem']"
)).filter(visible);
const seen = new Set();
const items = [];

for (const row of rows) {
  if (items.length >= limit) break;
  const label = clean(row.getAttribute('aria-label') || row.getAttribute('data-tooltip') || row.getAttribute('title'));
  let name = label;
  if (!name) {
    const nameEl = row.querySelector && row.querySelector("[data-tooltip], [aria-label], a, span");
    if (nameEl) name = clean(nameEl.getAttribute('aria-label') || nameEl.getAttribute('data-tooltip') || nameEl.innerText || nameEl.textContent);
  }
  if (!name) name = clean(row.innerText || row.textContent);
  if (!name || name.length > 240 || seen.has(name)) continue;

  const link = closestLink(row);
  const text = clean(row.innerText || row.textContent);
  const modifiedMatch = text.match(/\b(today|yesterday|\d{1,2}\/\d{1,2}\/\d{2,4}|[A-Z][a-z]+ \d{1,2},?\s*\d{0,4})\b/i);
  const sizeMatch = text.match(/\b\d+(?:\.\d+)?\s*(?:bytes|B|KB|MB|GB|TB)\b/i);
  const ownerMatch = text.match(/\b(me|you)\b/i);
  seen.add(name);
  items.push({
    name,
    url: link ? link.href : '',
    kind: inferKind(text, label),
    owner: ownerMatch ? ownerMatch[0] : '',
    modified: modifiedMatch ? modifiedMatch[0] : '',
    size: sizeMatch ? sizeMatch[0] : '',
    shared: /shared/i.test(text),
  });
}

return items;
"""


_PATH_SCRIPT = r"""
const clean = (value) => String(value || '').replace(/\s+/g, ' ').trim();
const crumbs = Array.from(document.querySelectorAll(
  "[role='navigation'] [role='button'], [aria-label*='breadcrumb' i] a, [aria-label*='breadcrumb' i] button, [data-target='breadcrumb'] *, .a-Z a"
));
const seen = new Set();
const out = [];
for (const el of crumbs) {
  const text = clean(el.innerText || el.textContent || el.getAttribute('aria-label'));
  if (!text || seen.has(text)) continue;
  seen.add(text);
  out.push(text);
}
return out;
"""

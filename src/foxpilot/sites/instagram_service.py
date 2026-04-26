"""Service layer for Instagram (instagram.com) browser workflows.

Instagram is hostile to automation: aggressive anti-bot, frequent DOM
churn, shadow-root content, and login challenges on new-device sessions.
The recommended foxpilot mode is `--zen` (reuse the user's already-
signed-in session). This module exposes URL helpers, handle/tag
normalization, search-URL builders, formatters, and best-effort DOM
extraction stubs. DOM helpers live in :mod:`foxpilot.sites._dom`.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

from foxpilot.sites._dom import (
    child_attr as _child_attr,
    find_all_css as _find_all_css,
    find_one_css as _find_one_css,
    find_one_xpath as _find_one_xpath,
    list_texts as _list_texts,
    safe_url as _safe_url,
    text_first as _text_first,
)


INSTAGRAM_HOST = "www.instagram.com"
INSTAGRAM_HOME = f"https://{INSTAGRAM_HOST}/"

CONTACT_CACHE_DEFAULT_TTL_S = 24 * 60 * 60  # 24h
FOLLOWERS_DEFAULT_LIMIT = 500

SECTIONS = {
    "home": "",
    "explore": "explore/",
    "reels": "reels/",
    "direct": "direct/inbox/",
    "notifications": "accounts/activity/",
    "tags": "explore/tags/",
}

_HANDLE_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9_]{1,100}$")


def is_instagram_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("instagram.com")


def home_url() -> str:
    return INSTAGRAM_HOME


def section_url(section: str) -> str:
    """Resolve a known Instagram section name to a full URL."""
    key = (section or "").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown Instagram section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTIONS))})"
        )
    return f"{INSTAGRAM_HOME}{SECTIONS[key]}"


def normalize_handle(value: str) -> str:
    """Accept an Instagram handle, `@handle`, or profile URL and return the handle."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty Instagram handle")
    if "://" in raw or raw.startswith("www.") or raw.startswith("instagram.com"):
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            raw = parts[0]
    raw = raw.lstrip("@").strip("/")
    if not _HANDLE_RE.match(raw):
        raise ValueError(f"invalid Instagram handle: {value!r}")
    return raw


def profile_url(handle_or_url: str) -> str:
    handle = normalize_handle(handle_or_url)
    return f"{INSTAGRAM_HOME}{handle}/"


def normalize_tag(value: str) -> str:
    raw = (value or "").strip().lstrip("#")
    if not raw:
        raise ValueError("empty Instagram tag")
    if not _TAG_RE.match(raw):
        raise ValueError(f"invalid Instagram tag: {value!r}")
    return raw.lower()


def tag_url(tag: str) -> str:
    name = normalize_tag(tag)
    return f"{INSTAGRAM_HOME}explore/tags/{name}/"


def post_url(shortcode: str) -> str:
    raw = (shortcode or "").strip().strip("/")
    if not raw:
        raise ValueError("empty post shortcode")
    return f"{INSTAGRAM_HOME}p/{urllib.parse.quote(raw, safe='')}/"


def reel_url(shortcode: str) -> str:
    raw = (shortcode or "").strip().strip("/")
    if not raw:
        raise ValueError("empty reel shortcode")
    return f"{INSTAGRAM_HOME}reel/{urllib.parse.quote(raw, safe='')}/"


def search_url(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    encoded = urllib.parse.urlencode({"q": query.strip()})
    return f"{INSTAGRAM_HOME}explore/search/keyword/?{encoded}"


def direct_thread_url(thread_id: str) -> str:
    raw = (thread_id or "").strip()
    if not raw:
        raise ValueError("empty direct thread id")
    return f"{INSTAGRAM_HOME}direct/t/{urllib.parse.quote(raw, safe='')}/"


def followers_url(handle_or_url: str) -> str:
    handle = normalize_handle(handle_or_url)
    return f"{INSTAGRAM_HOME}{handle}/followers/"


def following_url(handle_or_url: str) -> str:
    handle = normalize_handle(handle_or_url)
    return f"{INSTAGRAM_HOME}{handle}/following/"


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_open_result(data: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"section: {data.get('section', '')}",
        ]
    )


def format_profile(data: dict[str, Any]) -> str:
    if not data:
        return "(no profile data)"
    lines = []
    for key in (
        "handle",
        "name",
        "bio",
        "posts",
        "followers",
        "following",
        "url",
    ):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_posts(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no posts)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('shortcode', '(no shortcode)')}")
        for key in ("caption", "likes", "comments", "url"):
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
        kind = item.get("kind") or "?"
        label = item.get("label") or "(unknown)"
        lines.append(f"[{i}] ({kind}) {label}")
        for key in ("subtitle", "url"):
            value = item.get(key)
            if value:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_threads(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no direct threads)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('peer', '(unknown)')}")
        snippet = item.get("snippet")
        if snippet:
            lines.append(f"    snippet: {snippet}")
        when = item.get("when")
        if when:
            lines.append(f"    when: {when}")
        thread = item.get("thread_id")
        if thread:
            lines.append(f"    thread: {thread}")
        lines.append("")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Politeness jitter (Instagram rate-limits aggressive scraping)
# ---------------------------------------------------------------------------

def polite_jitter(min_secs: float = 0.7, spread: float = 0.8) -> None:
    """Sleep a small randomised amount between paginated reads.

    Default: `0.7 + random()*0.8` seconds — i.e. 0.7s to 1.5s. Instagram
    is more aggressive than LinkedIn, so the floor is higher.
    """
    time.sleep(min_secs + random.random() * spread)


# ---------------------------------------------------------------------------
# DOM extraction stubs (best effort; selectors via private helpers)
# ---------------------------------------------------------------------------

def extract_profile(driver) -> dict[str, Any]:
    """Read handle, display name, bio, and counts from a profile page."""
    handle = _text_first(driver, [
        "header h2",
        "header section h2",
    ])
    name = _text_first(driver, [
        "header section h1",
        "header h1",
    ])
    bio = _text_first(driver, [
        "header section > div > span",
        "header div[class*='biography']",
    ])
    counts = _list_texts(driver, [
        "header li",
        "header section ul li",
    ], limit=3)
    posts, followers, following = "", "", ""
    if len(counts) >= 1:
        posts = _split_count(counts[0])
    if len(counts) >= 2:
        followers = _split_count(counts[1])
    if len(counts) >= 3:
        following = _split_count(counts[2])
    return {
        "handle": handle,
        "name": name,
        "bio": bio,
        "posts": posts,
        "followers": followers,
        "following": following,
        "url": _safe_url(driver),
    }


def extract_posts(driver, limit: int = 12) -> list[dict[str, Any]]:
    """Extract recent posts from a profile-grid page. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "article a[href*='/p/']",
        "main a[href*='/p/']",
        "a[href*='/reel/']",
    ])
    seen: set[str] = set()
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
        shortcode = _shortcode_from_url(href)
        caption = _child_attr(card, ["img"], "alt")
        results.append({
            "shortcode": shortcode,
            "caption": caption,
            "likes": "",
            "comments": "",
            "url": href,
        })
        if len(results) % 4 == 0:
            polite_jitter()
    return results


def extract_search_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract entries from a search-results dropdown / page. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "div[role='dialog'] a",
        "div[role='listbox'] a",
        "main a[href^='/']",
    ])
    seen: set[str] = set()
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
        kind, label = _classify_search_href(href)
        if not kind:
            continue
        subtitle = ""
        try:
            subtitle = (card.text or "").strip().splitlines()[-1]
        except Exception:
            subtitle = ""
        results.append({
            "kind": kind,
            "label": label,
            "subtitle": subtitle,
            "url": href,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def extract_direct_threads(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract recent DM threads from the inbox. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "div[role='listbox'] a[href*='/direct/t/']",
        "div[role='list'] a[href*='/direct/t/']",
        "a[href*='/direct/t/']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        link = ""
        try:
            link = card.get_attribute("href") or ""
        except Exception:
            link = ""
        peer = ""
        snippet = ""
        when = ""
        try:
            text = (card.text or "").strip().splitlines()
        except Exception:
            text = []
        if text:
            peer = text[0]
        if len(text) > 1:
            snippet = text[1]
        if len(text) > 2:
            when = text[-1]
        thread_id = ""
        if link and "/direct/t/" in link:
            try:
                thread_id = link.rstrip("/").split("/direct/t/")[1].split("/")[0]
            except Exception:
                thread_id = ""
        results.append({
            "peer": peer,
            "snippet": snippet,
            "when": when,
            "thread_id": thread_id,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def click_follow_button(driver) -> bool:
    """Click the Follow button on a profile page. Returns True on click."""
    btn = _find_one_xpath(driver, [
        "//header//button[normalize-space()='Follow']",
        "//header//button[contains(., 'Follow') and not(contains(., 'Following'))]",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def click_like_button(driver) -> bool:
    """Click the heart/like button on an open post page. Returns True on click."""
    btn = _find_one_xpath(driver, [
        "//section//button[.//*[name()='svg' and (@aria-label='Like' or @aria-label='Like post')]]",
        "//button[@aria-label='Like']",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def post_comment(driver, text: str) -> bool:
    """Type a comment on an open post page and submit. Returns True on success."""
    box = _find_one_css(driver, [
        "form textarea",
        "textarea[aria-label='Add a comment…']",
        "textarea[aria-label='Add a comment...']",
    ])
    if box is None:
        return False
    try:
        box.click()
        box.send_keys(text)
    except Exception:
        return False
    submit = _find_one_xpath(driver, [
        "//form//button[@type='submit']",
        "//form//div[@role='button' and normalize-space()='Post']",
        "//button[normalize-space()='Post']",
    ])
    if submit is None:
        return False
    try:
        submit.click()
    except Exception:
        return False
    return True


def send_dm(driver, text: str) -> bool:
    """Type into the DM composer on an open thread and submit."""
    box = _find_one_css(driver, [
        "div[role='textbox'][contenteditable='true']",
        "textarea[placeholder='Message…']",
        "textarea[placeholder='Message...']",
    ])
    if box is None:
        return False
    try:
        box.click()
        box.send_keys(text)
    except Exception:
        return False
    send = _find_one_xpath(driver, [
        "//div[@role='button' and normalize-space()='Send']",
        "//button[normalize-space()='Send']",
    ])
    if send is None:
        # Try Enter as fallback.
        try:
            from selenium.webdriver.common.keys import Keys

            box.send_keys(Keys.RETURN)
            return True
        except Exception:
            return False
    try:
        send.click()
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Private parsing helpers
# ---------------------------------------------------------------------------

def _shortcode_from_url(url: str) -> str:
    if not url:
        return ""
    for marker in ("/p/", "/reel/", "/tv/"):
        if marker in url:
            try:
                return url.split(marker)[1].split("/")[0]
            except Exception:
                return ""
    return ""


def _classify_search_href(href: str) -> tuple[str, str]:
    if not href:
        return ("", "")
    parsed = urllib.parse.urlparse(href)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return ("", "")
    if parts[0] == "explore" and len(parts) >= 3 and parts[1] == "tags":
        return ("tag", f"#{parts[2]}")
    if parts[0] == "p" and len(parts) >= 2:
        return ("post", parts[1])
    if parts[0] == "reel" and len(parts) >= 2:
        return ("reel", parts[1])
    if parts[0] == "explore" and len(parts) >= 3 and parts[1] == "locations":
        return ("location", parts[2])
    if _HANDLE_RE.match(parts[0]):
        return ("user", f"@{parts[0]}")
    return ("", "")


def _split_count(value: str) -> str:
    """Pull the leading count out of a string like '12 posts' or '1,234 followers'."""
    if not value:
        return ""
    head = value.strip().split()
    return head[0] if head else value.strip()


# ---------------------------------------------------------------------------
# whoami / followers / following / contact resolution
# ---------------------------------------------------------------------------

def detect_own_handle(driver) -> str:
    """Best-effort: find the signed-in user's handle from header chrome."""
    candidates = _find_all_css(driver, [
        "a[href^='/'][role='link'][aria-label]",
        "nav a[href^='/']",
        "a[href*='/?next='][role='link']",
    ])
    for el in candidates:
        try:
            href = el.get_attribute("href") or ""
        except Exception:
            continue
        if not href:
            continue
        parsed = urllib.parse.urlparse(href)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) == 1 and _HANDLE_RE.match(parts[0]):
            try:
                aria = (el.get_attribute("aria-label") or "").lower()
            except Exception:
                aria = ""
            if "profile" in aria or len(parts[0]) > 0:
                return parts[0]
    return ""


def extract_followers(driver, limit: int = FOLLOWERS_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Extract followers from an open `/<handle>/followers/` modal. Best effort.

    Caller is responsible for scrolling the modal to load more rows; this
    function reads whatever is currently mounted.
    """
    return _extract_user_rows(driver, limit=limit)


def extract_following(driver, limit: int = FOLLOWERS_DEFAULT_LIMIT) -> list[dict[str, Any]]:
    """Extract following list from an open `/<handle>/following/` modal."""
    return _extract_user_rows(driver, limit=limit)


def scroll_user_list(driver, max_rounds: int = 30, batch: int = 50) -> int:
    """Scroll the followers/following modal to load more rows.

    Returns total visible row count after scrolling. Stops early if no
    new rows arrive after a round, or after `max_rounds` rounds.
    """
    last = -1
    for _ in range(max_rounds):
        rows = _find_all_css(driver, [
            "div[role='dialog'] div[role='button'] a[href^='/']",
            "div[role='dialog'] a[href^='/'][role='link']",
            "div[role='dialog'] li a[href^='/']",
        ])
        if not rows:
            break
        count = len(rows)
        if count == last:
            break
        last = count
        try:
            rows[-1].location_once_scrolled_into_view  # triggers lazy-load
        except Exception:
            try:
                driver.execute_script("arguments[0].scrollIntoView();", rows[-1])
            except Exception:
                break
        polite_jitter(0.6, 0.6)
        if count >= batch * (max_rounds // 5 + 1):
            continue
    return last if last > 0 else 0


def _extract_user_rows(driver, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    rows = _find_all_css(driver, [
        "div[role='dialog'] a[href^='/'][role='link']",
        "div[role='dialog'] a[href^='/']",
    ])
    for row in rows:
        if len(results) >= limit:
            break
        try:
            href = row.get_attribute("href") or ""
        except Exception:
            continue
        parsed = urllib.parse.urlparse(href)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) != 1:
            continue
        handle = parts[0]
        if not _HANDLE_RE.match(handle):
            continue
        if handle in seen:
            continue
        seen.add(handle)
        name = ""
        try:
            text_lines = (row.text or "").strip().splitlines()
            if text_lines and text_lines[0] and text_lines[0] != handle:
                name = text_lines[0]
            elif len(text_lines) > 1:
                name = text_lines[1]
        except Exception:
            name = ""
        results.append({
            "handle": handle,
            "name": name,
            "url": f"{INSTAGRAM_HOME}{handle}/",
        })
    return results


# ---------------------------------------------------------------------------
# Contact cache
# ---------------------------------------------------------------------------

def default_cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "foxpilot" / "instagram"


def cache_path(owner: str, *, cache_dir: Path | None = None) -> Path:
    handle = normalize_handle(owner)
    folder = cache_dir or default_cache_dir()
    return folder / f"{handle}-contacts.json"


def save_contacts(
    owner: str,
    contacts: list[dict[str, Any]],
    *,
    cache_dir: Path | None = None,
    now: float | None = None,
) -> Path:
    """Persist a contacts list to disk. Returns the file path."""
    path = cache_path(owner, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "owner": normalize_handle(owner),
        "saved_at": now if now is not None else time.time(),
        "contacts": contacts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_contacts(
    owner: str,
    *,
    cache_dir: Path | None = None,
    ttl_s: int = CONTACT_CACHE_DEFAULT_TTL_S,
    now: float | None = None,
) -> list[dict[str, Any]]:
    """Load cached contacts. Returns [] if missing or stale."""
    path = cache_path(owner, cache_dir=cache_dir)
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    saved_at = float(payload.get("saved_at", 0.0))
    age = (now if now is not None else time.time()) - saved_at
    if age > ttl_s:
        return []
    contacts = payload.get("contacts") or []
    if not isinstance(contacts, list):
        return []
    return contacts


def merge_contacts(*sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge contact lists, dedup by handle, keep first-seen `source` tag."""
    out: dict[str, dict[str, Any]] = {}
    for src in sources:
        for entry in src or []:
            handle = (entry or {}).get("handle") or ""
            if not handle:
                continue
            existing = out.get(handle)
            if existing is None:
                out[handle] = dict(entry)
            else:
                if not existing.get("name") and entry.get("name"):
                    existing["name"] = entry["name"]
                src_tag = entry.get("source")
                if src_tag and src_tag not in (existing.get("source") or ""):
                    existing["source"] = (
                        f"{existing.get('source', '')}+{src_tag}".strip("+")
                    )
    return list(out.values())


# ---------------------------------------------------------------------------
# Fuzzy resolver
# ---------------------------------------------------------------------------

def fuzzy_match_contacts(
    contacts: list[dict[str, Any]],
    query: str,
) -> list[dict[str, Any]]:
    """Token-AND, case-insensitive substring match on handle + name.

    Returns matches sorted by score (handle exact > handle prefix >
    name token-AND > handle substring), then alphabetically by handle.
    """
    if not query or not query.strip():
        return []
    tokens = [t for t in re.split(r"\s+", query.strip().lower()) if t]
    if not tokens:
        return []

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for entry in contacts or []:
        handle = (entry.get("handle") or "").lower()
        name = (entry.get("name") or "").lower()
        if not handle:
            continue
        haystack = f"{handle} {name}"
        if not all(tok in haystack for tok in tokens):
            continue
        score = 0
        joined = " ".join(tokens)
        if handle == joined:
            score = 100
        elif handle.startswith(joined):
            score = 80
        elif all(tok in handle for tok in tokens):
            score = 60
        elif name and all(tok in name for tok in tokens):
            score = 40
        else:
            score = 20
        scored.append((score, handle, entry))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _, _, entry in scored]


__all__ = [
    "CONTACT_CACHE_DEFAULT_TTL_S",
    "FOLLOWERS_DEFAULT_LIMIT",
    "INSTAGRAM_HOME",
    "INSTAGRAM_HOST",
    "SECTIONS",
    "cache_path",
    "click_follow_button",
    "click_like_button",
    "default_cache_dir",
    "detect_own_handle",
    "direct_thread_url",
    "extract_direct_threads",
    "extract_followers",
    "extract_following",
    "extract_posts",
    "extract_profile",
    "extract_search_results",
    "followers_url",
    "following_url",
    "format_open_result",
    "format_posts",
    "format_profile",
    "format_search_results",
    "format_threads",
    "fuzzy_match_contacts",
    "home_url",
    "is_instagram_url",
    "load_contacts",
    "merge_contacts",
    "normalize_handle",
    "normalize_tag",
    "polite_jitter",
    "post_comment",
    "post_url",
    "profile_url",
    "reel_url",
    "save_contacts",
    "scroll_user_list",
    "search_url",
    "section_url",
    "send_dm",
    "tag_url",
]

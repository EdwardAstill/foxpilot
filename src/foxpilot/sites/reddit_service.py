"""Service layer for Reddit (reddit.com) browser workflows.

Reddit has moderate bot friction: login walls for some actions, rate
limits on repeated scraping, and periodic DOM churn. Most read-only
browsing works without auth. Write actions (submit, comment, vote)
require a signed-in session. Recommended mode is `--zen`. Selectors
live behind `_find_*` helpers.
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
    find_one_css as _find_one_css,
    safe_url as _safe_url,
    text_first as _text_first,
)


REDDIT_HOST = "www.reddit.com"
REDDIT_HOME = f"https://{REDDIT_HOST}/"

SECTIONS = {
    "home": "",
    "popular": "r/popular/",
    "all": "r/all/",
    "saved": "saved/",
}

SORT_OPTIONS = {"hot", "new", "top", "rising"}

_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")


def is_reddit_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("reddit.com")


def home_url() -> str:
    return REDDIT_HOME


def section_url(section: str) -> str:
    key = (section or "").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown Reddit section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTIONS))})"
        )
    return f"{REDDIT_HOME}{SECTIONS[key]}"


def normalize_subreddit(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty subreddit name")
    raw = re.sub(r"^/?r/", "", raw).strip("/")
    if not _SUBREDDIT_RE.match(raw):
        raise ValueError(f"invalid subreddit name: {value!r}")
    return raw


def subreddit_url(name: str, sort: str = "hot") -> str:
    sub = normalize_subreddit(name)
    sort = (sort or "hot").lower()
    if sort not in SORT_OPTIONS:
        raise ValueError(f"invalid sort: {sort!r} (expected one of: {', '.join(sorted(SORT_OPTIONS))})")
    return f"{REDDIT_HOME}r/{sub}/{sort}/"


def post_url_from_id(post_id: str) -> str:
    raw = (post_id or "").strip().strip("/")
    if not raw:
        raise ValueError("empty post id")
    return f"{REDDIT_HOME}comments/{urllib.parse.quote(raw, safe='')}/"


def normalize_post_target(target: str) -> str:
    """Accept a post id, /comments/<id>/ path, or full URL and return a full URL."""
    raw = (target or "").strip()
    if not raw:
        raise ValueError("empty post target")
    if "://" in raw:
        return raw
    if raw.startswith("/comments/") or raw.startswith("comments/"):
        return f"{REDDIT_HOME}{raw.lstrip('/')}"
    return post_url_from_id(raw)


def search_url(query: str, subreddit: str = "", sort: str = "relevance") -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    params: dict[str, str] = {"q": query.strip(), "sort": sort}
    if subreddit:
        sub = normalize_subreddit(subreddit)
        params["restrict_sr"] = "1"
        return f"{REDDIT_HOME}r/{sub}/search/?{urllib.parse.urlencode(params)}"
    return f"{REDDIT_HOME}search/?{urllib.parse.urlencode(params)}"


def polite_jitter(min_secs: float = 0.4, spread: float = 0.6) -> None:
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


def format_posts(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no posts)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('title', '(no title)')}")
        for key in ("subreddit", "author", "score", "comments", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_post(data: dict[str, Any]) -> str:
    if not data:
        return "(no post data)"
    lines = []
    for key in ("title", "subreddit", "author", "score", "text", "url"):
        value = data.get(key)
        if value not in (None, ""):
            text = str(value)
            if key == "text" and len(text) > 400:
                text = text[:400] + "…"
            lines.append(f"{key}: {text}")
    return "\n".join(lines)


def format_search_results(results: list[dict[str, Any]]) -> str:
    return format_posts(results)


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

def extract_posts(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract post listings from a subreddit or home feed. Best effort."""
    results: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Try new Reddit first, then old
    cards = _find_all_css(driver, [
        "article",
        "div[data-testid='post-container']",
        "div.Post",
        "div[data-fullname]",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        title = ""
        url = ""
        try:
            title_el = _child_el(card, [
                "h3",
                "a[data-click-id='title']",
                "a[class*='title']",
            ])
            if title_el:
                title = (title_el.text or "").strip()
                href = title_el.get_attribute("href") or ""
                if href:
                    url = href if "://" in href else f"{REDDIT_HOME.rstrip('/')}{href}"
        except Exception:
            pass
        if not title or url in seen:
            continue
        seen.add(url)
        subreddit = _child_text(card, [
            "a[href^='/r/'][data-click-id='subreddit']",
            "a[href^='/r/']",
        ])
        author = _child_text(card, [
            "a[href^='/user/']",
            "span[class*='author']",
        ])
        score = _child_text(card, [
            "div[class*='score']",
            "span[class*='score']",
            "button[aria-label*='upvote'] + *",
        ])
        comments = _child_text(card, [
            "a[data-click-id='comments'] span",
            "a[class*='comments']",
        ])
        results.append({
            "title": title,
            "subreddit": subreddit,
            "author": author,
            "score": score,
            "comments": comments,
            "url": url,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def extract_post(driver) -> dict[str, Any]:
    """Extract the opened post: title, body text, metadata."""
    title = _text_first(driver, [
        "h1[slot='title']",
        "div[data-test-id='post-content'] h1",
        "h1",
    ])
    text = _text_first(driver, [
        "div[data-click-id='text'] div[class*='md']",
        "div[slot='text-body']",
        "div[data-test-id='post-content'] div[class*='body']",
    ])
    author = _text_first(driver, [
        "a[data-testid='post_author_link']",
        "a[href*='/user/']",
    ])
    score = _text_first(driver, [
        "faceplate-number[pretty]",
        "div[class*='score']",
    ])
    subreddit = _text_first(driver, [
        "a[href^='/r/'][data-click-id='subreddit']",
        "shreddit-subreddit-link a",
    ])
    return {
        "title": title,
        "subreddit": subreddit,
        "author": author,
        "score": score,
        "text": text,
        "url": _safe_url(driver),
    }


def post_comment(driver, text: str) -> bool:
    """Type and submit a comment on an open post page. Returns True on success."""
    box = _find_one_css(driver, [
        "div[data-testid='comment-textarea'] div[contenteditable='true']",
        "div[id*='comment'] div[contenteditable='true']",
        "textarea[placeholder*='comment']",
        "div[placeholder*='comment'][contenteditable='true']",
    ])
    if box is None:
        return False
    try:
        box.click()
        box.send_keys(text)
    except Exception:
        return False
    submit = _find_one_css(driver, [
        "button[slot='submit-button']",
        "button[type='submit'][class*='comment']",
    ])
    if submit is None:
        return False
    try:
        submit.click()
    except Exception:
        return False
    return True


def submit_post(driver, subreddit: str, title: str, body: str) -> bool:
    """Navigate to submit page and fill the post form. Returns True on success."""
    sub = normalize_subreddit(subreddit)
    try:
        driver.get(f"{REDDIT_HOME}r/{sub}/submit")
        polite_jitter(1.0, 0.5)
    except Exception:
        return False
    title_input = _find_one_css(driver, [
        "textarea[name='title']",
        "input[name='title']",
        "div[placeholder*='title'][contenteditable='true']",
    ])
    if title_input is None:
        return False
    try:
        title_input.click()
        title_input.send_keys(title)
    except Exception:
        return False
    if body:
        body_input = _find_one_css(driver, [
            "div[data-testid='text-body-input'] div[contenteditable='true']",
            "div.public-DraftEditor-content",
            "textarea[name='body']",
        ])
        if body_input:
            try:
                body_input.click()
                body_input.send_keys(body)
            except Exception:
                pass
    submit = _find_one_css(driver, [
        "button[type='submit']",
        "button[class*='submit']",
    ])
    if submit is None:
        return False
    try:
        submit.click()
    except Exception:
        return False
    return True


__all__ = [
    "REDDIT_HOME",
    "REDDIT_HOST",
    "SECTIONS",
    "SORT_OPTIONS",
    "extract_post",
    "extract_posts",
    "format_open_result",
    "format_post",
    "format_posts",
    "format_search_results",
    "home_url",
    "is_reddit_url",
    "normalize_post_target",
    "normalize_subreddit",
    "polite_jitter",
    "post_comment",
    "post_url_from_id",
    "search_url",
    "section_url",
    "submit_post",
    "subreddit_url",
]

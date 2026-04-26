"""Service layer for X / Twitter (x.com) browser workflows.

X is hostile to automation: aggressive anti-bot, login walls for most
content, frequent DOM churn, and rate-limit redirects. The recommended
foxpilot mode is `--zen` (reuse the user's already-signed-in session).
Selectors live behind private `_find_*` helpers so a single edit
re-tunes the plugin when X changes its markup.
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
    find_one_xpath as _find_one_xpath,
    safe_url as _safe_url,
    text_first as _text_first,
)


TWITTER_HOST = "x.com"
TWITTER_HOME = f"https://{TWITTER_HOST}/"

SECTIONS = {
    "home": "home",
    "explore": "explore",
    "notifications": "notifications",
    "messages": "messages",
    "bookmarks": "i/bookmarks",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")


def is_twitter_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("x.com") or host.endswith("twitter.com")


def home_url() -> str:
    return TWITTER_HOME


def section_url(section: str) -> str:
    key = (section or "").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown X section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTIONS))})"
        )
    return f"{TWITTER_HOME}{SECTIONS[key]}"


def normalize_username(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty X username")
    if "://" in raw or raw.startswith("x.com") or raw.startswith("twitter.com"):
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
        parts = [p for p in parsed.path.split("/") if p]
        if parts:
            raw = parts[0]
    raw = raw.lstrip("@").strip("/")
    if not _USERNAME_RE.match(raw):
        raise ValueError(f"invalid X username: {value!r}")
    return raw


def profile_url(username_or_url: str) -> str:
    username = normalize_username(username_or_url)
    return f"{TWITTER_HOME}{username}"


def search_url(query: str, tab: str = "Top") -> str:
    if not query or not query.strip():
        raise ValueError("empty search query")
    params = {"q": query.strip(), "src": "typed_query", "f": tab}
    return f"{TWITTER_HOME}search?{urllib.parse.urlencode(params)}"


def tweet_url(username: str, tweet_id: str) -> str:
    user = normalize_username(username)
    raw = (tweet_id or "").strip()
    if not raw:
        raise ValueError("empty tweet id")
    return f"{TWITTER_HOME}{user}/status/{raw}"


def polite_jitter(min_secs: float = 0.6, spread: float = 0.8) -> None:
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


def format_profile(data: dict[str, Any]) -> str:
    if not data:
        return "(no profile data)"
    lines = []
    for key in ("username", "name", "bio", "location", "tweets", "followers", "following", "url"):
        value = data.get(key)
        if value not in (None, ""):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_tweets(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no tweets)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('text', '(no text)')[:120]}")
        for key in ("username", "time", "likes", "retweets", "url"):
            value = item.get(key)
            if value not in (None, ""):
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_search_results(results: list[dict[str, Any]]) -> str:
    return format_tweets(results)


# ---------------------------------------------------------------------------
# DOM extraction
# ---------------------------------------------------------------------------

def extract_profile(driver) -> dict[str, Any]:
    username = ""
    try:
        parsed = urllib.parse.urlparse(driver.current_url or "")
        parts = [p for p in parsed.path.split("/") if p]
        if parts and parts[0] not in ("home", "explore", "notifications", "messages", "search", "i"):
            username = parts[0]
    except Exception:
        pass

    name = _text_first(driver, [
        "div[data-testid='UserName'] span span",
        "h2[role='heading'] span",
    ])
    bio = _text_first(driver, [
        "div[data-testid='UserDescription']",
        "div[data-testid='UserProfileHeader_Items'] ~ div",
    ])
    location = _text_first(driver, [
        "span[data-testid='UserLocation']",
    ])
    followers = _text_first(driver, [
        "a[href$='/followers'] span",
        "a[href*='verified_followers'] span",
    ])
    following = _text_first(driver, [
        "a[href$='/following'] span",
    ])
    tweets = _text_first(driver, [
        "div[data-testid='primaryColumn'] nav a[aria-selected='true'] span",
    ])
    return {
        "username": username,
        "name": name,
        "bio": bio,
        "location": location,
        "tweets": tweets,
        "followers": followers,
        "following": following,
        "url": _safe_url(driver),
    }


def extract_tweets(driver, limit: int = 10) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = _find_all_css(driver, [
        "article[data-testid='tweet']",
        "div[data-testid='tweet']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        text = ""
        try:
            text_el = _child_el(card, ["div[data-testid='tweetText']"])
            if text_el:
                text = (text_el.text or "").strip()
        except Exception:
            text = ""
        username = ""
        try:
            user_el = _child_el(card, ["div[data-testid='User-Name'] a"])
            if user_el:
                href = user_el.get_attribute("href") or ""
                parts = [p for p in urllib.parse.urlparse(href).path.split("/") if p]
                if parts:
                    username = parts[0]
        except Exception:
            username = ""
        url = ""
        try:
            time_el = _child_el(card, ["time"])
            if time_el:
                parent = time_el.find_element("xpath", "..")
                href = parent.get_attribute("href") or ""
                if href:
                    url = href if "://" in href else f"{TWITTER_HOME.rstrip('/')}{href}"
        except Exception:
            url = ""
        key = url or text[:60]
        if not key or key in seen:
            continue
        seen.add(key)
        timestamp = ""
        try:
            time_el = _child_el(card, ["time"])
            if time_el:
                timestamp = time_el.get_attribute("datetime") or ""
        except Exception:
            timestamp = ""
        likes = _child_text(card, ["div[data-testid='like'] span"])
        retweets = _child_text(card, ["div[data-testid='retweet'] span"])
        results.append({
            "text": text,
            "username": username,
            "time": timestamp,
            "likes": likes,
            "retweets": retweets,
            "url": url,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def type_tweet(driver, text: str) -> bool:
    """Open the compose box and type tweet text. Returns True on success."""
    compose = _find_one_css(driver, [
        "div[data-testid='tweetTextarea_0']",
        "div[aria-label='Tweet text'][contenteditable='true']",
        "div[aria-label='Post text'][contenteditable='true']",
    ])
    if compose is None:
        btn = _find_one_css(driver, [
            "a[data-testid='SideNav_NewTweet_Button']",
            "a[aria-label='Post']",
            "button[data-testid='SideNav_NewTweet_Button']",
        ])
        if btn is None:
            return False
        try:
            btn.click()
        except Exception:
            return False
        polite_jitter(0.5, 0.3)
        compose = _find_one_css(driver, [
            "div[data-testid='tweetTextarea_0']",
            "div[aria-label='Post text'][contenteditable='true']",
        ])
    if compose is None:
        return False
    try:
        compose.click()
        compose.send_keys(text)
    except Exception:
        return False
    return True


def submit_tweet(driver) -> bool:
    """Click the Tweet/Post submit button. Returns True on click."""
    btn = _find_one_css(driver, [
        "button[data-testid='tweetButtonInline']",
        "button[data-testid='tweetButton']",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def click_follow_button(driver) -> bool:
    btn = _find_one_xpath(driver, [
        "//div[@data-testid='placementTracking']//button[not(@aria-label='Following') and not(@aria-label='Unfollow')][@data-testid='follow']",
        "//button[@data-testid='follow']",
    ])
    if btn is None:
        return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def send_dm(driver, text: str) -> bool:
    box = _find_one_css(driver, [
        "div[data-testid='dmComposerTextInput']",
        "div[aria-label='Message'][contenteditable='true']",
    ])
    if box is None:
        return False
    try:
        box.click()
        box.send_keys(text)
    except Exception:
        return False
    send = _find_one_css(driver, [
        "button[data-testid='dmComposerSendButton']",
    ])
    if send is None:
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


def open_dm_thread(driver, username: str) -> bool:
    """Navigate to a DM thread with a user. Returns True if thread opened."""
    user = normalize_username(username)
    try:
        driver.get(f"{TWITTER_HOME}messages/compose?recipient_id={user}")
        polite_jitter(0.5, 0.3)
        return True
    except Exception:
        return False





__all__ = [
    "TWITTER_HOME",
    "TWITTER_HOST",
    "SECTIONS",
    "click_follow_button",
    "extract_profile",
    "extract_tweets",
    "format_open_result",
    "format_profile",
    "format_search_results",
    "format_tweets",
    "home_url",
    "is_twitter_url",
    "normalize_username",
    "open_dm_thread",
    "polite_jitter",
    "profile_url",
    "search_url",
    "section_url",
    "send_dm",
    "submit_tweet",
    "tweet_url",
    "type_tweet",
]

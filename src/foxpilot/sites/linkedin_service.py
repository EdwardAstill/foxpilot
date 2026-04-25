"""Service layer for LinkedIn (linkedin.com) browser workflows.

LinkedIn is aggressive about new-device challenges, so the recommended
foxpilot mode is `--zen` (reuse the user's already-signed-in session).
This module exposes URL helpers, slug builders, search-URL builders,
formatters, and best-effort DOM extraction stubs. Selenium imports are
local-to-function. Selectors live behind private `_find_*` helpers so a
single edit re-tunes the plugin when LinkedIn changes its markup.
"""

from __future__ import annotations

import random
import re
import time
import urllib.parse
from typing import Any, Optional


LINKEDIN_HOST = "www.linkedin.com"
LINKEDIN_HOME = f"https://{LINKEDIN_HOST}/"

SECTIONS = {
    "feed": "feed/",
    "mynetwork": "mynetwork/",
    "messaging": "messaging/",
    "notifications": "notifications/",
    "jobs": "jobs/",
}

_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-_%.]{1,99}$")


def is_linkedin_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value)
    host = (parsed.netloc or "").lower()
    return host.endswith("linkedin.com")


def home_url() -> str:
    return LINKEDIN_HOME


def section_url(section: str) -> str:
    """Resolve a known LinkedIn section name to a full URL."""
    key = (section or "").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown LinkedIn section: {section!r} "
            f"(expected one of: {', '.join(sorted(SECTIONS))})"
        )
    return f"{LINKEDIN_HOME}{SECTIONS[key]}"


def normalize_profile_slug(value: str) -> str:
    """Accept a LinkedIn profile slug or `/in/<slug>` URL and return the slug."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("empty profile slug")
    if "://" in raw or raw.startswith("www.") or raw.startswith("linkedin.com"):
        parsed = urllib.parse.urlparse(raw if "://" in raw else f"https://{raw}")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "in":
            raw = parts[1]
        elif parts:
            raw = parts[-1]
    raw = raw.strip("/")
    if not _SLUG_RE.match(raw):
        raise ValueError(f"invalid LinkedIn profile slug: {value!r}")
    return raw


def profile_url(slug_or_url: str) -> str:
    slug = normalize_profile_slug(slug_or_url)
    return f"{LINKEDIN_HOME}in/{slug}/"


def people_search_url(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("empty people-search query")
    encoded = urllib.parse.urlencode({"keywords": query.strip()})
    return f"{LINKEDIN_HOME}search/results/people/?{encoded}"


def jobs_search_url(query: str, location: Optional[str] = None) -> str:
    if not query or not query.strip():
        raise ValueError("empty jobs-search query")
    params: list[tuple[str, str]] = [("keywords", query.strip())]
    if location and location.strip():
        params.append(("location", location.strip()))
    encoded = urllib.parse.urlencode(params)
    return f"{LINKEDIN_HOME}jobs/search/?{encoded}"


def messaging_thread_url(thread_id: str) -> str:
    raw = (thread_id or "").strip()
    if not raw:
        raise ValueError("empty messaging thread id")
    return f"{LINKEDIN_HOME}messaging/thread/{urllib.parse.quote(raw, safe='')}/"


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
    for key in ("name", "headline", "location", "current_role", "url"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    skills = data.get("skills") or []
    if skills:
        lines.append("skills:")
        for skill in skills:
            lines.append(f"  - {skill}")
    return "\n".join(lines)


def format_people_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no people results)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('name', '(unknown)')}")
        for key in ("headline", "location", "url"):
            value = item.get(key)
            if value:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_jobs_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no job results)"
    lines = []
    for i, item in enumerate(results, 1):
        lines.append(f"[{i}] {item.get('title', '(no title)')}")
        for key in ("company", "location", "posted", "url"):
            value = item.get(key)
            if value:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_threads(results: list[dict[str, Any]]) -> str:
    if not results:
        return "(no message threads)"
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
# Politeness jitter (LinkedIn rate-limits aggressive scraping)
# ---------------------------------------------------------------------------

def polite_jitter(min_secs: float = 0.5, spread: float = 0.5) -> None:
    """Sleep a small randomised amount between paginated reads.

    Default: `0.5 + random()*0.5` seconds — i.e. 0.5s to 1.0s. Documented in
    the CLI doc so users know reads are intentionally slow.
    """
    time.sleep(min_secs + random.random() * spread)


# ---------------------------------------------------------------------------
# DOM extraction stubs (best effort; selectors via private helpers)
# ---------------------------------------------------------------------------

def extract_profile(driver) -> dict[str, Any]:
    """Read headline, location, current role, and skills from a profile page."""
    name = _text_first(driver, [
        "h1.text-heading-xlarge",
        "h1[class*='heading']",
    ])
    headline = _text_first(driver, [
        "div.text-body-medium.break-words",
        "[data-test-id='hero-headline']",
    ])
    location = _text_first(driver, [
        "span.text-body-small.inline.t-black--light.break-words",
        "[data-test-id='hero-location']",
    ])
    current_role = _text_first(driver, [
        "[aria-label='Current company'] span",
        "section[id*='experience'] li:first-child span[aria-hidden='true']",
    ])
    skills = _list_texts(driver, [
        "section[id*='skills'] span[aria-hidden='true']",
        "[data-test-id='skills-section'] li",
    ], limit=20)
    return {
        "name": name,
        "headline": headline,
        "location": location,
        "current_role": current_role,
        "skills": skills,
        "url": _safe_url(driver),
    }


def extract_people_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract people-search result cards. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "li.reusable-search__result-container",
        "div.entity-result",
        "li[class*='search-result']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        name = _child_text(card, ["span[aria-hidden='true']", "a span"])
        link = _child_attr(card, ["a.app-aware-link", "a[href*='/in/']"], "href")
        headline = _child_text(card, [
            "div.entity-result__primary-subtitle",
            "div[class*='subtitle']",
        ])
        location = _child_text(card, [
            "div.entity-result__secondary-subtitle",
            "div[class*='secondary']",
        ])
        if not name and not link:
            continue
        results.append({
            "name": name,
            "headline": headline,
            "location": location,
            "url": link,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def extract_jobs_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract job-search result cards. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "li.jobs-search-results__list-item",
        "div.job-card-container",
        "[data-job-id]",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        title = _child_text(card, [
            "a.job-card-list__title",
            "a[class*='job-card-list__title']",
            "h3",
        ])
        company = _child_text(card, [
            "span.job-card-container__primary-description",
            "[class*='company-name']",
            "h4",
        ])
        location = _child_text(card, [
            "li.job-card-container__metadata-item",
            "[class*='job-card-container__metadata']",
        ])
        link = _child_attr(card, [
            "a.job-card-list__title",
            "a[href*='/jobs/view/']",
        ], "href")
        posted = _child_text(card, [
            "time",
            "[class*='posted']",
        ])
        if not title and not link:
            continue
        results.append({
            "title": title,
            "company": company,
            "location": location,
            "posted": posted,
            "url": link,
        })
        if len(results) % 5 == 0:
            polite_jitter()
    return results


def extract_message_threads(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract recent inbox threads. Best effort."""
    results: list[dict[str, Any]] = []
    cards = _find_all_css(driver, [
        "li.msg-conversation-listitem",
        "div.msg-conversation-card",
        "[class*='conversation-listitem']",
    ])
    for card in cards:
        if len(results) >= limit:
            break
        peer = _child_text(card, [
            "h3.msg-conversation-listitem__participant-names",
            "[class*='participant-names']",
        ])
        snippet = _child_text(card, [
            "p.msg-conversation-card__message-snippet",
            "[class*='message-snippet']",
        ])
        when = _child_text(card, [
            "time.msg-conversation-listitem__time-stamp",
            "time",
        ])
        link = _child_attr(card, ["a"], "href")
        thread_id = ""
        if link and "/messaging/thread/" in link:
            try:
                thread_id = link.rstrip("/").split("/messaging/thread/")[1].split("/")[0]
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


def click_connect_button(driver) -> bool:
    """Click the Connect button on a profile page. Returns True on click."""
    btn = _find_one_xpath(driver, [
        "//button[.//span[normalize-space()='Connect']]",
        "//button[normalize-space()='Connect']",
        "//button[contains(@aria-label, 'Invite') and contains(@aria-label, 'connect')]",
    ])
    if btn is None:
        # Connect may be hidden behind the More menu.
        more = _find_one_xpath(driver, [
            "//button[normalize-space()='More']",
            "//button[contains(@aria-label, 'More actions')]",
        ])
        if more is None:
            return False
        try:
            more.click()
        except Exception:
            return False
        polite_jitter(0.3, 0.3)
        btn = _find_one_xpath(driver, [
            "//div[@role='menu']//*[normalize-space()='Connect']",
        ])
        if btn is None:
            return False
    try:
        btn.click()
    except Exception:
        return False
    return True


def confirm_send_invitation(driver, note: Optional[str] = None) -> bool:
    """Inside the Connect modal, optionally add a note, then click Send."""
    if note:
        add_note = _find_one_xpath(driver, [
            "//button[normalize-space()='Add a note']",
        ])
        if add_note is not None:
            try:
                add_note.click()
            except Exception:
                pass
            polite_jitter(0.3, 0.3)
            box = _find_one_css(driver, [
                "textarea#custom-message",
                "textarea[name='message']",
            ])
            if box is not None:
                try:
                    box.send_keys(note)
                except Exception:
                    pass
    send = _find_one_xpath(driver, [
        "//button[@aria-label='Send now']",
        "//button[normalize-space()='Send']",
        "//button[normalize-space()='Send now']",
    ])
    if send is None:
        return False
    try:
        send.click()
    except Exception:
        return False
    return True


def send_message(driver, text: str) -> bool:
    """Type into the message composer on a thread page and press Ctrl+Enter."""
    box = _find_one_css(driver, [
        "div.msg-form__contenteditable",
        "div[role='textbox'][contenteditable='true']",
    ])
    if box is None:
        return False
    try:
        box.click()
        box.send_keys(text)
    except Exception:
        return False
    send = _find_one_xpath(driver, [
        "//button[normalize-space()='Send']",
        "//button[contains(@class, 'msg-form__send-button')]",
    ])
    if send is None:
        return False
    try:
        send.click()
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------
# Private DOM helpers
# ---------------------------------------------------------------------------

def _safe_url(driver) -> str:
    try:
        return driver.current_url
    except Exception:
        return ""


def _find_one_css(driver, selectors: list[str]):
    from selenium.webdriver.common.by import By
    for selector in selectors:
        try:
            return driver.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
    return None


def _find_one_xpath(driver, xpaths: list[str]):
    from selenium.webdriver.common.by import By
    for xpath in xpaths:
        try:
            return driver.find_element(By.XPATH, xpath)
        except Exception:
            continue
    return None


def _find_all_css(driver, selectors: list[str]):
    from selenium.webdriver.common.by import By
    for selector in selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            if els:
                return els
        except Exception:
            continue
    return []


def _text_first(driver, selectors: list[str]) -> str:
    el = _find_one_css(driver, selectors)
    if el is None:
        return ""
    try:
        return (el.text or "").strip()
    except Exception:
        return ""


def _list_texts(driver, selectors: list[str], limit: int = 50) -> list[str]:
    els = _find_all_css(driver, selectors)
    out: list[str] = []
    for el in els:
        if len(out) >= limit:
            break
        try:
            text = (el.text or "").strip()
        except Exception:
            continue
        if text and text not in out:
            out.append(text)
    return out


def _child_text(parent, selectors: list[str]) -> str:
    from selenium.webdriver.common.by import By
    for selector in selectors:
        try:
            el = parent.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        try:
            text = (el.text or "").strip()
        except Exception:
            continue
        if text:
            return text
    return ""


def _child_attr(parent, selectors: list[str], attr: str) -> str:
    from selenium.webdriver.common.by import By
    for selector in selectors:
        try:
            el = parent.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        try:
            value = el.get_attribute(attr)
        except Exception:
            continue
        if value:
            return value
    return ""


__all__ = [
    "LINKEDIN_HOME",
    "LINKEDIN_HOST",
    "SECTIONS",
    "click_connect_button",
    "confirm_send_invitation",
    "extract_jobs_results",
    "extract_message_threads",
    "extract_people_results",
    "extract_profile",
    "format_jobs_results",
    "format_open_result",
    "format_people_results",
    "format_profile",
    "format_threads",
    "home_url",
    "is_linkedin_url",
    "jobs_search_url",
    "messaging_thread_url",
    "normalize_profile_slug",
    "people_search_url",
    "polite_jitter",
    "profile_url",
    "section_url",
    "send_message",
]

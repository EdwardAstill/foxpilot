"""Service layer for Microsoft Teams web (teams.microsoft.com) workflows.

Teams web is an Electron-style SPA. Some surfaces render inside an embedded
iframe (`iframe#embedded-page-container`). DOM extraction helpers route
through `_switch_to_main_iframe(driver)` before scraping. Selectors live in
private `_find_*` helpers so future tuning is one edit.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Literal


TEAMS_HOST = "teams.microsoft.com"
TEAMS_HOME = f"https://{TEAMS_HOST}/"

Section = Literal["chat", "teams", "calendar", "calls", "activity"]

TEAMS_SECTIONS: dict[str, str] = {
    "chat": "_#/conversations",
    "chats": "_#/conversations",
    "teams": "_#/discover",
    "calendar": "_#/calendarv2",
    "calls": "_#/calls",
    "activity": "_#/activity",
}

_SECTION_ALIASES = {
    "messages": "chat",
    "conversation": "chat",
    "conversations": "chat",
    "channels": "teams",
    "team": "teams",
    "schedule": "calendar",
    "meetings": "calendar",
    "call": "calls",
    "feed": "activity",
    "notifications": "activity",
}


def normalize_section(section: str) -> Section:
    value = (section or "chat").strip().lower()
    value = _SECTION_ALIASES.get(value, value)
    if value not in TEAMS_SECTIONS:
        expected = ", ".join(sorted({s for s in TEAMS_SECTIONS}))
        raise ValueError(f"unknown Teams section '{section}' (expected: {expected})")
    if value == "chats":
        value = "chat"
    return value  # type: ignore[return-value]


def build_teams_url(section: str = "chat") -> str:
    """Build a stable Teams landing URL for a high-level section."""
    normalized = normalize_section(section)
    fragment = TEAMS_SECTIONS[normalized]
    if not fragment:
        return TEAMS_HOME
    return f"{TEAMS_HOME}{fragment}"


def is_teams_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(_ensure_url_scheme(value))
    host = (parsed.netloc or "").lower()
    return host == TEAMS_HOST or host.endswith(".teams.microsoft.com") or host.endswith("teams.live.com")


def normalize_teams_target(target: str) -> str:
    """Return a navigable Teams URL from a URL or section name."""
    value = (target or "chat").strip()
    if _looks_like_url(value):
        url = _ensure_url_scheme(value)
        if not is_teams_url(url):
            raise ValueError(f"not a Teams URL: {target}")
        return url
    return build_teams_url(value)


def to_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def format_open_result(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in ("title", "url", "section"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_chats(chats: list[dict[str, Any]]) -> str:
    if not chats:
        return "(no chats found)"
    lines: list[str] = []
    for index, chat in enumerate(chats, 1):
        name = chat.get("name") or "(unnamed)"
        lines.append(f"[{index}] {name}")
        for key in ("snippet", "timestamp", "unread"):
            value = chat.get(key)
            if value not in (None, "", False):
                lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def format_messages(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return "(no messages found)"
    lines: list[str] = []
    for index, msg in enumerate(messages, 1):
        author = msg.get("author") or "(unknown)"
        ts = msg.get("timestamp") or ""
        body = msg.get("body") or ""
        header = f"[{index}] {author}"
        if ts:
            header = f"{header} - {ts}"
        lines.append(header)
        if body:
            lines.append(f"    {body}")
    return "\n".join(lines)


def format_teams_list(teams: list[dict[str, Any]]) -> str:
    if not teams:
        return "(no teams found)"
    lines: list[str] = []
    for index, team in enumerate(teams, 1):
        name = team.get("name") or "(unnamed)"
        lines.append(f"[{index}] {name}")
        channels = team.get("channels") or []
        if channels:
            lines.append(f"    channels: {', '.join(str(c) for c in channels)}")
    return "\n".join(lines)


def format_post_result(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key in ("status", "target", "message", "url"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DOM extraction stubs — best-effort selectors, easy to retune.
# ---------------------------------------------------------------------------


def extract_chats(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract recent chats from the chats list pane. Best effort."""
    _switch_to_main_iframe(driver)
    rows = _find_all(driver, "css selector", "[data-tid='chat-list-item'], li[role='treeitem']")
    chats: list[dict[str, Any]] = []
    for row in rows[: max(limit, 0)]:
        try:
            name_el = _find_one_within(row, "css selector", "[data-tid='chat-list-item-title'], .ts-title-text")
            snippet_el = _find_one_within(row, "css selector", "[data-tid='chat-list-item-preview'], .ts-message-preview")
            ts_el = _find_one_within(row, "css selector", "[data-tid='chat-list-item-timestamp'], time")
        except Exception:
            continue
        name = _text_of(name_el) or _text_of(row)
        if not name:
            continue
        chats.append(
            {
                "name": name,
                "snippet": _text_of(snippet_el),
                "timestamp": _text_of(ts_el),
                "unread": "unread" in (row.get_attribute("class") or "").lower(),
            }
        )
    return chats


def extract_messages(driver, limit: int = 50) -> list[dict[str, Any]]:
    """Extract messages visible in the current chat thread. Best effort."""
    _switch_to_main_iframe(driver)
    rows = _find_all(driver, "css selector", "[data-tid='chat-pane-message'], [role='listitem'][data-tid*='message']")
    messages: list[dict[str, Any]] = []
    for row in rows[-max(limit, 0):] if limit else rows:
        author_el = _find_one_within(row, "css selector", "[data-tid='message-author-name'], .author")
        body_el = _find_one_within(row, "css selector", "[data-tid='message-body-content'], .message-body")
        ts_el = _find_one_within(row, "css selector", "time, [data-tid='message-timestamp']")
        messages.append(
            {
                "author": _text_of(author_el),
                "body": _text_of(body_el) or _text_of(row),
                "timestamp": _text_of(ts_el),
            }
        )
    return messages


def extract_teams(driver) -> list[dict[str, Any]]:
    """Extract joined teams from the teams pane. Best effort."""
    _switch_to_main_iframe(driver)
    rows = _find_all(driver, "css selector", "[data-tid='team-channel-list'] [data-tid='team'], [role='treeitem'][aria-level='1']")
    teams: list[dict[str, Any]] = []
    for row in rows:
        name = _text_of(_find_one_within(row, "css selector", "[data-tid='team-name'], .ts-title-text")) or _text_of(row)
        if not name:
            continue
        channels: list[str] = []
        chan_nodes = _find_all_within(row, "css selector", "[data-tid='channel-name'], [aria-level='2']")
        for c in chan_nodes:
            ct = _text_of(c)
            if ct:
                channels.append(ct)
        teams.append({"name": name, "channels": channels})
    return teams


def open_chat(driver, name: str) -> dict[str, Any]:
    """Open a 1:1 or group chat by visible name."""
    _switch_to_main_iframe(driver)
    from selenium.webdriver.common.by import By

    literal = _xpath_literal(name)
    xpaths = [
        f"//*[@data-tid='chat-list-item'][.//*[contains(normalize-space(.), {literal})]]",
        f"//li[@role='treeitem'][.//*[contains(normalize-space(.), {literal})]]",
        f"//*[contains(@aria-label, {literal})]",
    ]
    for xpath in xpaths:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except Exception:
            continue
        for element in elements:
            try:
                if element.is_displayed():
                    element.click()
                    return {"name": name, "url": getattr(driver, "current_url", "")}
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    return {"name": name, "url": getattr(driver, "current_url", "")}
                except Exception:
                    continue
    raise RuntimeError(f"no visible Teams chat matching '{name}'")


def open_channel(driver, team: str, channel: str) -> dict[str, Any]:
    """Expand a team and click a channel by visible name."""
    _switch_to_main_iframe(driver)
    from selenium.webdriver.common.by import By

    team_literal = _xpath_literal(team)
    chan_literal = _xpath_literal(channel)
    team_xpaths = [
        f"//*[@role='treeitem'][@aria-level='1'][.//*[contains(normalize-space(.), {team_literal})]]",
        f"//*[contains(@aria-label, {team_literal})][@role='treeitem']",
    ]
    for xpath in team_xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        el.click()
                        break
                except Exception:
                    continue
        except Exception:
            continue

    chan_xpaths = [
        f"//*[@role='treeitem'][@aria-level='2'][.//*[contains(normalize-space(.), {chan_literal})]]",
        f"//*[contains(@aria-label, {chan_literal})][@role='treeitem']",
    ]
    for xpath in chan_xpaths:
        try:
            for el in driver.find_elements(By.XPATH, xpath):
                try:
                    if el.is_displayed():
                        el.click()
                        return {"team": team, "channel": channel, "url": getattr(driver, "current_url", "")}
                except Exception:
                    continue
        except Exception:
            continue
    raise RuntimeError(f"no visible Teams channel '{channel}' under team '{team}'")


def post_message(driver, target: str, message: str) -> dict[str, Any]:
    """Type a message into the active compose box and press Enter."""
    _switch_to_main_iframe(driver)
    box = _find_compose_box(driver)
    if box is None:
        raise RuntimeError("could not find Teams compose box")
    try:
        box.click()
    except Exception:
        pass
    box.send_keys(message)
    from selenium.webdriver.common.keys import Keys
    box.send_keys(Keys.ENTER)
    return {"status": "posted", "target": target, "message": message, "url": getattr(driver, "current_url", "")}


def _find_compose_box(driver):
    selectors = [
        "div[data-tid='ckeditor'][contenteditable='true']",
        "[role='textbox'][contenteditable='true']",
        "div[aria-label*='Type a message' i]",
        "div[aria-label*='message' i][contenteditable='true']",
    ]
    for selector in selectors:
        elem = _find_one(driver, "css selector", selector)
        if elem is not None:
            return elem
    return None


def _switch_to_main_iframe(driver) -> bool:
    """Switch into Teams' main embedded iframe if present.

    Returns True if a switch happened. Always tries to return to default
    content first so callers can call this idempotently.
    """
    try:
        driver.switch_to.default_content()
    except Exception:
        return False
    from selenium.webdriver.common.by import By
    try:
        frame = driver.find_element(By.CSS_SELECTOR, "iframe#embedded-page-container")
    except Exception:
        return False
    try:
        driver.switch_to.frame(frame)
        return True
    except Exception:
        return False


def _find_one(driver, by, selector):
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return driver.find_element(by_obj, selector)
    except Exception:
        return None


def _find_all(driver, by, selector):
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return driver.find_elements(by_obj, selector)
    except Exception:
        return []


def _find_one_within(parent, by, selector):
    if parent is None:
        return None
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return parent.find_element(by_obj, selector)
    except Exception:
        return None


def _find_all_within(parent, by, selector):
    if parent is None:
        return []
    from selenium.webdriver.common.by import By
    by_obj = By.CSS_SELECTOR if by == "css selector" else by
    try:
        return parent.find_elements(by_obj, selector)
    except Exception:
        return []


def _text_of(element) -> str:
    if element is None:
        return ""
    try:
        text = element.text or element.get_attribute("aria-label") or ""
    except Exception:
        return ""
    return " ".join(text.split())


def _looks_like_url(value: str) -> bool:
    value = (value or "").strip()
    if not value or any(ch.isspace() for ch in value):
        return False
    return "://" in value or "." in value.split("/", 1)[0]


def _ensure_url_scheme(value: str) -> str:
    return value if "://" in value else f"https://{value}"


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


__all__ = [
    "TEAMS_HOME",
    "TEAMS_HOST",
    "TEAMS_SECTIONS",
    "build_teams_url",
    "extract_chats",
    "extract_messages",
    "extract_teams",
    "format_chats",
    "format_messages",
    "format_open_result",
    "format_post_result",
    "format_teams_list",
    "is_teams_url",
    "normalize_section",
    "normalize_teams_target",
    "open_chat",
    "open_channel",
    "post_message",
    "to_json",
]

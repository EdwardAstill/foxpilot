"""YouTube Music browser workflow helpers.

YouTube Music is a YouTube-frontend, so URL shapes parallel youtube.com.
Selectors below are best-effort and likely to drift; DOM-fragile lookups
live in clearly named ``_find_*`` / ``_extract_*`` helpers so future
tuning is one edit.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Optional

# Reuse YouTube origin set / video id parser where shapes are shared.
from foxpilot.sites.youtube_service import extract_video_id  # re-exported helper


YT_MUSIC_HOST = "music.youtube.com"
YT_MUSIC_HOME = f"https://{YT_MUSIC_HOST}/"

SECTIONS: dict[str, str] = {
    "home": YT_MUSIC_HOME,
    "explore": f"{YT_MUSIC_HOME}explore",
    "library": f"{YT_MUSIC_HOME}library",
    "playlists": f"{YT_MUSIC_HOME}library/playlists",
}

# Search "kind" → query parameter / chip mapping.
# YouTube Music routes filtered searches via the `EgWKAQ...` style continuation
# tokens — for stable URL building we just send the raw query and rely on a
# best-effort kind hint that the CLI passes through to the chip clicker.
SEARCH_KINDS = {"track", "song", "video", "artist", "album", "playlist"}


def is_youtube_music_url(value: str) -> bool:
    if not value:
        return False
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    return (parsed.netloc or "").lower() == YT_MUSIC_HOST


def section_url(name: str) -> str:
    key = (name or "home").strip().lower()
    if key not in SECTIONS:
        raise ValueError(
            f"unknown section: {name!r} (expected one of {sorted(SECTIONS)})"
        )
    return SECTIONS[key]


def youtube_music_search_url(query: str, kind: str = "") -> str:
    """Build a YouTube Music search URL for a free-text query.

    ``kind`` is preserved as a hint; the search results page exposes
    chips ("Songs", "Videos", "Albums", ...) which we click client-side
    rather than encoding into the URL.
    """
    if not query or not query.strip():
        raise ValueError("search query cannot be empty")
    encoded = urllib.parse.quote(query.strip())
    return f"{YT_MUSIC_HOME}search?q={encoded}"


def normalize_kind(kind: str) -> str:
    if not kind:
        return ""
    cleaned = kind.strip().lower()
    if cleaned in {"song", "songs"}:
        cleaned = "track"
    if cleaned not in SEARCH_KINDS and cleaned != "track":
        raise ValueError(
            f"unknown search kind: {kind!r} "
            f"(expected one of track, artist, album, playlist)"
        )
    return cleaned


def watch_url_for(video_id: str) -> str:
    return f"{YT_MUSIC_HOME}watch?v={video_id}"


def normalize_play_target(value: str) -> str:
    """Resolve a 'play' argument to a music.youtube.com URL or pass-through query.

    Returns either a fully-qualified watch URL (when a video id is recognised)
    or a search URL (when the input looks like free text).
    """
    value = (value or "").strip()
    if not value:
        raise ValueError("play target cannot be empty")
    if is_youtube_music_url(value):
        return value
    vid = extract_video_id(value)
    if vid:
        return watch_url_for(vid)
    return youtube_music_search_url(value)


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


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No YouTube Music results found."
    lines: list[str] = []
    for i, item in enumerate(results, 1):
        title = item.get("title") or "(no title)"
        lines.append(f"[{i}] {title}")
        for key in ("kind", "artist", "album", "duration", "url"):
            val = item.get(key)
            if not val:
                continue
            if key == "url":
                lines.append(f"    {val}")
            else:
                lines.append(f"    {key}: {val}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_now_playing(data: dict[str, Any]) -> str:
    if not data or not data.get("title"):
        return "(nothing playing)"
    bits = [
        f"title: {data.get('title', '')}",
        f"artist: {data.get('artist', '')}",
        f"album: {data.get('album', '')}",
        f"position: {data.get('position', '')}",
        f"duration: {data.get('duration', '')}",
        f"url: {data.get('url', '')}",
    ]
    return "\n".join(b for b in bits if b.split(": ", 1)[1])


def format_playlists(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(no playlists found)"
    lines = []
    for item in items:
        name = item.get("name") or "(unnamed)"
        count = item.get("track_count")
        suffix = f" ({count} tracks)" if count else ""
        lines.append(f"- {name}{suffix}")
        url = item.get("url")
        if url:
            lines.append(f"    {url}")
    return "\n".join(lines)


def format_playlist_tracks(data: dict[str, Any]) -> str:
    name = data.get("name") or "(unnamed playlist)"
    tracks = data.get("tracks") or []
    if not tracks:
        return f"{name}\n(no tracks found)"
    lines = [name]
    for i, t in enumerate(tracks, 1):
        title = t.get("title") or "(no title)"
        artist = t.get("artist") or ""
        suffix = f" — {artist}" if artist else ""
        lines.append(f"  {i:>3}. {title}{suffix}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# DOM extraction (best-effort, selectors WILL drift)
# ---------------------------------------------------------------------------


def extract_search_results(driver, limit: int = 10, kind: str = "") -> list[dict[str, Any]]:
    from selenium.webdriver.common.by import By

    results: list[dict[str, Any]] = []
    try:
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "ytmusic-responsive-list-item-renderer, ytmusic-card-shelf-renderer",
        )
    except Exception:
        return results

    for row in rows:
        if len(results) >= limit:
            break
        try:
            if not row.is_displayed():
                continue
        except Exception:
            continue
        item = _extract_search_row(row)
        if not item.get("title"):
            continue
        if kind and item.get("kind") and item["kind"] != kind:
            continue
        results.append(item)
    return results


def _extract_search_row(row) -> dict[str, Any]:
    from selenium.webdriver.common.by import By

    title_el = _first(row, By.CSS_SELECTOR, "yt-formatted-string.title, a.yt-simple-endpoint")
    title = (title_el.text.strip() if title_el else "").strip()
    href = title_el.get_attribute("href") if title_el else ""

    subtitles = []
    try:
        subs = row.find_elements(By.CSS_SELECTOR, "yt-formatted-string.subtitle, yt-formatted-string.flex-column")
        subtitles = [s.text.strip() for s in subs if s.text.strip()]
    except Exception:
        pass

    kind = ""
    if subtitles:
        head = subtitles[0].lower()
        if "song" in head or "track" in head:
            kind = "track"
        elif "album" in head:
            kind = "album"
        elif "artist" in head:
            kind = "artist"
        elif "playlist" in head:
            kind = "playlist"
        elif "video" in head:
            kind = "video"

    return {
        "title": title,
        "url": href or "",
        "kind": kind,
        "artist": subtitles[1] if len(subtitles) >= 2 else "",
        "album": subtitles[2] if len(subtitles) >= 3 else "",
        "duration": subtitles[-1] if subtitles and ":" in subtitles[-1] else "",
    }


def extract_now_playing(driver) -> dict[str, Any]:
    """Return current track metadata from the persistent player bar."""
    bar = _find_player_bar(driver)
    if bar is None:
        return {}
    return _extract_track_metadata(driver, bar)


def _find_player_bar(driver):
    """Locate the persistent player bar at the bottom of the YT Music UI."""
    from selenium.webdriver.common.by import By

    selectors = [
        "ytmusic-player-bar",
        "#player-bar",
        "div.ytmusic-player-bar",
    ]
    for sel in selectors:
        el = _first(driver, By.CSS_SELECTOR, sel)
        if el is not None:
            return el
    return None


def _extract_track_metadata(driver, bar) -> dict[str, Any]:
    from selenium.webdriver.common.by import By

    title_el = _first(bar, By.CSS_SELECTOR, ".title, yt-formatted-string.title")
    byline_el = _first(bar, By.CSS_SELECTOR, ".byline, yt-formatted-string.byline")
    time_el = _first(bar, By.CSS_SELECTOR, ".time-info, span.time-info")

    title = (title_el.text.strip() if title_el else "")
    byline = (byline_el.text.strip() if byline_el else "")
    time_text = (time_el.text.strip() if time_el else "")

    artist = ""
    album = ""
    if byline:
        parts = [p.strip() for p in byline.split("•") if p.strip()]
        if parts:
            artist = parts[0]
        if len(parts) >= 2:
            album = parts[1]

    position = ""
    duration = ""
    if "/" in time_text:
        position, _, duration = time_text.partition("/")
        position = position.strip()
        duration = duration.strip()

    return {
        "title": title,
        "artist": artist,
        "album": album,
        "byline": byline,
        "position": position,
        "duration": duration,
        "url": getattr(driver, "current_url", ""),
    }


def extract_playlists(driver) -> list[dict[str, Any]]:
    from selenium.webdriver.common.by import By

    items: list[dict[str, Any]] = []
    try:
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "ytmusic-two-row-item-renderer, ytmusic-responsive-list-item-renderer",
        )
    except Exception:
        return items
    for row in rows:
        try:
            if not row.is_displayed():
                continue
        except Exception:
            continue
        title_el = _first(row, By.CSS_SELECTOR, "yt-formatted-string.title, a.yt-simple-endpoint")
        if not title_el:
            continue
        name = title_el.text.strip()
        if not name:
            continue
        href = title_el.get_attribute("href") or ""
        items.append({"name": name, "url": href, "track_count": ""})
    return items


def extract_playlist_tracks(driver, name: str = "") -> dict[str, Any]:
    from selenium.webdriver.common.by import By

    title_el = _first(driver, By.CSS_SELECTOR, "ytmusic-detail-header-renderer h2, h2.title")
    title = (title_el.text.strip() if title_el else name)

    tracks: list[dict[str, Any]] = []
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "ytmusic-responsive-list-item-renderer")
    except Exception:
        rows = []
    for row in rows:
        item = _extract_search_row(row)
        if item.get("title"):
            tracks.append(
                {
                    "title": item["title"],
                    "artist": item.get("artist", ""),
                    "album": item.get("album", ""),
                    "duration": item.get("duration", ""),
                    "url": item.get("url", ""),
                }
            )
    return {"name": title, "tracks": tracks}


# ---------------------------------------------------------------------------
# Internal selector helper
# ---------------------------------------------------------------------------


def _first(parent, by, selector):
    try:
        return parent.find_element(by, selector)
    except Exception:
        return None

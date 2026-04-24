"""YouTube-specific browser workflow helpers."""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Optional


YOUTUBE_ORIGINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def is_youtube_url(value: str) -> bool:
    """Return True when value is a YouTube URL Foxpilot understands."""
    parsed = _parse_url(value)
    return parsed.netloc.lower() in YOUTUBE_ORIGINS


def extract_video_id(value: str) -> Optional[str]:
    """Extract a YouTube video id from common URL shapes or a bare id."""
    value = value.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value

    parsed = _parse_url(value)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if host == "youtu.be" and path_parts:
        return path_parts[0]

    if host in YOUTUBE_ORIGINS:
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("v"):
            return query["v"][0]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
            return path_parts[1]

    return None


def normalize_youtube_url(value: str) -> str:
    """Normalize video URLs to canonical watch URLs; queries become search URLs."""
    video_id = extract_video_id(value)
    if video_id:
        return f"https://www.youtube.com/watch?v={video_id}"
    if is_youtube_url(value):
        return value
    return youtube_search_url(value)


def youtube_search_url(query: str) -> str:
    encoded = urllib.parse.urlencode({"search_query": query})
    return f"https://www.youtube.com/results?{encoded}"


def format_search_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No YouTube results found."

    lines: list[str] = []
    for i, result in enumerate(results, 1):
        title = result.get("title") or "(no title)"
        lines.append(f"[{i}] {title}")
        for key in ("url", "channel", "duration", "views", "published"):
            value = result.get(key)
            if not value:
                continue
            if key == "url":
                lines.append(f"    {value}")
            else:
                lines.append(f"    {key}: {value}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_metadata(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "No YouTube metadata found."

    preferred = [
        "type",
        "title",
        "url",
        "video_id",
        "channel",
        "channel_url",
        "views",
        "published",
        "duration",
        "description",
        "is_live",
        "is_short",
    ]
    lines = []
    for key in preferred:
        value = metadata.get(key)
        if value not in (None, "", []):
            lines.append(f"{key}: {value}")
    for key, value in metadata.items():
        if key not in preferred and value not in (None, "", []):
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def format_transcript(transcript: dict[str, Any], output_format: str = "text") -> str:
    output_format = output_format.lower()
    if output_format == "json":
        return json.dumps(transcript, ensure_ascii=False, indent=2)
    if output_format == "segments":
        lines = []
        for segment in transcript.get("segments", []):
            stamp = _format_timestamp(float(segment.get("start", 0.0)))
            lines.append(f"[{stamp}] {segment.get('text', '')}")
        return "\n".join(lines)
    if output_format == "srt":
        return _format_srt(transcript.get("segments", []))
    return str(transcript.get("text") or "")


def extract_search_results(driver, limit: int = 10) -> list[dict[str, Any]]:
    """Extract visible video results from a YouTube search results page."""
    from selenium.webdriver.common.by import By

    results: list[dict[str, Any]] = []
    renderers = driver.find_elements(
        By.CSS_SELECTOR,
        "ytd-video-renderer, ytd-rich-item-renderer, ytd-grid-video-renderer",
    )

    for renderer in renderers:
        if len(results) >= limit:
            break
        try:
            if not renderer.is_displayed():
                continue
        except Exception:
            continue

        link = _first_element(
            renderer,
            By.CSS_SELECTOR,
            "a#video-title, a#video-title-link, a.yt-simple-endpoint[href*='watch']",
        )
        if not link:
            continue

        title = (
            link.get_attribute("title")
            or link.get_attribute("aria-label")
            or link.text
            or ""
        ).strip()
        href = link.get_attribute("href") or ""
        video_id = extract_video_id(href)
        if not video_id:
            continue

        channel_el = _first_element(
            renderer,
            By.CSS_SELECTOR,
            "ytd-channel-name a, a.yt-simple-endpoint[href*='@']",
        )
        metadata = _texts_by_selector(renderer, By.CSS_SELECTOR, "#metadata-line span")
        thumb = _first_element(renderer, By.CSS_SELECTOR, "img")

        results.append(
            {
                "title": _clean_title(title),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "video_id": video_id,
                "channel": channel_el.text.strip() if channel_el else "",
                "channel_url": channel_el.get_attribute("href") if channel_el else "",
                "duration": _first_text_by_selector(
                    renderer,
                    By.CSS_SELECTOR,
                    "ytd-thumbnail-overlay-time-status-renderer",
                ),
                "views": metadata[0] if len(metadata) >= 1 else "",
                "published": metadata[1] if len(metadata) >= 2 else "",
                "thumbnail": thumb.get_attribute("src") if thumb else "",
            }
        )

    return results


def extract_video_metadata(driver) -> dict[str, Any]:
    """Extract metadata from the current YouTube video page."""
    from selenium.webdriver.common.by import By

    url = driver.current_url
    video_id = extract_video_id(url) or ""
    title = _text_by_selectors(
        driver,
        [
            "h1 yt-formatted-string",
            "h1.title",
            "meta[name='title']",
        ],
        attr_fallbacks={"meta[name='title']": "content"},
    )
    channel_el = _first_driver_element(
        driver,
        By.CSS_SELECTOR,
        "ytd-watch-metadata ytd-channel-name a, #owner ytd-channel-name a, ytd-video-owner-renderer a",
    )
    description = _text_by_selectors(
        driver,
        [
            "#description-inline-expander",
            "ytd-text-inline-expander",
            "meta[name='description']",
        ],
        attr_fallbacks={"meta[name='description']": "content"},
    )
    views = _text_by_selectors(driver, ["#info span.bold", "span.view-count"])
    published = _text_by_selectors(
        driver,
        ["#info-strings yt-formatted-string", "#date yt-formatted-string"],
    )
    duration = driver.execute_script(
        """
        const video = document.querySelector('video');
        if (!video || !Number.isFinite(video.duration)) return '';
        const seconds = Math.round(video.duration);
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
                 : `${m}:${String(s).padStart(2, '0')}`;
        """
    )

    return {
        "type": "video" if video_id else "youtube",
        "title": title or driver.title,
        "url": url,
        "video_id": video_id,
        "channel": channel_el.text.strip() if channel_el else "",
        "channel_url": channel_el.get_attribute("href") if channel_el else "",
        "views": views,
        "published": published,
        "duration": duration or "",
        "description": description,
        "is_live": "watch?v=" in url and "live" in driver.page_source[:5000].lower(),
        "is_short": "/shorts/" in url,
    }


def extract_transcript(driver, lang: Optional[str] = None) -> dict[str, Any]:
    """Best-effort extraction of transcript segments from the loaded page."""
    segments = _extract_transcript_from_page_data(driver, lang=lang)
    if not segments:
        segments = _extract_transcript_from_panel(driver)
    if not segments:
        raise RuntimeError(
            "no transcript found; captions may be disabled, unavailable, or hidden behind a changed YouTube UI"
        )

    text = "\n".join(segment["text"] for segment in segments if segment.get("text"))
    metadata = extract_video_metadata(driver)
    return {
        "title": metadata.get("title", ""),
        "url": driver.current_url,
        "language": lang or "",
        "segments": segments,
        "text": text,
    }


def _extract_transcript_from_page_data(driver, lang: Optional[str] = None) -> list[dict[str, Any]]:
    from selenium.webdriver.common.by import By

    tracks = driver.execute_script(
        """
        const player = window.ytInitialPlayerResponse || {};
        const list = player?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
        return list.map(t => ({
            baseUrl: t.baseUrl || '',
            languageCode: t.languageCode || '',
            name: t.name?.simpleText || (t.name?.runs || []).map(r => r.text).join('')
        }));
        """
    )
    if not tracks:
        return []

    chosen = None
    if lang:
        for track in tracks:
            if track.get("languageCode") == lang:
                chosen = track
                break
    chosen = chosen or tracks[0]
    url = chosen.get("baseUrl")
    if not url:
        return []

    driver.execute_script("window.open(arguments[0], '_blank');", url)
    handles = driver.window_handles
    current = driver.current_window_handle
    try:
        driver.switch_to.window(handles[-1])
        return _parse_timed_text_xml(driver.page_source)
    finally:
        try:
            driver.close()
        except Exception:
            pass
        try:
            driver.switch_to.window(current)
        except Exception:
            pass


def _extract_transcript_from_panel(driver) -> list[dict[str, Any]]:
    from selenium.webdriver.common.by import By

    selectors = [
        "button[aria-label*='transcript' i]",
        "yt-button-shape button[aria-label*='transcript' i]",
        "ytd-menu-service-item-renderer",
    ]
    for selector in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, selector):
                label = " ".join(
                    [
                        el.text or "",
                        el.get_attribute("aria-label") or "",
                        el.get_attribute("title") or "",
                    ]
                ).lower()
                if "transcript" in label and el.is_displayed():
                    el.click()
                    break
        except Exception:
            continue

    import time

    time.sleep(1.0)
    rows = driver.find_elements(
        By.CSS_SELECTOR,
        "ytd-transcript-segment-renderer, ytd-transcript-segment-list-renderer [role='button']",
    )
    segments: list[dict[str, Any]] = []
    for row in rows:
        text = row.text.strip()
        if not text:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 2:
            start = _parse_timestamp_to_seconds(lines[0])
            segment_text = " ".join(lines[1:])
        else:
            start = 0.0
            segment_text = lines[0]
        segments.append({"start": start, "duration": 0.0, "text": segment_text})
    return segments


def _parse_timed_text_xml(text: str) -> list[dict[str, Any]]:
    import html
    import xml.etree.ElementTree as ET

    segments: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return segments

    for node in root.iter("text"):
        raw_text = "".join(node.itertext()).strip()
        if not raw_text:
            continue
        segments.append(
            {
                "start": float(node.attrib.get("start", "0") or 0),
                "duration": float(node.attrib.get("dur", "0") or 0),
                "text": html.unescape(raw_text),
            }
        )
    return segments


def _format_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, 1):
        start = float(segment.get("start", 0.0))
        end = start + float(segment.get("duration", 0.0) or 2.0)
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}",
                    str(segment.get("text", "")),
                ]
            )
        )
    return "\n\n".join(blocks)


def _format_timestamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _format_srt_timestamp(seconds: float) -> str:
    millis = int(round((seconds - int(seconds)) * 1000))
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def _parse_timestamp_to_seconds(value: str) -> float:
    parts = [int(p) for p in value.split(":") if p.isdigit()]
    if len(parts) == 3:
        return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    return 0.0


def _first_element(parent, by, selector):
    try:
        return parent.find_element(by, selector)
    except Exception:
        return None


def _first_driver_element(driver, by, selector):
    try:
        return driver.find_element(by, selector)
    except Exception:
        return None


def _texts_by_selector(parent, by, selector) -> list[str]:
    try:
        els = [e for e in parent.find_elements(by, selector) if e.is_displayed()]
        return [e.text.strip() for e in els if e.text.strip()]
    except Exception:
        return []


def _first_text_by_selector(parent, by, selector) -> str:
    texts = _texts_by_selector(parent, by, selector)
    return texts[0] if texts else ""


def _text_by_selectors(
    driver,
    selectors: list[str],
    attr_fallbacks: Optional[dict[str, str]] = None,
) -> str:
    from selenium.webdriver.common.by import By

    attr_fallbacks = attr_fallbacks or {}
    for selector in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            attr = attr_fallbacks.get(selector)
            value = el.get_attribute(attr) if attr else el.text
            if value:
                return value.strip()
        except Exception:
            continue
    return ""


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+-\s+YouTube$", "", title).strip()
    title = re.sub(r"\s+", " ", title)
    return title


def _parse_url(value: str) -> urllib.parse.ParseResult:
    value = value.strip()
    if value.startswith("www.") or value.startswith("m.") or value.startswith("youtu.be/"):
        value = "https://" + value
    return urllib.parse.urlparse(value)

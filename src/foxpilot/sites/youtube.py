"""Typer command branch for YouTube workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.youtube_service import (
    extract_search_results,
    extract_transcript,
    extract_video_metadata,
    format_metadata,
    format_search_results,
    format_transcript,
    normalize_youtube_url,
    youtube_search_url,
)


app = typer.Typer(
    help="YouTube search, metadata, transcripts, and playlist helpers.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    """Set the browser factory used by this branch.

    The top-level CLI injects its mode-aware factory so global flags like
    --zen, --visible, and --headless-mode keep working for site branches.
    """
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help():
    """Show YouTube branch help and examples."""
    typer.echo(
        """foxpilot youtube - YouTube search, video metadata, transcripts, and playlists

Common commands:
  foxpilot youtube search "rust async tutorial"
  foxpilot youtube open "rust async tutorial"
  foxpilot youtube open https://www.youtube.com/watch?v=VIDEO_ID
  foxpilot youtube metadata
  foxpilot youtube transcript

Useful options:
  --json                     Return structured JSON where supported
  --limit N                  Limit result count for list commands
  --format text|segments|srt|json

Auth:
  Public YouTube pages often work without login. For logged-in YouTube, run:
    foxpilot login https://youtube.com
    foxpilot import-cookies --domain youtube.com --include-storage

Modes:
  default claude: recommended dedicated profile
  --zen: use your real Zen browser
  --headless-mode: best effort only; YouTube may show consent or bot checks

Run:
  foxpilot youtube <command> --help"""
    )


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="YouTube search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum videos to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Search YouTube and return visible video results."""
    with _site_browser() as driver:
        driver.get(youtube_search_url(query))
        time.sleep(1.5)
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument(..., help="YouTube URL, video id, or search query."),
    kind: str = typer.Option(
        "",
        "--kind",
        help="Optional hint: video, channel, playlist, or search.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Open a YouTube URL or search query."""
    with _site_browser() as driver:
        if kind == "video" and not _looks_like_url(target):
            driver.get(youtube_search_url(target))
            time.sleep(1.5)
            results = extract_search_results(driver, limit=1)
            if not results:
                _exit_error("no YouTube video result found", url=driver.current_url)
            driver.get(results[0]["url"])
        elif kind == "search":
            driver.get(youtube_search_url(target))
        else:
            driver.get(normalize_youtube_url(target))

        time.sleep(1.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "type": _infer_page_type(driver.current_url),
        }
        _emit(data, json_output, _format_open_result)


@app.command(name="metadata")
def cmd_metadata(
    target_url: Optional[str] = typer.Argument(
        None,
        help="Optional YouTube URL or video id. Omit to inspect current page.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract metadata from a YouTube video page."""
    with _site_browser() as driver:
        if target_url:
            driver.get(normalize_youtube_url(target_url))
            time.sleep(1.0)
        data = extract_video_metadata(driver)
        _emit(data, json_output, format_metadata)


@app.command(name="transcript")
def cmd_transcript(
    target_url: Optional[str] = typer.Argument(
        None,
        help="Optional YouTube URL or video id. Omit to inspect current page.",
    ),
    lang: Optional[str] = typer.Option(None, "--lang", help="Preferred caption language code."),
    output_format: str = typer.Option(
        "text",
        "--format",
        help="Output format: text, segments, srt, or json.",
    ),
):
    """Extract a YouTube transcript from the current or provided video."""
    if output_format not in {"text", "segments", "srt", "json"}:
        _exit_error("unknown transcript format", reason="expected text, segments, srt, or json")

    with _site_browser() as driver:
        if target_url:
            driver.get(normalize_youtube_url(target_url))
            time.sleep(1.0)
        try:
            data = extract_transcript(driver, lang=lang)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="try --visible or verify the video has captions")
        typer.echo(format_transcript(data, output_format=output_format))


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def _format_open_result(data: dict) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"type: {data.get('type', '')}",
        ]
    )


def _infer_page_type(url: str) -> str:
    if "watch?v=" in url:
        return "video"
    if "/shorts/" in url:
        return "short"
    if "playlist?list=" in url:
        return "playlist"
    if "/results?" in url:
        return "search"
    if "/@" in url or "/channel/" in url:
        return "channel"
    return "youtube"


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("www.")


def _exit_error(
    message: str,
    *,
    url: str = "",
    reason: str = "",
    next_step: str = "",
) -> None:
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if reason:
        typer.echo(f"reason: {reason}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)

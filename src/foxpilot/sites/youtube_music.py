"""Typer command branch for YouTube Music workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.youtube_music_service import (
    SECTIONS,
    YT_MUSIC_HOME,
    extract_now_playing,
    extract_playlist_tracks,
    extract_playlists,
    extract_search_results,
    format_now_playing,
    format_open_result,
    format_playlist_tracks,
    format_playlists,
    format_search_results,
    normalize_kind,
    normalize_play_target,
    section_url,
    youtube_music_search_url,
)


app = typer.Typer(
    help="YouTube Music search, playback, and playlist helpers.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    """Set the browser factory used by this branch."""
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help() -> None:
    """Show YouTube Music branch help and examples."""
    typer.echo(
        """foxpilot youtube-music - YouTube Music search, playback, and playlist helpers

Common commands:
  foxpilot youtube-music open                       # open YT Music home
  foxpilot youtube-music open library
  foxpilot youtube-music search "deftones"
  foxpilot youtube-music search "deftones" --kind track --limit 5
  foxpilot youtube-music play "deftones change"
  foxpilot youtube-music play https://music.youtube.com/watch?v=VIDEO_ID
  foxpilot youtube-music pause
  foxpilot youtube-music resume
  foxpilot youtube-music next
  foxpilot youtube-music previous
  foxpilot youtube-music now-playing --json
  foxpilot youtube-music playlists --json
  foxpilot youtube-music playlist "Daily mix 1"
  foxpilot youtube-music add-to-playlist "Daily mix 1" "deftones change" --yes

Sections (open):
  home, explore, library, playlists

Auth:
  Default mode is the dedicated automation profile:
    foxpilot login https://music.youtube.com
  Or import cookies from your main browser:
    foxpilot import-cookies --domain youtube.com --include-storage

Modes:
  default claude (recommended), --visible, --zen

Run:
  foxpilot youtube-music <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None, help=f"Section: {', '.join(SECTIONS)}. Omit for home."
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open YouTube Music home or a named section."""
    try:
        url = section_url(section) if section else YT_MUSIC_HOME
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": section or "home",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    kind: str = typer.Option(
        "", "--kind",
        help="Filter result kind: track, artist, album, playlist.",
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search YouTube Music and return visible results."""
    try:
        kind_norm = normalize_kind(kind) if kind else ""
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(youtube_music_search_url(query, kind=kind_norm))
        time.sleep(1.5)
        results = extract_search_results(driver, limit=limit, kind=kind_norm)
        _emit(results, json_output, format_search_results)


@app.command(name="play")
def cmd_play(
    target: str = typer.Argument(
        ..., help="Track URL, video id, or free-text query (top hit will play)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Start playback for a track URL, id, or top search hit."""
    try:
        url = normalize_play_target(target)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        if "/search?" in driver.current_url:
            results = extract_search_results(driver, limit=1, kind="track")
            if not results:
                _exit_error(
                    "no YouTube Music result found",
                    url=driver.current_url,
                    next_step="try a more specific query or pass a watch URL",
                )
            top = results[0]
            if top.get("url"):
                driver.get(top["url"])
                time.sleep(1.5)
        _click_play_button(driver)
        time.sleep(1.0)
        data = extract_now_playing(driver) or {
            "title": driver.title,
            "url": driver.current_url,
        }
        _emit(data, json_output, format_now_playing)


@app.command(name="pause")
def cmd_pause() -> None:
    """Pause playback."""
    with _site_browser() as driver:
        _press_play_pause(driver)
        typer.echo("paused")


@app.command(name="resume")
def cmd_resume() -> None:
    """Resume playback."""
    with _site_browser() as driver:
        _press_play_pause(driver)
        typer.echo("resumed")


@app.command(name="next")
def cmd_next() -> None:
    """Skip to the next track."""
    with _site_browser() as driver:
        _press_player_button(
            driver,
            ["tp-yt-paper-icon-button.next-button", "[aria-label='Next']", "[title='Next']"],
        )
        typer.echo("next")


@app.command(name="previous")
def cmd_previous() -> None:
    """Return to the previous track."""
    with _site_browser() as driver:
        _press_player_button(
            driver,
            [
                "tp-yt-paper-icon-button.previous-button",
                "[aria-label='Previous']",
                "[title='Previous']",
            ],
        )
        typer.echo("previous")


@app.command(name="now-playing")
def cmd_now_playing(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Report the currently playing track."""
    with _site_browser() as driver:
        data = extract_now_playing(driver)
        if not data:
            _exit_error(
                "no active player bar found",
                url=getattr(driver, "current_url", ""),
                next_step="open music.youtube.com and play a track first",
            )
        _emit(data, json_output, format_now_playing)


@app.command(name="playlists")
def cmd_playlists(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List user playlists from the library page."""
    with _site_browser() as driver:
        driver.get(SECTIONS["playlists"])
        time.sleep(1.5)
        items = extract_playlists(driver)
        _emit(items, json_output, format_playlists)


@app.command(name="playlist")
def cmd_playlist(
    name: str = typer.Argument(..., help="Playlist name (or URL)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a playlist and list its tracks."""
    with _site_browser() as driver:
        if name.startswith("http"):
            driver.get(name)
        else:
            driver.get(SECTIONS["playlists"])
            time.sleep(1.5)
            if not _open_playlist_by_name(driver, name):
                _exit_error(
                    f"playlist not found: {name!r}",
                    url=driver.current_url,
                    next_step="run `foxpilot youtube-music playlists` to list available names",
                )
        time.sleep(1.5)
        data = extract_playlist_tracks(driver, name=name)
        _emit(data, json_output, format_playlist_tracks)


@app.command(name="add-to-playlist")
def cmd_add_to_playlist(
    playlist: str = typer.Argument(..., help="Target playlist name."),
    track: str = typer.Argument(..., help="Track title or watch URL."),
    yes: bool = typer.Option(
        False, "--yes",
        help="Confirm the destructive add (required).",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Add a track to a playlist (requires --yes)."""
    if not yes:
        _exit_error(
            "add-to-playlist requires confirmation",
            reason="this command modifies your library",
            next_step="re-run with --yes to confirm",
        )
    with _site_browser() as driver:
        try:
            url = normalize_play_target(track)
        except ValueError as exc:
            _exit_error(str(exc))
        driver.get(url)
        time.sleep(1.5)
        ok = _add_current_track_to_playlist(driver, playlist)
        if not ok:
            _exit_error(
                f"could not add to playlist: {playlist!r}",
                url=driver.current_url,
                next_step="open the track menu manually with --visible to inspect the menu shape",
            )
        data = {"playlist": playlist, "track": track, "url": driver.current_url}
        _emit(data, json_output, lambda d: f"added {d['track']!r} -> {d['playlist']!r}")


# ---------------------------------------------------------------------------
# Player-button helpers (DOM-fragile, scoped here)
# ---------------------------------------------------------------------------


def _press_play_pause(driver) -> None:
    _press_player_button(
        driver,
        [
            "#play-pause-button",
            "tp-yt-paper-icon-button#play-pause-button",
            "[aria-label='Play']",
            "[aria-label='Pause']",
            "[title='Play']",
            "[title='Pause']",
        ],
    )


def _click_play_button(driver) -> None:
    _press_player_button(
        driver,
        [
            "ytmusic-play-button-renderer",
            "#play-pause-button",
            "[aria-label='Play']",
        ],
    )


def _press_player_button(driver, selectors: list[str]) -> None:
    from selenium.webdriver.common.by import By

    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
        except Exception:
            continue
        try:
            if not el.is_displayed():
                continue
        except Exception:
            continue
        try:
            el.click()
            return
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", el)
                return
            except Exception:
                continue


def _open_playlist_by_name(driver, name: str) -> bool:
    from selenium.webdriver.common.by import By

    needle = name.strip().lower()
    try:
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "ytmusic-two-row-item-renderer, ytmusic-responsive-list-item-renderer",
        )
    except Exception:
        return False
    for row in rows:
        try:
            text = row.text.lower()
        except Exception:
            continue
        if needle in text:
            try:
                link = row.find_element(By.CSS_SELECTOR, "a.yt-simple-endpoint, yt-formatted-string.title")
                link.click()
                return True
            except Exception:
                try:
                    row.click()
                    return True
                except Exception:
                    continue
    return False


def _add_current_track_to_playlist(driver, playlist: str) -> bool:
    from selenium.webdriver.common.by import By

    # Open the song menu in the player bar.
    menu_selectors = [
        "ytmusic-player-bar [aria-label='More actions']",
        "ytmusic-player-bar tp-yt-paper-icon-button[aria-label*='ore']",
    ]
    opened = False
    for sel in menu_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            el.click()
            opened = True
            break
        except Exception:
            continue
    if not opened:
        return False
    time.sleep(0.5)
    # Click "Save to playlist".
    try:
        items = driver.find_elements(By.CSS_SELECTOR, "ytmusic-menu-service-item-renderer")
    except Exception:
        items = []
    for item in items:
        if "save to playlist" in (item.text or "").lower() or "add to playlist" in (item.text or "").lower():
            try:
                item.click()
                break
            except Exception:
                continue
    time.sleep(0.8)
    # Pick the playlist row matching ``playlist`` in the dialog.
    needle = playlist.strip().lower()
    try:
        rows = driver.find_elements(
            By.CSS_SELECTOR,
            "ytmusic-playlist-add-to-option-renderer, tp-yt-paper-dialog yt-formatted-string",
        )
    except Exception:
        rows = []
    for row in rows:
        if needle in (row.text or "").lower():
            try:
                row.click()
                return True
            except Exception:
                continue
    return False


# ---------------------------------------------------------------------------
# Output + error helpers
# ---------------------------------------------------------------------------


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def _exit_error(
    message: str,
    *,
    url: str = "",
    reason: str = "",
    next_step: str = "",
) -> NoReturn:
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if reason:
        typer.echo(f"reason: {reason}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)

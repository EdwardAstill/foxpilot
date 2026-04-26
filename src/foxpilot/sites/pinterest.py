"""Typer command branch for Pinterest (pinterest.com) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.pinterest_service import (
    PINTEREST_HOME,
    board_url,
    click_follow_button,
    click_save_button,
    extract_boards,
    extract_pins,
    extract_profile,
    extract_search_results,
    format_boards,
    format_open_result,
    format_pins,
    format_profile,
    format_search_results,
    is_pinterest_url,
    normalize_pin_target,
    normalize_username,
    polite_jitter,
    profile_url,
    search_url,
    section_url,
    select_board_for_save,
)


app = typer.Typer(
    help="Pinterest navigation, profile, pins, boards, search, and save helpers.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    with _browser_factory() as driver:
        yield driver


@app.command(name="help")
def cmd_help() -> None:
    """Show Pinterest branch help and examples."""
    typer.echo(
        """foxpilot pinterest - Pinterest (pinterest.com) helpers

Common commands:
  foxpilot pinterest open                          # open Pinterest home
  foxpilot pinterest open explore                  # today/following/notifications
  foxpilot pinterest profile <user-or-url>         # dump profile fields
  foxpilot pinterest boards <user-or-url>          # list boards
  foxpilot pinterest pins <user-or-url> --limit 12 # recent pins from profile
  foxpilot pinterest board <user-or-url> <slug>    # pins from a specific board
  foxpilot pinterest search "<query>" --limit 12   # search pins
  foxpilot pinterest save <pin-url-or-id> --yes    # save/repin a pin
  foxpilot pinterest save <pin-url-or-id> --board "Travel" --yes
  foxpilot pinterest follow <user> --yes           # follow a profile

Confirmation gate:
  `save` and `follow` are write actions — they require --yes.

Auth:
  Default mode is --zen so the user's already-signed-in Zen session
  is reused. Pinterest shows a login wall for unauthenticated sessions.

Modes:
  default --zen (recommended), --visible, claude (fragile)

Run:
  foxpilot pinterest <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Optional section: home, today, explore, following, notifications.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Pinterest home or a specific section."""
    if section:
        try:
            url = section_url(section)
        except ValueError as exc:
            _exit_error(str(exc))
    else:
        url = PINTEREST_HOME
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": section or "",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="profile")
def cmd_profile(
    user_or_url: str = typer.Argument(..., help="Pinterest username or profile URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a profile and dump username, name, bio, and counts."""
    try:
        url = profile_url(user_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not is_pinterest_url(driver.current_url):
            _exit_error(
                "redirected away from Pinterest",
                url=driver.current_url,
                next_step="run `foxpilot --zen pinterest open` to verify the session",
            )
        data = extract_profile(driver)
        _emit(data, json_output, format_profile)


@app.command(name="boards")
def cmd_boards(
    user_or_url: str = typer.Argument(..., help="Pinterest username or profile URL."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum boards."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List boards from a profile."""
    try:
        url = profile_url(user_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_boards(driver, limit=limit)
        _emit(results, json_output, format_boards)


@app.command(name="pins")
def cmd_pins(
    user_or_url: str = typer.Argument(..., help="Pinterest username or profile URL."),
    limit: int = typer.Option(12, "--limit", "-n", help="Maximum pins."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent pins from a profile."""
    try:
        url = profile_url(user_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_pins(driver, limit=limit)
        _emit(results, json_output, format_pins)


@app.command(name="board")
def cmd_board(
    user_or_url: str = typer.Argument(..., help="Pinterest username or profile URL."),
    board_slug: str = typer.Argument(..., help="Board slug (the URL path segment after the username)."),
    limit: int = typer.Option(12, "--limit", "-n", help="Maximum pins."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List pins from a specific board."""
    try:
        url = board_url(user_or_url, board_slug)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_pins(driver, limit=limit)
        _emit(results, json_output, format_pins)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(12, "--limit", "-n", help="Maximum pins."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Pinterest pins."""
    try:
        url = search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="save")
def cmd_save(
    target: str = typer.Argument(..., help="Pin numeric id, /pin/<id>/ path, or full pin URL."),
    board: Optional[str] = typer.Option(None, "--board", "-b", help="Board name to save to (optional)."),
    yes: bool = typer.Option(False, "--yes", help="Confirm saving the pin."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Save (repin) a pin to your profile or a specific board (confirmation gated)."""
    if not yes:
        _exit_error(
            "save requires confirmation",
            reason="this performs a real save/repin",
            next_step="re-run with --yes to save",
        )
    try:
        url = normalize_pin_target(target)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not click_save_button(driver):
            _exit_error(
                "could not find the Save button",
                url=driver.current_url,
                next_step="retry with --visible to inspect the pin page",
            )
        if board:
            if not select_board_for_save(driver, board):
                _exit_error(
                    f"could not find board {board!r} in the save dialog",
                    url=driver.current_url,
                    next_step="retry with --visible and verify the board name",
                )
        data = {"target": target, "board": board or "", "url": driver.current_url, "saved": True}
        _emit(data, json_output, lambda d: f"saved pin {d['target']}" + (f" to '{d['board']}'" if d["board"] else ""))


@app.command(name="follow")
def cmd_follow(
    user: str = typer.Argument(..., help="Pinterest username or profile URL."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the follow."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Follow a Pinterest profile (confirmation gated)."""
    if not yes:
        _exit_error(
            "follow requires confirmation",
            reason="this performs a real follow",
            next_step="re-run with --yes to follow",
        )
    try:
        url = profile_url(user)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not click_follow_button(driver):
            _exit_error(
                "could not find the Follow button",
                url=driver.current_url,
                next_step="open the profile manually with --visible and verify Follow is visible",
            )
        data = {"username": normalize_username(user), "url": driver.current_url, "followed": True}
        _emit(data, json_output, lambda d: f"followed {d['username']}")



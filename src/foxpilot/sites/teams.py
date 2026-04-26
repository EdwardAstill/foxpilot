"""Typer command branch for Microsoft Teams web (teams.microsoft.com) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.teams_service import (
    TEAMS_HOME,
    build_teams_url,
    extract_chats,
    extract_messages,
    extract_teams,
    format_chats,
    format_messages,
    format_open_result,
    format_post_result,
    format_teams_list,
    normalize_section,
    normalize_teams_target,
    open_chat,
    open_channel,
    post_message,
    to_json,
)


app = typer.Typer(
    help="Microsoft Teams web navigation and messaging helpers.",
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
    try:
        manager = _browser_factory()
        driver = manager.__enter__()
    except RuntimeError as exc:
        _exit_error(
            f"browser unavailable: {exc}",
            next_step="run `foxpilot doctor`, or retry from a shell that can launch/control the browser",
        )
    try:
        yield driver
    except BaseException as exc:
        suppress = manager.__exit__(type(exc), exc, exc.__traceback__)
        if not suppress:
            raise
    else:
        manager.__exit__(None, None, None)


@app.command(name="help")
def cmd_help() -> None:
    """Show Teams branch help and examples."""
    typer.echo(
        """foxpilot teams - Microsoft Teams web (teams.microsoft.com) helpers

Common commands:
  foxpilot teams open                       # open Teams home (chat)
  foxpilot teams open calendar              # open Teams calendar view
  foxpilot teams chats --json               # list recent chats
  foxpilot teams chat "Alice"               # open a 1:1 / group chat
  foxpilot teams messages --limit 20 --json # recent messages in current chat
  foxpilot teams post "Alice" "hi" --yes    # post into a chat (confirmation gated)
  foxpilot teams teams --json               # list joined teams
  foxpilot teams channel "Project X" "General"

Sections:
  chat, teams, calendar, calls, activity

Auth:
  Default mode --zen reuses your Zen browser's existing M365 session.
  For claude-mode use:
    foxpilot login https://teams.microsoft.com/

Modes:
  default --zen (recommended), --visible, automation profile after login

Run:
  foxpilot teams <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: str = typer.Argument("chat", help="Section name or Teams URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Teams at a section or URL."""
    try:
        url = normalize_teams_target(section)
        normalized = section if "://" in section else normalize_section(section)
    except ValueError as exc:
        _exit_error(str(exc), next_step="run `foxpilot teams help` for known sections")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": normalized,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="chats")
def cmd_chats(
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum chats to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent chats with peer + last-message snippet."""
    with _site_browser() as driver:
        chats = extract_chats(driver, limit=limit)
        _emit(chats, json_output, format_chats)


@app.command(name="chat")
def cmd_chat(
    name: str = typer.Argument(..., help="Visible chat name (1:1 or group)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a chat by visible name."""
    with _site_browser() as driver:
        try:
            data = open_chat(driver, name)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=getattr(driver, "current_url", ""),
                next_step="run `foxpilot teams chats` to see visible chat names",
            )
        data.update({"title": getattr(driver, "title", ""), "section": "chat"})
        _emit(data, json_output, format_open_result)


@app.command(name="messages")
def cmd_messages(
    chat: Optional[str] = typer.Option(None, "--chat", help="Open chat by name first."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum messages to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent messages in the current chat."""
    with _site_browser() as driver:
        if chat:
            try:
                open_chat(driver, chat)
                time.sleep(1.0)
            except RuntimeError as exc:
                _exit_error(str(exc), url=getattr(driver, "current_url", ""))
        messages = extract_messages(driver, limit=limit)
        _emit(messages, json_output, format_messages)


@app.command(name="post")
def cmd_post(
    target: str = typer.Argument(..., help="Chat or channel name to post into."),
    message: str = typer.Argument(..., help="Message body to post."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm the post (required)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Post a message into a chat or channel. Requires --yes."""
    if not yes:
        _exit_error(
            "post requires --yes confirmation",
            reason="post is a write action; pass --yes to confirm",
            next_step=f"foxpilot teams post {target!r} {message!r} --yes",
        )
    with _site_browser() as driver:
        try:
            open_chat(driver, target)
            time.sleep(0.8)
        except RuntimeError as exc:
            _exit_error(str(exc), url=getattr(driver, "current_url", ""))
        try:
            data = post_message(driver, target, message)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=getattr(driver, "current_url", ""),
                next_step="retry with `foxpilot --visible teams post ...` to see the compose box",
            )
        _emit(data, json_output, format_post_result)


@app.command(name="teams")
def cmd_teams(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List joined teams."""
    with _site_browser() as driver:
        teams = extract_teams(driver)
        _emit(teams, json_output, format_teams_list)


@app.command(name="channel")
def cmd_channel(
    team: str = typer.Argument(..., help="Team name."),
    channel: str = typer.Argument(..., help="Channel name."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a channel within a team."""
    with _site_browser() as driver:
        try:
            url = build_teams_url("teams")
            driver.get(url)
            time.sleep(1.5)
            data = open_channel(driver, team, channel)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=getattr(driver, "current_url", ""),
                next_step="run `foxpilot teams teams` to list joined teams",
            )
        data.update({"title": getattr(driver, "title", ""), "section": "teams"})
        _emit(data, json_output, format_open_result)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(to_json(data))
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

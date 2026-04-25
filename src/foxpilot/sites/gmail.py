"""Typer command branch for Gmail (mail.google.com) workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.gmail_service import (
    GMAIL_HOME,
    apply_thread_action,
    build_gmail_search_url,
    click_send,
    extract_message_rows,
    extract_open_message,
    fill_compose,
    format_action_result,
    format_compose_result,
    format_message_detail,
    format_message_list,
    format_open_result,
    is_gmail_url,
    label_url,
    looks_like_thread_id,
    normalize_thread_id,
)


app = typer.Typer(
    help="Gmail navigation, message read/list/search, compose + thread actions.",
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
    """Show Gmail branch help and examples."""
    typer.echo(
        """foxpilot gmail - Gmail (mail.google.com) helpers

Common commands:
  foxpilot gmail open                          # open inbox
  foxpilot gmail open Starred                  # open a label
  foxpilot gmail list --limit 20 --unread      # list inbox messages
  foxpilot gmail search "from:alice has:attachment"
  foxpilot gmail read <thread-id-or-search>    # open + dump current message
  foxpilot gmail compose --to a@b.com --subject Hi --body "..."
  foxpilot gmail send --yes                    # send current draft
  foxpilot gmail star <id>
  foxpilot gmail archive <id>
  foxpilot gmail delete <id> --yes

Confirmation gates:
  send + delete require --yes (or interactive y/N) before acting.
  list / read / open / search / compose / star / archive run unconfirmed.

Auth:
  foxpilot login https://mail.google.com         # one-time
  default mode is the claude profile.

Modes:
  default claude (recommended), --visible, --zen

Run:
  foxpilot gmail <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    label: Optional[str] = typer.Argument(
        None,
        help="Label to open: inbox, starred, important, sent, drafts, trash, or a user label.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the Gmail inbox or a specific label."""
    target = label_url(label) if label else GMAIL_HOME
    with _site_browser() as driver:
        driver.get(target)
        time.sleep(1.5)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "label": (label or "inbox").strip(),
        }
        _emit(data, json_output, format_open_result)


@app.command(name="list")
def cmd_list(
    label: Optional[str] = typer.Option(None, "--label", help="Label to list. Default current view."),
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum messages to return."),
    unread: bool = typer.Option(False, "--unread", help="Only return unread messages."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List messages in the current Gmail view (or a label)."""
    with _site_browser() as driver:
        if label:
            driver.get(label_url(label))
            time.sleep(1.5)
        elif "mail.google.com" not in (driver.current_url or ""):
            driver.get(GMAIL_HOME)
            time.sleep(1.5)
        rows = extract_message_rows(driver, limit=limit, unread_only=unread)
        _emit(rows, json_output, format_message_list)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Gmail search query, e.g. \"from:alice has:attachment\"."),
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum messages to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Run a Gmail search and list results."""
    try:
        url = build_gmail_search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        rows = extract_message_rows(driver, limit=limit)
        _emit(rows, json_output, format_message_list)


@app.command(name="read")
def cmd_read(
    target: str = typer.Argument(..., help="Thread id or a search string that selects one thread."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a thread and dump headers + body."""
    cleaned = normalize_thread_id(target)
    with _site_browser() as driver:
        if looks_like_thread_id(cleaned):
            driver.get(f"https://mail.google.com/mail/u/0/#inbox/{cleaned}")
        else:
            try:
                driver.get(build_gmail_search_url(cleaned))
            except ValueError as exc:
                _exit_error(str(exc))
        time.sleep(1.5)
        try:
            data = extract_open_message(driver)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url)
        _emit(data, json_output, format_message_detail)


@app.command(name="compose")
def cmd_compose(
    to: str = typer.Option(..., "--to", help="Recipient email address."),
    subject: str = typer.Option("", "--subject", help="Subject line."),
    body: str = typer.Option("", "--body", help="Body text."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the compose pane and fill To / Subject / Body."""
    with _site_browser() as driver:
        if "mail.google.com" not in (driver.current_url or ""):
            driver.get(GMAIL_HOME)
            time.sleep(1.5)
        try:
            data = fill_compose(driver, to=to, subject=subject, body=body)
        except RuntimeError as exc:
            _exit_error(str(exc), next_step="open Gmail manually and check the Compose button")
        _emit(data, json_output, format_compose_result)


@app.command(name="send")
def cmd_send(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the interactive confirmation."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send the currently open compose draft. Requires --yes or interactive confirmation."""
    if not yes and not _confirm("send the open draft?"):
        _exit_error("send cancelled", reason="confirmation declined", next_step="re-run with --yes")
    with _site_browser() as driver:
        try:
            data = click_send(driver)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url)
        _emit(data, json_output, format_action_result)


@app.command(name="archive")
def cmd_archive(
    thread_id: str = typer.Argument(..., help="Thread id (or current selection)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Archive a thread (no confirmation gate — reversible)."""
    target = normalize_thread_id(thread_id)
    with _site_browser() as driver:
        _open_thread_if_id(driver, target)
        try:
            data = apply_thread_action(driver, "archive", target)
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, format_action_result)


@app.command(name="star")
def cmd_star(
    thread_id: str = typer.Argument(..., help="Thread id (or current selection)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Star a thread."""
    target = normalize_thread_id(thread_id)
    with _site_browser() as driver:
        _open_thread_if_id(driver, target)
        try:
            data = apply_thread_action(driver, "star", target)
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, format_action_result)


@app.command(name="delete")
def cmd_delete(
    thread_id: str = typer.Argument(..., help="Thread id (or current selection)."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the interactive confirmation."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Delete (move to Trash) a thread. Requires --yes or interactive confirmation."""
    target = normalize_thread_id(thread_id)
    if not yes and not _confirm(f"delete thread {target!r}?"):
        _exit_error("delete cancelled", reason="confirmation declined", next_step="re-run with --yes")
    with _site_browser() as driver:
        _open_thread_if_id(driver, target)
        try:
            data = apply_thread_action(driver, "delete", target)
        except (RuntimeError, ValueError) as exc:
            _exit_error(str(exc))
        _emit(data, json_output, format_action_result)


def _open_thread_if_id(driver, value: str) -> None:
    if looks_like_thread_id(value):
        driver.get(f"https://mail.google.com/mail/u/0/#inbox/{value}")
        time.sleep(1.0)


def _confirm(prompt: str) -> bool:
    try:
        return typer.confirm(prompt, default=False)
    except Exception:
        return False


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


# Quiet unused-import noise for tooling that scans this module.
_ = is_gmail_url

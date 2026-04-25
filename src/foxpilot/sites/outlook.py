"""Typer command branch for Microsoft 365 Outlook on the web."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.outlook_service import (
    OUTLOOK_CALENDAR_HOME,
    OUTLOOK_MAIL_HOME,
    build_calendar_url,
    build_folder_url,
    build_search_url,
    extract_calendar_events,
    extract_messages,
    extract_reading_pane,
    format_calendar,
    format_compose_result,
    format_message_detail,
    format_messages,
    format_open_result,
    format_send_result,
    is_outlook_url,
    normalize_folder,
    normalize_outlook_target,
    parse_recipients,
    to_json,
)


app = typer.Typer(
    help="Microsoft 365 Outlook on the web (mail + calendar) helpers.",
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
            next_step="run `foxpilot doctor`, or retry from a shell that can launch the browser",
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
    """Show Outlook branch help and examples."""
    typer.echo(
        """foxpilot outlook - Microsoft 365 Outlook on the web

Common commands:
  foxpilot outlook open                      # open inbox
  foxpilot outlook open sent
  foxpilot outlook open drafts
  foxpilot outlook list --limit 25 --unread
  foxpilot outlook read "<subject-or-search>"
  foxpilot outlook search "from:advisor"
  foxpilot outlook compose --to a@b.com --subject "hi" --body "..."
  foxpilot outlook send --yes
  foxpilot outlook calendar

Folders:
  inbox, sent, drafts, archive

Auth:
  Sign into outlook.office.com once. UWA M365 users will likely already
  have an existing session in their Zen browser:
    foxpilot --zen outlook open
  For the dedicated claude profile:
    foxpilot login https://outlook.office.com/mail/

Modes:
  default --zen (recommended for UWA M365)
  --visible, claude (after `foxpilot login`)

Run:
  foxpilot outlook <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    folder: str = typer.Argument("inbox", help="Folder name (inbox/sent/drafts/archive) or Outlook URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Outlook on the web at a folder or URL."""
    try:
        if "://" in folder or "." in folder.split("/", 1)[0]:
            url = normalize_outlook_target(folder)
            label = "url"
        else:
            label = normalize_folder(folder)
            url = build_folder_url(folder)
    except ValueError as exc:
        _exit_error(str(exc), next_step="run `foxpilot outlook help` for known folders")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        data = {
            "title": getattr(driver, "title", ""),
            "url": getattr(driver, "current_url", url),
            "folder": label,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="list")
def cmd_list(
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum messages to return."),
    unread: bool = typer.Option(False, "--unread", help="Filter to unread messages only."),
    folder: str = typer.Option("inbox", "--folder", "-f", help="Folder to list."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List messages in the current or specified folder."""
    try:
        url = build_folder_url(folder)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        items = extract_messages(driver, limit=limit)
        if unread:
            items = [item for item in items if item.get("unread")]
        _emit(items, json_output, format_messages)


@app.command(name="read")
def cmd_read(
    target: str = typer.Argument(..., help="Subject or search query to locate the message."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the first matching message and dump body + headers."""
    with _site_browser() as driver:
        try:
            driver.get(build_search_url(target))
        except ValueError as exc:
            _exit_error(str(exc))
        time.sleep(1.5)
        if not _open_first_message(driver):
            _exit_error(
                "no matching Outlook message",
                url=getattr(driver, "current_url", ""),
                next_step="try `foxpilot outlook search ...` to inspect search results",
            )
        time.sleep(1.0)
        data = extract_reading_pane(driver)
        if not data:
            data = {"url": getattr(driver, "current_url", ""), "body": ""}
        _emit(data, json_output, format_message_detail)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Outlook search query."),
    folder: str = typer.Option("inbox", "--folder", "-f", help="Folder scope for the search."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Run an Outlook search and list results."""
    try:
        url = build_search_url(query, folder=folder)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        items = extract_messages(driver, limit=limit)
        _emit(items, json_output, format_messages)


@app.command(name="compose")
def cmd_compose(
    to: str = typer.Option(..., "--to", help="Recipient(s), comma-separated."),
    subject: str = typer.Option("", "--subject", help="Message subject."),
    body: str = typer.Option("", "--body", help="Message body (plain text)."),
    cc: Optional[str] = typer.Option(None, "--cc", help="CC recipient(s)."),
    bcc: Optional[str] = typer.Option(None, "--bcc", help="BCC recipient(s)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the Outlook compose pane and fill the fields. Does NOT send."""
    to_list = parse_recipients(to)
    cc_list = parse_recipients(cc)
    bcc_list = parse_recipients(bcc)
    if not to_list:
        _exit_error("--to must include at least one recipient")

    with _site_browser() as driver:
        driver.get(OUTLOOK_MAIL_HOME)
        time.sleep(1.5)
        try:
            _click_new_mail(driver)
            time.sleep(1.0)
            _fill_compose(driver, to_list, cc_list, bcc_list, subject, body)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=getattr(driver, "current_url", ""),
                next_step="retry with `foxpilot --visible outlook compose ...`",
            )
        data = {
            "status": "drafted",
            "to": to_list,
            "cc": cc_list,
            "bcc": bcc_list,
            "subject": subject,
            "url": getattr(driver, "current_url", ""),
        }
        _emit(data, json_output, format_compose_result)


@app.command(name="send")
def cmd_send(
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm send. REQUIRED before the draft is sent."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send the currently open Outlook compose draft. Requires --yes."""
    if not yes:
        _exit_error(
            "send requires explicit confirmation",
            reason="this is a destructive action",
            next_step="re-run with --yes to actually send the open draft",
        )
    with _site_browser() as driver:
        try:
            _click_send(driver)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=getattr(driver, "current_url", ""),
                next_step="ensure a compose pane is open and the Send button is visible",
            )
        time.sleep(0.8)
        data = {
            "status": "sent",
            "url": getattr(driver, "current_url", ""),
        }
        _emit(data, json_output, format_send_result)


@app.command(name="calendar")
def cmd_calendar(
    view: str = typer.Option("week", "--view", help="Calendar view: day/week/workweek/month."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum events to return."),
    from_date: Optional[str] = typer.Option(None, "--from", help="Range start (informational; URL hint only)."),
    to_date: Optional[str] = typer.Option(None, "--to", help="Range end (informational; URL hint only)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Outlook calendar and list visible events."""
    try:
        url = build_calendar_url(view)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        events = extract_calendar_events(driver, limit=limit)
        if json_output:
            payload = {
                "view": view,
                "from": from_date,
                "to": to_date,
                "url": getattr(driver, "current_url", url),
                "events": events,
            }
            typer.echo(to_json(payload))
        else:
            typer.echo(format_calendar(events))


# --- private helpers --------------------------------------------------------


def _open_first_message(driver) -> bool:
    from selenium.webdriver.common.by import By

    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "div[role='option']")
    except Exception:
        return False
    for row in rows:
        try:
            if not row.is_displayed():
                continue
            row.click()
            return True
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", row)
                return True
            except Exception:
                continue
    return False


def _click_new_mail(driver) -> None:
    from selenium.webdriver.common.by import By

    selectors = [
        "button[aria-label='New mail']",
        "button[aria-label*='New mail' i]",
        "[role='button'][aria-label*='New mail' i]",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            try:
                if element.is_displayed():
                    element.click()
                    return
            except Exception:
                continue
    raise RuntimeError("could not find Outlook 'New mail' button")


def _fill_compose(driver, to_list, cc_list, bcc_list, subject: str, body: str) -> None:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    def _fill(selector_list, values):
        if not values:
            return
        for selector in selector_list:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                try:
                    if not element.is_displayed():
                        continue
                    element.click()
                    for value in values:
                        element.send_keys(value)
                        element.send_keys(Keys.ENTER)
                    return
                except Exception:
                    continue

    _fill(
        [
            "input[aria-label='To']",
            "[aria-label='To'][role='combobox']",
            "div[aria-label='To'] input",
        ],
        to_list,
    )
    _fill(
        [
            "input[aria-label='Cc']",
            "[aria-label='Cc'][role='combobox']",
        ],
        cc_list,
    )
    _fill(
        [
            "input[aria-label='Bcc']",
            "[aria-label='Bcc'][role='combobox']",
        ],
        bcc_list,
    )

    if subject:
        for selector in [
            "input[aria-label='Add a subject']",
            "input[aria-label*='subject' i]",
        ]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                try:
                    if element.is_displayed():
                        element.click()
                        element.send_keys(subject)
                        break
                except Exception:
                    continue

    if body:
        for selector in [
            "div[aria-label='Message body']",
            "[role='textbox'][aria-label*='Message body' i]",
            "div[contenteditable='true'][aria-label*='Message' i]",
        ]:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for element in elements:
                try:
                    if element.is_displayed():
                        element.click()
                        element.send_keys(body)
                        return
                except Exception:
                    continue


def _click_send(driver) -> None:
    from selenium.webdriver.common.by import By

    selectors = [
        "button[aria-label='Send']",
        "button[aria-label*='Send' i]",
        "[role='button'][aria-label='Send']",
    ]
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            try:
                if element.is_displayed():
                    element.click()
                    return
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    return
                except Exception:
                    continue
    raise RuntimeError("could not find Outlook Send button")


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

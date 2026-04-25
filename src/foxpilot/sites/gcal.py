"""Typer command branch for Google Calendar (calendar.google.com) workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.gcal_service import (
    GCAL_HOME,
    VALID_VIEWS,
    date_range_url,
    event_create_url,
    extract_event_detail,
    extract_events,
    format_event_detail,
    format_events,
    format_open_result,
    parse_date,
    parse_when,
    view_url,
)


app = typer.Typer(
    help="Google Calendar navigation and event helpers.",
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
    """Show gcal branch help and examples."""
    typer.echo(
        """foxpilot gcal - Google Calendar (calendar.google.com) helpers

Common commands:
  foxpilot gcal open                       # open default Calendar view
  foxpilot gcal open week                  # open week view
  foxpilot gcal open month                 # open month view
  foxpilot gcal today                      # today's events
  foxpilot gcal events --from today --to +7d
  foxpilot gcal event "Standup"            # open event detail
  foxpilot gcal create --title "Lunch" --when "2026-04-25 12:30" --duration 45 --yes

Useful options:
  --json                Return structured JSON where supported
  --yes                 Confirm destructive create (otherwise dialog stays unsaved)

Auth:
  Default mode is claude. Run once:
    foxpilot login https://calendar.google.com/

Modes:
  default claude (recommended), --visible, --zen

Run:
  foxpilot gcal <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    view: Optional[str] = typer.Argument(
        None,
        help=f"View to open: one of {', '.join(VALID_VIEWS)}. Omit for default.",
    ),
    on: Optional[str] = typer.Option(
        None, "--on", help="Date to land on (YYYY-MM-DD, today, +Nd)."
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Google Calendar at home or a specific view."""
    if view is not None and view not in VALID_VIEWS:
        _exit_error(
            f"unknown view: {view!r}",
            reason=f"expected one of {', '.join(VALID_VIEWS)}",
        )
    target_date: Optional[date] = None
    if on:
        try:
            target_date = parse_date(on)
        except ValueError as exc:
            _exit_error(str(exc))
    if view is None:
        url = GCAL_HOME
    else:
        url = view_url(view, on=target_date)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "view": view or "default",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="today")
def cmd_today(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open today's view and list today's events."""
    today = date.today()
    url = view_url("day", on=today)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.5)
        events = extract_events(driver)
        _emit(events, json_output, format_events)


@app.command(name="events")
def cmd_events(
    from_date: Optional[str] = typer.Option(
        None, "--from", help="Start date (YYYY-MM-DD, today, +Nd). Default: today."
    ),
    to_date: Optional[str] = typer.Option(
        None, "--to", help="End date (YYYY-MM-DD, today, +Nd). Default: +7d."
    ),
    view: str = typer.Option(
        "agenda", "--view", help=f"View to use: one of {', '.join(VALID_VIEWS)}."
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List events between two dates (best effort)."""
    if view not in VALID_VIEWS:
        _exit_error(
            f"unknown view: {view!r}",
            reason=f"expected one of {', '.join(VALID_VIEWS)}",
        )
    try:
        start = parse_date(from_date) if from_date else date.today()
        end = parse_date(to_date) if to_date else start + timedelta(days=7)
    except ValueError as exc:
        _exit_error(str(exc))
    try:
        url = date_range_url(view, start, end)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.8)
        events = extract_events(driver)
        _emit(events, json_output, format_events)


@app.command(name="event")
def cmd_event(
    target: str = typer.Argument(..., help="Event title or id to open."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open an event detail panel and dump it.

    Best-effort: the panel is opened by clicking the first chip whose
    aria-label contains the target text.
    """
    with _site_browser() as driver:
        if not driver.current_url.startswith("https://calendar.google."):
            driver.get(view_url("agenda"))
            time.sleep(1.5)
        try:
            _open_event_chip(driver, target)
        except RuntimeError as exc:
            _exit_error(
                str(exc),
                url=driver.current_url,
                next_step="open the right view first (foxpilot gcal open week) and retry",
            )
        time.sleep(0.8)
        data = extract_event_detail(driver)
        _emit(data, json_output, format_event_detail)


@app.command(name="create")
def cmd_create(
    title: str = typer.Option(..., "--title", help="Event title."),
    when: str = typer.Option(..., "--when", help="Start datetime, e.g. '2026-04-25 12:30'."),
    duration: int = typer.Option(60, "--duration", help="Duration in minutes."),
    invitees: Optional[str] = typer.Option(
        None, "--invitees", help="Comma-separated invitee emails."
    ),
    location: Optional[str] = typer.Option(None, "--location", help="Event location."),
    details: Optional[str] = typer.Option(None, "--details", help="Event description."),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Click Save after the dialog opens. Without --yes, the dialog opens prefilled but stays unsaved.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the create-event dialog with prefilled fields.

    By default this opens the dialog but does not click Save — you can review
    it manually. Pass `--yes` to confirm and click Save.
    """
    try:
        parse_when(when)
    except ValueError as exc:
        _exit_error(str(exc))
    invitee_list: list[str] = []
    if invitees:
        invitee_list = [s.strip() for s in invitees.split(",") if s.strip()]
    url = event_create_url(
        title=title,
        when=when,
        duration_minutes=duration,
        invitees=invitee_list,
        location=location,
        details=details,
    )
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        saved = False
        if yes:
            saved = _click_save_button(driver)
            time.sleep(1.0)
        data = {
            "title": title,
            "when": when,
            "duration_minutes": duration,
            "invitees": invitee_list,
            "location": location or "",
            "details": details or "",
            "url": driver.current_url,
            "saved": saved,
            "confirmed": yes,
        }
        formatter = lambda d: (
            f"opened create dialog for {d['title']!r} at {d['when']}"
            + ("\nsaved: yes" if d["saved"] else ("\nsaved: no (review and run again with --yes)" if not d["confirmed"] else "\nsaved: no (Save button not found)"))
        )
        _emit(data, json_output, formatter)


def _open_event_chip(driver, target: str) -> None:
    """Click the first event chip whose aria-label contains target text."""
    from selenium.webdriver.common.by import By

    needle = (target or "").strip().lower()
    if not needle:
        raise RuntimeError("empty event target")
    selectors = [
        "[data-eventid]",
        "div[role='button'][data-eventchip]",
        "div[role='button'][aria-label]",
    ]
    for selector in selectors:
        try:
            nodes = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for node in nodes:
            try:
                label = (node.get_attribute("aria-label") or node.text or "").lower()
            except Exception:
                continue
            if needle in label:
                try:
                    node.click()
                    return
                except Exception:
                    continue
    raise RuntimeError(f"no event chip matched {target!r}")


def _click_save_button(driver) -> bool:
    """Click the Save button on the create-event dialog. Best effort."""
    from selenium.webdriver.common.by import By

    selectors = [
        "//button[.//span[normalize-space()='Save']]",
        "//button[normalize-space()='Save']",
        "//div[@role='button' and (normalize-space()='Save' or .//span[normalize-space()='Save'])]",
    ]
    for xpath in selectors:
        try:
            el = driver.find_element(By.XPATH, xpath)
        except Exception:
            continue
        try:
            el.click()
            return True
        except Exception:
            continue
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

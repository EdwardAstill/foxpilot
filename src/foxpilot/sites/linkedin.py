"""Typer command branch for LinkedIn (linkedin.com) workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.linkedin_service import (
    LINKEDIN_HOME,
    click_connect_button,
    confirm_send_invitation,
    extract_jobs_results,
    extract_message_threads,
    extract_people_results,
    extract_profile,
    format_jobs_results,
    format_open_result,
    format_people_results,
    format_profile,
    format_threads,
    is_linkedin_url,
    jobs_search_url,
    messaging_thread_url,
    normalize_profile_slug,
    people_search_url,
    polite_jitter,
    profile_url,
    section_url,
    send_message,
)


app = typer.Typer(
    help="LinkedIn navigation, profile, search, and messaging helpers.",
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
    """Show LinkedIn branch help and examples."""
    typer.echo(
        """foxpilot linkedin - LinkedIn (linkedin.com) helpers

Common commands:
  foxpilot linkedin open                          # open LinkedIn home
  foxpilot linkedin open feed                     # feed/mynetwork/messaging/notifications/jobs
  foxpilot linkedin profile <slug-or-url>         # dump profile fields
  foxpilot linkedin search-people "<query>"       # people search
  foxpilot linkedin search-jobs "<query>" --location "Perth"
  foxpilot linkedin messages                      # list recent inbox threads
  foxpilot linkedin connect <slug> --yes          # send connection request
  foxpilot linkedin message <slug-or-thread> "..." --yes

Confirmation gate:
  `connect` and `message` are destructive — they require --yes.

Rate limits:
  LinkedIn rate-limits aggressive scraping. Reads add a 0.5-1.0s jitter
  between paginated batches. Keep --limit modest.

Auth:
  Default mode is --zen so the user's already-signed-in Zen session
  is reused. LinkedIn flags new-device sessions; expect a challenge
  prompt if you sign in fresh in the claude profile.

Modes:
  default --zen (recommended), --visible, claude (fragile)

Run:
  foxpilot linkedin <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Optional section: feed, mynetwork, messaging, notifications, jobs.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open LinkedIn home or a specific section."""
    if section:
        try:
            url = section_url(section)
        except ValueError as exc:
            _exit_error(str(exc))
    else:
        url = LINKEDIN_HOME
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
    slug_or_url: str = typer.Argument(..., help="LinkedIn profile slug or /in/ URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a profile and dump headline, location, current role, skills."""
    try:
        url = profile_url(slug_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not is_linkedin_url(driver.current_url):
            _exit_error(
                "redirected away from LinkedIn",
                url=driver.current_url,
                next_step="run `foxpilot --zen linkedin open feed` and complete any challenge",
            )
        data = extract_profile(driver)
        _emit(data, json_output, format_profile)


@app.command(name="search-people")
def cmd_search_people(
    query: str = typer.Argument(..., help="People search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """People-search results."""
    try:
        url = people_search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_people_results(driver, limit=limit)
        _emit(results, json_output, format_people_results)


@app.command(name="search-jobs")
def cmd_search_jobs(
    query: str = typer.Argument(..., help="Jobs search query."),
    location: Optional[str] = typer.Option(None, "--location", help="Location filter."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Job-search results."""
    try:
        url = jobs_search_url(query, location)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_jobs_results(driver, limit=limit)
        _emit(results, json_output, format_jobs_results)


@app.command(name="connect")
def cmd_connect(
    slug: str = typer.Argument(..., help="LinkedIn profile slug or /in/ URL."),
    note: Optional[str] = typer.Option(None, "--note", help="Optional invitation note."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the connection request."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send a connection request (confirmation gated)."""
    if not yes:
        _exit_error(
            "connect requires confirmation",
            reason="this sends a real connection request",
            next_step="re-run with --yes to send",
        )
    try:
        url = profile_url(slug)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not click_connect_button(driver):
            _exit_error(
                "could not find the Connect button",
                url=driver.current_url,
                next_step="open the profile manually and verify Connect is visible",
            )
        polite_jitter(0.5, 0.5)
        if not confirm_send_invitation(driver, note=note):
            _exit_error(
                "could not click Send on the invitation modal",
                url=driver.current_url,
                next_step="retry with --visible to inspect the modal",
            )
        data = {"slug": normalize_profile_slug(slug), "url": driver.current_url, "sent": True}
        _emit(data, json_output, lambda d: f"sent connection request to {d['slug']}")


@app.command(name="messages")
def cmd_messages(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum threads."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent inbox threads."""
    with _site_browser() as driver:
        driver.get(section_url("messaging"))
        time.sleep(2.0)
        polite_jitter()
        results = extract_message_threads(driver, limit=limit)
        _emit(results, json_output, format_threads)


@app.command(name="message")
def cmd_message(
    target: str = typer.Argument(..., help="Profile slug, /in/ URL, or thread id."),
    text: str = typer.Argument(..., help="Message text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the message."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send a DM to a profile or thread (confirmation gated)."""
    if not yes:
        _exit_error(
            "message requires confirmation",
            reason="this sends a real DM",
            next_step="re-run with --yes to send",
        )
    if not text or not text.strip():
        _exit_error("empty message text")

    looks_like_thread = (
        "://" in target and "/messaging/thread/" in target
    ) or (target.isalnum() and len(target) >= 8 and "/" not in target)

    if looks_like_thread:
        if "://" in target:
            url = target
        else:
            url = messaging_thread_url(target)
    else:
        try:
            url = profile_url(target)
        except ValueError as exc:
            _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not looks_like_thread:
            # On a profile page, click Message to open the composer.
            from foxpilot.sites.linkedin_service import _find_one_xpath  # type: ignore

            btn = _find_one_xpath(driver, [
                "//button[normalize-space()='Message']",
                "//a[normalize-space()='Message']",
            ])
            if btn is None:
                _exit_error(
                    "could not find Message button on profile",
                    url=driver.current_url,
                    next_step="ensure you have permission to message this person",
                )
            try:
                btn.click()
            except Exception:
                _exit_error("could not click Message button", url=driver.current_url)
            polite_jitter(0.5, 0.5)

        if not send_message(driver, text):
            _exit_error(
                "could not send the message",
                url=driver.current_url,
                next_step="retry with --visible and verify the composer is open",
            )
        data = {"target": target, "url": driver.current_url, "sent": True}
        _emit(data, json_output, lambda d: f"sent message to {d['target']}")


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

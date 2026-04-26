"""Typer command branch for X / Twitter (x.com) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.twitter_service import (
    TWITTER_HOME,
    click_follow_button,
    extract_profile,
    extract_tweets,
    format_open_result,
    format_profile,
    format_search_results,
    format_tweets,
    is_twitter_url,
    normalize_username,
    open_dm_thread,
    polite_jitter,
    profile_url,
    search_url,
    section_url,
    send_dm,
    submit_tweet,
    type_tweet,
)


app = typer.Typer(
    help="X / Twitter navigation, profile, search, tweet, follow, and DM helpers.",
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
    """Show X branch help and examples."""
    typer.echo(
        """foxpilot twitter - X / Twitter (x.com) helpers

Common commands:
  foxpilot twitter open                            # open X home
  foxpilot twitter open explore                    # explore/notifications/messages/bookmarks
  foxpilot twitter profile <user-or-url>           # dump profile fields
  foxpilot twitter timeline --limit 10             # home timeline tweets
  foxpilot twitter search "<query>" --limit 10     # search tweets
  foxpilot twitter tweet "Hello world" --yes       # post a tweet
  foxpilot twitter follow <user> --yes             # follow a profile
  foxpilot twitter dm <user> "message" --yes       # send a DM

Confirmation gate:
  `tweet`, `follow`, and `dm` are write actions — they require --yes.

Auth:
  Default mode is --zen so the user's already-signed-in Zen session
  is reused. X is very aggressive about new-device sessions and bots.

Modes:
  default --zen (recommended), --visible, claude (fragile)

Run:
  foxpilot twitter <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Optional section: home, explore, notifications, messages, bookmarks.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open X home or a specific section."""
    if section:
        try:
            url = section_url(section)
        except ValueError as exc:
            _exit_error(str(exc))
    else:
        url = TWITTER_HOME
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
    user_or_url: str = typer.Argument(..., help="X username, @username, or profile URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a profile and dump username, name, bio, and counts."""
    try:
        url = profile_url(user_or_url)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.5)
        if not is_twitter_url(driver.current_url):
            _exit_error(
                "redirected away from X",
                url=driver.current_url,
                next_step="run `foxpilot --zen twitter open` to verify the session",
            )
        data = extract_profile(driver)
        _emit(data, json_output, format_profile)


@app.command(name="timeline")
def cmd_timeline(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum tweets."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Fetch tweets from your home timeline."""
    with _site_browser() as driver:
        driver.get(f"{TWITTER_HOME}home")
        time.sleep(2.5)
        polite_jitter()
        results = extract_tweets(driver, limit=limit)
        _emit(results, json_output, format_tweets)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum tweets."),
    tab: str = typer.Option("Top", "--tab", help="Search tab: Top, Latest, People, Media."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search X and return tweets."""
    try:
        url = search_url(query, tab=tab)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.5)
        polite_jitter()
        results = extract_tweets(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="tweet")
def cmd_tweet(
    text: str = typer.Argument(..., help="Tweet text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm posting."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Post a tweet (confirmation gated)."""
    if not yes:
        _exit_error(
            "tweet requires confirmation",
            reason="this posts a real tweet",
            next_step="re-run with --yes to post",
        )
    if not text or not text.strip():
        _exit_error("empty tweet text")
    with _site_browser() as driver:
        driver.get(f"{TWITTER_HOME}home")
        time.sleep(2.5)
        if not type_tweet(driver, text):
            _exit_error(
                "could not open the tweet compose box",
                url=driver.current_url,
                next_step="retry with --visible and verify you are signed in",
            )
        polite_jitter(0.3, 0.3)
        if not submit_tweet(driver):
            _exit_error(
                "could not find the Post/Tweet submit button",
                url=driver.current_url,
                next_step="retry with --visible to inspect",
            )
        data = {"text": text, "posted": True}
        _emit(data, json_output, lambda d: f"posted: {d['text'][:80]}")


@app.command(name="follow")
def cmd_follow(
    user: str = typer.Argument(..., help="X username, @username, or profile URL."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the follow."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Follow an X profile (confirmation gated)."""
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
        time.sleep(2.5)
        if not click_follow_button(driver):
            _exit_error(
                "could not find the Follow button",
                url=driver.current_url,
                next_step="open the profile manually with --visible and verify Follow is visible",
            )
        data = {"username": normalize_username(user), "url": driver.current_url, "followed": True}
        _emit(data, json_output, lambda d: f"followed @{d['username']}")


@app.command(name="dm")
def cmd_dm(
    user: str = typer.Argument(..., help="X username, @username, or profile URL."),
    text: str = typer.Argument(..., help="Message text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm sending the DM."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Send a DM to an X user (confirmation gated)."""
    if not yes:
        _exit_error(
            "dm requires confirmation",
            reason="this sends a real DM",
            next_step="re-run with --yes to send",
        )
    if not text or not text.strip():
        _exit_error("empty message text")
    try:
        username = normalize_username(user)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        if not open_dm_thread(driver, username):
            _exit_error(
                "could not open DM thread",
                next_step="retry with --visible and verify the session and DM permissions",
            )
        time.sleep(2.0)
        if not send_dm(driver, text):
            _exit_error(
                "could not find the DM composer",
                url=driver.current_url,
                next_step="retry with --visible to inspect",
            )
        data = {"username": username, "url": driver.current_url, "sent": True}
        _emit(data, json_output, lambda d: f"sent DM to @{d['username']}")



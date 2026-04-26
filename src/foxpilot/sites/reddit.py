"""Typer command branch for Reddit (reddit.com) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.reddit_service import (
    REDDIT_HOME,
    extract_post,
    extract_posts,
    format_open_result,
    format_post,
    format_posts,
    format_search_results,
    is_reddit_url,
    normalize_post_target,
    normalize_subreddit,
    polite_jitter,
    post_comment,
    search_url,
    section_url,
    submit_post,
    subreddit_url,
)


app = typer.Typer(
    help="Reddit navigation, subreddits, posts, search, submit, and comment helpers.",
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
    """Show Reddit branch help and examples."""
    typer.echo(
        """foxpilot reddit - Reddit (reddit.com) helpers

Common commands:
  foxpilot reddit open                             # open Reddit home
  foxpilot reddit open popular                     # popular/all
  foxpilot reddit subreddit python --limit 10      # list posts in r/python
  foxpilot reddit subreddit python --sort new      # sorted by new
  foxpilot reddit post <id-or-url>                 # open a post
  foxpilot reddit search "query" --limit 10        # search all Reddit
  foxpilot reddit search "query" --sub python      # search within r/python
  foxpilot reddit submit python "Title" "Body" --yes
  foxpilot reddit comment <post-url> "text" --yes

Confirmation gate:
  `submit` and `comment` are write actions — they require --yes.

Auth:
  Read-only browsing works without auth. Write actions require --zen
  so the signed-in session is available.

Run:
  foxpilot reddit <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: Optional[str] = typer.Argument(
        None,
        help="Optional section: home, popular, all.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Reddit home or a section."""
    if section:
        try:
            url = section_url(section)
        except ValueError as exc:
            _exit_error(str(exc))
    else:
        url = REDDIT_HOME
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": section or "",
        }
        _emit(data, json_output, format_open_result)


@app.command(name="subreddit")
def cmd_subreddit(
    name: str = typer.Argument(..., help="Subreddit name (without leading r/)."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum posts."),
    sort: str = typer.Option("hot", "--sort", help="Sort order: hot, new, top, rising."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List posts in a subreddit."""
    try:
        url = subreddit_url(name, sort=sort)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_posts(driver, limit=limit)
        _emit(results, json_output, format_posts)


@app.command(name="post")
def cmd_post(
    target: str = typer.Argument(..., help="Post id, /comments/<id>/ path, or full URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a post and dump its title, body, and metadata."""
    try:
        url = normalize_post_target(target)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not is_reddit_url(driver.current_url):
            _exit_error(
                "redirected away from Reddit",
                url=driver.current_url,
            )
        data = extract_post(driver)
        _emit(data, json_output, format_post)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    sub: Optional[str] = typer.Option(None, "--sub", help="Restrict search to this subreddit."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum posts."),
    sort: str = typer.Option("relevance", "--sort", help="Sort: relevance, new, top, comments."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Reddit posts."""
    try:
        url = search_url(query, subreddit=sub or "", sort=sort)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        polite_jitter()
        results = extract_posts(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="submit")
def cmd_submit(
    subreddit: str = typer.Argument(..., help="Subreddit name (without leading r/)."),
    title: str = typer.Argument(..., help="Post title."),
    body: str = typer.Argument("", help="Post body text (optional for link posts)."),
    yes: bool = typer.Option(False, "--yes", help="Confirm submitting the post."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Submit a text post to a subreddit (confirmation gated)."""
    if not yes:
        _exit_error(
            "submit requires confirmation",
            reason="this posts a real submission to Reddit",
            next_step="re-run with --yes to submit",
        )
    if not title or not title.strip():
        _exit_error("empty post title")
    try:
        sub = normalize_subreddit(subreddit)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        if not submit_post(driver, sub, title, body):
            _exit_error(
                "could not complete the submission form",
                url=driver.current_url,
                next_step="retry with --visible and verify you are signed in",
            )
        data = {
            "subreddit": sub,
            "title": title,
            "url": driver.current_url,
            "submitted": True,
        }
        _emit(data, json_output, lambda d: f"submitted to r/{d['subreddit']}: {d['title'][:60]}")


@app.command(name="comment")
def cmd_comment(
    target: str = typer.Argument(..., help="Post id, /comments/<id>/ path, or full URL."),
    text: str = typer.Argument(..., help="Comment text."),
    yes: bool = typer.Option(False, "--yes", help="Confirm posting the comment."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Post a comment on a Reddit post (confirmation gated)."""
    if not yes:
        _exit_error(
            "comment requires confirmation",
            reason="this posts a real comment",
            next_step="re-run with --yes to post",
        )
    if not text or not text.strip():
        _exit_error("empty comment text")
    try:
        url = normalize_post_target(target)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if not post_comment(driver, text):
            _exit_error(
                "could not post the comment",
                url=driver.current_url,
                next_step="retry with --visible and verify you are signed in",
            )
        data = {"target": target, "url": driver.current_url, "posted": True}
        _emit(data, json_output, lambda d: f"posted comment on {d['target']}")



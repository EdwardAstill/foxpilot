"""Typer command branch for Wikipedia workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn

import typer

from foxpilot.core import browser
from foxpilot.sites.wikipedia_service import (
    DEFAULT_LANG,
    article_url,
    extract_links,
    extract_references,
    extract_search_results,
    extract_summary,
    format_links,
    format_references,
    format_search_results,
    format_summary,
    random_url,
    search_url,
)


app = typer.Typer(
    help="Wikipedia article lookup, search, summary, and reference helpers.",
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
    """Show Wikipedia branch help and examples."""
    typer.echo(
        """foxpilot wikipedia - Wikipedia search, article lookup, and summary helpers

Common commands:
  foxpilot wikipedia open "Ada Lovelace"
  foxpilot wikipedia search "rust programming language" --json
  foxpilot wikipedia summary "Ada Lovelace"
  foxpilot wikipedia links "Ada Lovelace" --limit 25
  foxpilot wikipedia references "Ada Lovelace"
  foxpilot wikipedia random
  foxpilot wikipedia random --lang fr

Useful options:
  --lang <code>   Language subdomain (default: en). e.g. en, fr, de, ja
  --json          Return structured JSON where supported
  --limit N       Limit result count for list commands

Auth:
  Public site, no login required.

Modes:
  default claude: dedicated profile
  --zen / --visible / --headless-mode: also supported

Run:
  foxpilot wikipedia <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument(..., help="Article title or wikipedia URL."),
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a Wikipedia article by title or URL."""
    try:
        url = article_url(target, lang=lang)
    except ValueError as exc:
        _exit_error(str(exc), reason="empty or invalid title")
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(0.8)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "lang": lang,
        }
        _emit(data, json_output, _format_open_result)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Wikipedia and return matching article titles + snippets."""
    with _site_browser() as driver:
        driver.get(search_url(query, lang=lang))
        time.sleep(1.0)
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="summary")
def cmd_summary(
    target: str = typer.Argument(..., help="Article title or wikipedia URL."),
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Return the lead paragraph + infobox key/values for an article."""
    try:
        url = article_url(target, lang=lang)
    except ValueError as exc:
        _exit_error(str(exc), reason="empty or invalid title")
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(0.8)
        data = extract_summary(driver, lang=lang)
        if not data.get("title"):
            _exit_error(
                "no Wikipedia article found",
                url=driver.current_url,
                next_step="try 'foxpilot wikipedia search' first",
            )
        _emit(data, json_output, format_summary)


@app.command(name="links")
def cmd_links(
    target: str = typer.Argument(..., help="Article title or wikipedia URL."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum links to return."),
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List internal links from a Wikipedia article."""
    try:
        url = article_url(target, lang=lang)
    except ValueError as exc:
        _exit_error(str(exc), reason="empty or invalid title")
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(0.8)
        links = extract_links(driver, limit=limit)
        _emit(links, json_output, format_links)


@app.command(name="references")
def cmd_references(
    target: str = typer.Argument(..., help="Article title or wikipedia URL."),
    limit: int = typer.Option(200, "--limit", "-n", help="Maximum references to return."),
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List entries from the article's reference list."""
    try:
        url = article_url(target, lang=lang)
    except ValueError as exc:
        _exit_error(str(exc), reason="empty or invalid title")
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(0.8)
        refs = extract_references(driver, limit=limit)
        _emit(refs, json_output, format_references)


@app.command(name="random")
def cmd_random(
    lang: str = typer.Option(DEFAULT_LANG, "--lang", help="Language subdomain (default: en)."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a random Wikipedia article."""
    with _site_browser() as driver:
        driver.get(random_url(lang=lang))
        time.sleep(1.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "lang": lang,
        }
        _emit(data, json_output, _format_open_result)


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
            f"lang: {data.get('lang', '')}",
        ]
    )


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

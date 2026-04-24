"""Typer command branch for documentation workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.docs_service import (
    docs_search_url,
    extract_examples,
    extract_links,
    extract_page_read,
    extract_search_results,
    format_examples,
    format_links,
    format_open_result,
    format_page_read,
    format_search_results,
    list_docs_sites,
    normalize_docs_target,
    resolve_docs_site,
    to_json,
)


app = typer.Typer(
    help="Official documentation search, open, read, links, and examples.",
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
def cmd_help(
    json_output: bool = typer.Option(False, "--json", help="Return known site registry as JSON."),
):
    """Show docs branch help, registry, and examples."""
    if json_output:
        typer.echo(to_json(list_docs_sites()))
        return

    typer.echo(
        """foxpilot docs - official documentation search and extraction

Common commands:
  foxpilot docs search "pathlib glob" --site python
  foxpilot docs open "useEffect cleanup" --site react
  foxpilot docs read --full
  foxpilot docs links --json
  foxpilot docs examples --lang python

Known sites:
  python       docs.python.org/3
  mdn          developer.mozilla.org/en-US/docs/Web
  react        react.dev
  typescript   typescriptlang.org/docs
  typer        typer.tiangolo.com
  selenium     selenium.dev/documentation

Modes:
  default claude: recommended persisted profile
  --zen: use your real Zen browser
  --headless-mode: fine for public docs, but search pages may challenge or render differently

Run:
  foxpilot docs <command> --help"""
    )


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Documentation search query."),
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Known site key."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Search official documentation sites."""
    try:
        search_url = docs_search_url(query, site_key=site)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(search_url)
        time.sleep(1.0)
        results = extract_search_results(driver, limit=limit, site_key=site)
        _emit(results, json_output, format_search_results)


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument(..., help="Docs URL, registry-relative path, or search query."),
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Known site key."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Open a docs URL or the first matching docs result for a query."""
    try:
        target_url = normalize_docs_target(target, site_key=site)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(target_url)
        time.sleep(1.0)

        if not _looks_like_url(target) and not target.startswith("/"):
            results = extract_search_results(driver, limit=1, site_key=site)
            if results:
                driver.get(results[0]["url"])
                time.sleep(0.75)

        data = {
            "title": driver.title,
            "url": driver.current_url,
            "site": resolve_docs_site(site).key if site else "",
        }
        if not data["site"]:
            from foxpilot.sites.docs_service import detect_docs_site

            data["site"] = detect_docs_site(driver.current_url)
        _emit(data, json_output, format_open_result)


@app.command(name="read")
def cmd_read(
    selector: Optional[str] = typer.Argument(None, help="CSS selector to scope reading."),
    full: bool = typer.Option(False, "--full", help="No truncation."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Read visible content from the current documentation page."""
    max_chars = 50000 if full else 5000
    with _site_browser() as driver:
        data = extract_page_read(driver, selector=selector, max_chars=max_chars)
        _emit(data, json_output, format_page_read)


@app.command(name="links")
def cmd_links(
    site: Optional[str] = typer.Option(None, "--site", "-s", help="Only include links for a known site."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum links to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """List visible links from the current documentation page."""
    try:
        resolve_docs_site(site)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        links = extract_links(driver, limit=limit, site_key=site)
        _emit(links, json_output, format_links)


@app.command(name="examples")
def cmd_examples(
    lang: Optional[str] = typer.Option(None, "--lang", "-l", help="Filter by code language."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum examples to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract code examples from the current documentation page."""
    with _site_browser() as driver:
        examples = extract_examples(driver, lang=lang, limit=limit)
        _emit(examples, json_output, format_examples)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(to_json(data))
    else:
        typer.echo(formatter(data))


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("www.") or "." in value.split("/", 1)[0]


def _exit_error(message: str, *, next_step: str = "") -> None:
    typer.echo(f"error: {message}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)

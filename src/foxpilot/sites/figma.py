"""Typer command branch for Figma (figma.com) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.figma_service import (
    FIGMA_HOME,
    extract_file_metadata,
    extract_files_list,
    extract_search_results,
    file_url,
    files_url,
    format_file,
    format_files,
    format_open_result,
    format_search_results,
    is_figma_url,
    polite_jitter,
    search_url,
)


app = typer.Typer(
    help="Figma navigation, file listing, and search helpers.",
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
    """Show Figma branch help and examples."""
    typer.echo(
        """foxpilot figma - Figma (figma.com) helpers

Common commands:
  foxpilot figma open                              # open Figma home
  foxpilot figma files --limit 20                 # list recent files
  foxpilot figma file <key-or-url>                # open a specific file
  foxpilot figma search "design system"           # search files

Auth:
  Figma requires authentication. Use --zen to reuse the signed-in
  Zen session. All operations are read-only.

File key:
  The alphanumeric ID in the Figma URL:
  https://www.figma.com/file/<KEY>/Title

Run:
  foxpilot figma <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Figma home."""
    with _site_browser() as driver:
        driver.get(FIGMA_HOME)
        time.sleep(2.0)
        data = {"title": driver.title, "url": driver.current_url}
        _emit(data, json_output, format_open_result)


@app.command(name="files")
def cmd_files(
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum files."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent and shared files from the Figma dashboard."""
    with _site_browser() as driver:
        driver.get(files_url())
        time.sleep(3.0)
        polite_jitter()
        results = extract_files_list(driver, limit=limit)
        _emit(results, json_output, format_files)


@app.command(name="file")
def cmd_file(
    target: str = typer.Argument(..., help="File key (alphanumeric id) or full Figma file URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a Figma file and dump its metadata."""
    try:
        url = file_url(target)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(4.0)
        if not is_figma_url(driver.current_url):
            _exit_error(
                "redirected away from Figma",
                url=driver.current_url,
                next_step="run `foxpilot --zen figma open` to verify the session",
            )
        data = extract_file_metadata(driver)
        _emit(data, json_output, format_file)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum files."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Figma files."""
    try:
        url = search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.5)
        polite_jitter()
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)



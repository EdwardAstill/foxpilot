"""Typer command branch for Google Drive navigation."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

import typer

from foxpilot.core import browser
from foxpilot.sites.drive_service import (
    build_drive_url,
    build_folder_url,
    build_search_url,
    download_item,
    extract_items,
    extract_path,
    format_download_result,
    format_items,
    format_open_result,
    format_path,
    normalize_drive_target,
    normalize_view,
    open_item,
    search_items,
    snapshot_download_dir,
    to_json,
    wait_for_download,
)


app = typer.Typer(
    help="Google Drive navigation helpers for files, folders, search, and downloads.",
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
    """Show Drive branch help and examples."""
    typer.echo(
        """foxpilot drive - Google Drive navigation helpers

Common commands:
  foxpilot drive open
  foxpilot drive open recent
  foxpilot drive open shared
  foxpilot drive files --json
  foxpilot drive files --folder <folder-id>
  foxpilot drive search "budget 2026"
  foxpilot drive download "Budget.xlsx" --dir ~/Downloads
  foxpilot drive wait-download --dir ~/Downloads
  foxpilot drive open-item "Budget.xlsx"
  foxpilot drive path

Views:
  home, recent, starred, shared, trash

Auth:
  Sign in once via the foxpilot automation profile:
    foxpilot login https://drive.google.com
  Or import cookies:
    foxpilot import-cookies --domain google.com --include-storage

Modes:
  default claude (recommended)
  --visible: show the browser window
  --zen: use your real Zen browser session
  --headless-mode: best-effort

Run:
  foxpilot drive <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument("home", help="View name or Drive URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Google Drive at a view or URL."""
    try:
        view = normalize_view(target) if not _looks_like_url(target) else "url"
        url = normalize_drive_target(target)
    except ValueError as exc:
        _exit_error(str(exc), next_step="run `foxpilot drive help` for known views")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "view": view,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="files")
def cmd_files(
    folder: str = typer.Option("", "--folder", "-f", help="Open a folder by id before listing."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List visible files and folders on the current Drive page."""
    with _site_browser() as driver:
        if folder:
            try:
                driver.get(build_folder_url(folder))
            except ValueError as exc:
                _exit_error(str(exc))
            time.sleep(1.0)
        _emit(extract_items(driver, limit=limit), json_output, format_items)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Drive search query."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Google Drive through the web UI and list visible results."""
    try:
        url = build_search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        try:
            driver.get(url)
            time.sleep(1.0)
            items = extract_items(driver, limit=limit)
            if not items:
                items = search_items(driver, query, limit=limit)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="try `foxpilot --visible drive search ...`")
        _emit(items, json_output, format_items)


@app.command(name="download")
def cmd_download(
    name: str = typer.Argument(..., help="Visible file or folder name to download."),
    download_dir: Path = typer.Option(
        Path("~/Downloads"),
        "--dir",
        "-d",
        help="Directory to watch for completed downloads.",
    ),
    timeout: float = typer.Option(60.0, "--timeout", "-t", help="Seconds to wait for a completed download."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Right-click a Drive item, click Download, and wait for the file."""
    directory = _resolve_download_dir(download_dir)
    before = snapshot_download_dir(directory)
    with _site_browser() as driver:
        try:
            download_item(driver, name)
            data = wait_for_download(directory, before=before, timeout=timeout)
        except (RuntimeError, TimeoutError) as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="retry with `foxpilot --visible drive download ...`")
        data.update({"name": name, "url": driver.current_url})
        _emit(data, json_output, format_download_result)


@app.command(name="wait-download")
@app.command(name="wait-for-download")
def cmd_wait_download(
    download_dir: Path = typer.Option(
        Path("~/Downloads"),
        "--dir",
        "-d",
        help="Directory to watch for completed downloads.",
    ),
    timeout: float = typer.Option(60.0, "--timeout", "-t", help="Seconds to wait for a completed download."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Wait for a new completed browser download to appear."""
    directory = _resolve_download_dir(download_dir)
    before = snapshot_download_dir(directory)
    try:
        data = wait_for_download(directory, before=before, timeout=timeout)
    except TimeoutError as exc:
        _exit_error(str(exc))
    _emit(data, json_output, format_download_result)


@app.command(name="open-item")
def cmd_open_item(
    name: str = typer.Argument(..., help="Visible file or folder name to open."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a visible Drive item by name."""
    with _site_browser() as driver:
        try:
            open_item(driver, name)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="run `foxpilot drive files` to inspect visible names")
        data = {"title": driver.title, "url": driver.current_url, "name": name}
        _emit(data, json_output, format_open_result)


@app.command(name="path")
def cmd_path(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Show the current Drive breadcrumb path."""
    with _site_browser() as driver:
        path = extract_path(driver)
        if json_output:
            typer.echo(to_json({"path": path, "url": driver.current_url, "title": driver.title}))
        else:
            typer.echo(format_path(path))


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(to_json(data))
    else:
        typer.echo(formatter(data))


def _resolve_download_dir(path: Path) -> Path:
    return path.expanduser().resolve()


def _looks_like_url(value: str) -> bool:
    return "://" in value or "." in value.split("/", 1)[0]


def _exit_error(
    message: str,
    *,
    url: str = "",
    next_step: str = "",
) -> None:
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)


# Build the URL from a view, used as a tested helper.
build_drive_url = build_drive_url

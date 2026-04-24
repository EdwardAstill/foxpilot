"""Typer command branch for OneDrive Online navigation."""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

import typer

from foxpilot.core import browser
from foxpilot.sites.onedrive_service import (
    build_onedrive_url,
    download_selected,
    extract_items,
    extract_path,
    format_download_result,
    format_items,
    format_open_result,
    format_path,
    format_select_result,
    normalize_account,
    normalize_onedrive_target,
    normalize_view,
    open_item,
    search_items,
    select_item,
    snapshot_download_dir,
    to_json,
    wait_for_download,
)


app = typer.Typer(
    help="OneDrive Online navigation helpers for files, folders, search, and paths.",
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
    """Show OneDrive branch help and examples."""
    typer.echo(
        """foxpilot onedrive - OneDrive Online navigation helpers

Common commands:
  foxpilot onedrive open
  foxpilot onedrive open recent
  foxpilot onedrive open shared --account work
  foxpilot onedrive files --json
  foxpilot onedrive search "budget 2026"
  foxpilot onedrive select "Budget.xlsx"
  foxpilot onedrive download "Budget.xlsx" --dir ~/Downloads
  foxpilot onedrive download-selected --dir ~/Downloads
  foxpilot onedrive wait-download --dir ~/Downloads
  foxpilot onedrive open-item "Budget.xlsx"
  foxpilot onedrive path

Views:
  home, files, recent, shared, photos, recycle

Accounts:
  personal    Uses https://onedrive.live.com/
  work        Uses https://www.microsoft365.com/onedrive

Auth:
  OneDrive almost always needs a signed-in Microsoft account:
    foxpilot login https://onedrive.live.com
    foxpilot import-cookies --domain live.com --include-storage
    foxpilot import-cookies --domain microsoft365.com --include-storage

Modes:
  default claude: recommended dedicated profile
  --zen: use your real Zen browser for an existing Microsoft login
  --headless-mode: usually not useful for OneDrive

Run:
  foxpilot onedrive <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument("home", help="View name or OneDrive URL."),
    account: str = typer.Option("personal", "--account", "-a", help="Account type: personal or work."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open OneDrive Online at a view or URL."""
    try:
        normalized_account = normalize_account(account)
        view = normalize_view(target) if not _looks_like_url(target) else "url"
        url = normalize_onedrive_target(target, account=normalized_account)
    except ValueError as exc:
        _exit_error(str(exc), next_step="run `foxpilot onedrive help` for known views")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.0)
        if normalized_account == "work" and view not in {"home", "url"}:
            _click_nav_label(driver, view)
            time.sleep(0.5)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "view": view,
            "account": normalized_account,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="files")
def cmd_files(
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List visible files and folders on the current OneDrive page."""
    with _site_browser() as driver:
        _emit(extract_items(driver, limit=limit), json_output, format_items)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="OneDrive search query."),
    account: str = typer.Option("personal", "--account", "-a", help="Account type: personal or work."),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum items to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search OneDrive through the web UI and list visible results."""
    try:
        url = build_onedrive_url("home", account=account)
    except ValueError as exc:
        _exit_error(str(exc))

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.0)
        try:
            items = search_items(driver, query, limit=limit)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="try `foxpilot --visible onedrive search ...`")
        _emit(items, json_output, format_items)


@app.command(name="open-item")
def cmd_open_item(
    name: str = typer.Argument(..., help="Visible file or folder name to open."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a visible OneDrive item by name."""
    with _site_browser() as driver:
        try:
            open_item(driver, name)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="run `foxpilot onedrive files` to inspect visible names")
        data = {"title": driver.title, "url": driver.current_url, "name": name}
        _emit(data, json_output, format_open_result)


@app.command(name="select")
def cmd_select(
    name: str = typer.Argument(..., help="Visible file or folder name to select."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Select a visible OneDrive item without opening it."""
    with _site_browser() as driver:
        try:
            data = select_item(driver, name)
        except RuntimeError as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="run `foxpilot onedrive files` to inspect visible names")
        _emit(data, json_output, format_select_result)


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
    """Select a visible OneDrive item, click Download, and wait for the file."""
    directory = _resolve_download_dir(download_dir)
    before = snapshot_download_dir(directory)
    with _site_browser() as driver:
        try:
            selection = select_item(driver, name)
            download_selected(driver)
            data = wait_for_download(directory, before=before, timeout=timeout)
        except (RuntimeError, TimeoutError) as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="retry with `foxpilot --visible onedrive download ...`")
        data.update({"name": name, "selection": selection, "url": driver.current_url})
        _emit(data, json_output, format_download_result)


@app.command(name="download-selected")
def cmd_download_selected(
    download_dir: Path = typer.Option(
        Path("~/Downloads"),
        "--dir",
        "-d",
        help="Directory to watch for completed downloads.",
    ),
    timeout: float = typer.Option(60.0, "--timeout", "-t", help="Seconds to wait for a completed download."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Click Download for the current OneDrive selection and wait for the file."""
    directory = _resolve_download_dir(download_dir)
    before = snapshot_download_dir(directory)
    with _site_browser() as driver:
        try:
            download_selected(driver)
            data = wait_for_download(directory, before=before, timeout=timeout)
        except (RuntimeError, TimeoutError) as exc:
            _exit_error(str(exc), url=driver.current_url, next_step="select an item first or retry visibly")
        data.update({"url": driver.current_url})
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


@app.command(name="path")
def cmd_path(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Show the current OneDrive breadcrumb path."""
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


def _click_nav_label(driver, view: str) -> None:
    labels = {
        "files": ["My files", "Files"],
        "recent": ["Recent"],
        "shared": ["Shared"],
        "photos": ["Photos"],
        "recycle": ["Recycle bin", "Deleted files"],
    }.get(view, [])
    if not labels:
        return
    from selenium.webdriver.common.by import By

    for label in labels:
        literal = _xpath_literal(label)
        xpaths = [
            f"//*[self::a or self::button][contains(normalize-space(.), {literal})]",
            f"//*[contains(@aria-label, {literal})]",
        ]
        for xpath in xpaths:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
            except Exception:
                continue
            for element in elements:
                try:
                    if element.is_displayed():
                        element.click()
                        return
                except Exception:
                    continue


def _looks_like_url(value: str) -> bool:
    return "://" in value or "." in value.split("/", 1)[0]


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"


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

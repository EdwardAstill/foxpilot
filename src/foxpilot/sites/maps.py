"""Typer command branch for Google Maps (google.com/maps) workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable

import typer

from foxpilot.core import browser
from foxpilot.sites._cli import emit as _emit, exit_error as _exit_error
from foxpilot.sites.maps_service import (
    MAPS_HOME,
    TRAVEL_MODES,
    directions_url,
    extract_directions,
    extract_place,
    extract_search_results,
    format_directions,
    format_open_result,
    format_place,
    format_places,
    polite_jitter,
    search_url,
)


app = typer.Typer(
    help="Google Maps search, place lookup, and directions helpers.",
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
    """Show Maps branch help and examples."""
    typer.echo(
        """foxpilot maps - Google Maps (google.com/maps) helpers

Common commands:
  foxpilot maps open                               # open Google Maps
  foxpilot maps search "coffee shops near me"      # search for places
  foxpilot maps place "Eiffel Tower"               # look up a single place
  foxpilot maps directions "London" "Paris"        # get directions
  foxpilot maps directions "London" "Paris" --mode transit

Travel modes: driving (default), transit, walking, cycling

Auth:
  No login required for basic map/search usage.
  --zen recommended for consistent locale and signed-in Google features.

Run:
  foxpilot maps <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Google Maps."""
    with _site_browser() as driver:
        driver.get(MAPS_HOME)
        time.sleep(2.0)
        data = {"title": driver.title, "url": driver.current_url}
        _emit(data, json_output, format_open_result)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Search query (place name, category, address)."),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum results."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search for places on Google Maps."""
    try:
        url = search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(3.0)
        polite_jitter()
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_places)


@app.command(name="place")
def cmd_place(
    query: str = typer.Argument(..., help="Place name or address."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Look up details for a single place."""
    try:
        url = search_url(query)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(3.0)
        polite_jitter()
        data = extract_place(driver)
        _emit(data, json_output, format_place)


@app.command(name="directions")
def cmd_directions(
    origin: str = typer.Argument(..., help="Starting point (address, place name, or coordinates)."),
    destination: str = typer.Argument(..., help="Destination (address, place name, or coordinates)."),
    mode: str = typer.Option(
        "driving",
        "--mode", "-m",
        help=f"Travel mode: {', '.join(sorted(TRAVEL_MODES))}.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Get directions between two places."""
    try:
        url = directions_url(origin, destination, mode=mode)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(3.5)
        polite_jitter()
        data = extract_directions(driver)
        data["origin"] = origin
        data["destination"] = destination
        data["mode"] = mode
        _emit(data, json_output, format_directions)



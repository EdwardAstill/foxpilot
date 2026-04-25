"""Typer command branch for Amazon workflows."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from typing import Callable, NoReturn, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.amazon_service import (
    DEFAULT_REGION,
    build_amazon_url,
    build_orders_url,
    build_product_url,
    build_search_url,
    build_track_url,
    extract_cart,
    extract_orders,
    extract_product,
    extract_search_results,
    extract_tracking,
    format_cart,
    format_open_result,
    format_orders,
    format_product,
    format_search_results,
    format_track,
    is_amazon_url,
    normalize_region,
    parse_asin_from_url,
)


app = typer.Typer(
    help="Amazon search, product, orders, cart, and tracking helpers.",
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


def _region_option() -> typer.Option:
    return typer.Option(
        DEFAULT_REGION,
        "--region",
        help="Amazon region: com, com.au, co.uk (default: com.au).",
    )


@app.command(name="help")
def cmd_help() -> None:
    """Show Amazon branch help and examples."""
    typer.echo(
        """foxpilot amazon - Amazon search, product, orders, cart, and tracking

Common commands:
  foxpilot amazon open                              # open Amazon home (com.au)
  foxpilot amazon open orders                       # open order history
  foxpilot amazon open cart                         # open cart
  foxpilot amazon search "usb-c hub" --limit 5      # search results
  foxpilot amazon product B0ABC12345                # product detail by ASIN
  foxpilot amazon product https://amazon.com.au/dp/B0ABC12345
  foxpilot amazon orders --year 2025                # order history (filtered)
  foxpilot amazon track 123-4567890-1234567         # track an order
  foxpilot amazon cart                              # dump cart contents

Region:
  --region com | com.au | co.uk   (default com.au — AU-based user)

Auth:
  Amazon is hostile to new-device sessions; prefer --zen for a real signed-in
  session. Reads (search, product) often work without login.

Modes:
  default --zen (recommended), --visible, claude (after foxpilot login)

Run:
  foxpilot amazon <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    section: str = typer.Argument(
        "home",
        help="home | orders | wishlist | cart, or a full Amazon URL.",
    ),
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open Amazon home or a known section, or navigate to a full URL."""
    try:
        normalized = normalize_region(region)
    except ValueError as exc:
        _exit_error(str(exc))
    if "://" in section or section.startswith("www."):
        if not is_amazon_url(section):
            _exit_error(
                "URL is not on a supported Amazon domain",
                reason=f"got {section!r}",
                next_step="use a www.amazon.com / .com.au / .co.uk URL",
            )
        url = section if "://" in section else f"https://{section}"
        section_label = "url"
    else:
        try:
            url = build_amazon_url(section, normalized)
        except ValueError as exc:
            _exit_error(str(exc))
        section_label = section
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "section": section_label,
            "region": normalized,
        }
        _emit(data, json_output, format_open_result)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="Amazon search query."),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum results."),
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search Amazon and return product cards."""
    try:
        normalized = normalize_region(region)
        url = build_search_url(query, normalized)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.8)
        results = extract_search_results(driver, limit=limit)
        _emit(results, json_output, format_search_results)


@app.command(name="product")
def cmd_product(
    target: str = typer.Argument(..., help="ASIN or product URL."),
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a product page by ASIN or URL and dump details."""
    try:
        normalized = normalize_region(region)
    except ValueError as exc:
        _exit_error(str(exc))
    asin = parse_asin_from_url(target) or target.strip().upper()
    try:
        url = build_product_url(asin, normalized)
    except ValueError as exc:
        _exit_error(
            str(exc),
            reason=f"could not parse ASIN from {target!r}",
            next_step="pass a 10-char ASIN like B0ABC12345 or a /dp/ URL",
        )
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = extract_product(driver)
        _emit(data, json_output, format_product)


@app.command(name="orders")
def cmd_orders(
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum orders."),
    year: Optional[int] = typer.Option(None, "--year", help="Filter to a year (e.g. 2025)."),
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List recent order-history entries."""
    try:
        normalized = normalize_region(region)
    except ValueError as exc:
        _exit_error(str(exc))
    url = build_orders_url(normalized, year=year)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        if "/ap/signin" in driver.current_url:
            _exit_error(
                "Amazon redirected to sign-in",
                url=driver.current_url,
                reason="orders require a logged-in session",
                next_step="rerun with --zen on a signed-in browser, or `foxpilot login https://www.amazon."
                + normalized
                + "/`",
            )
        orders = extract_orders(driver, limit=limit)
        _emit(orders, json_output, format_orders)


@app.command(name="track")
def cmd_track(
    order_id: str = typer.Argument(..., help="Amazon order id."),
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open the track-package page for an order id."""
    try:
        normalized = normalize_region(region)
        url = build_track_url(order_id, normalized)
    except ValueError as exc:
        _exit_error(str(exc))
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = extract_tracking(driver)
        _emit(data, json_output, format_track)


@app.command(name="cart")
def cmd_cart(
    region: str = typer.Option(DEFAULT_REGION, "--region", help="Amazon region."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open and dump the cart contents."""
    try:
        normalized = normalize_region(region)
    except ValueError as exc:
        _exit_error(str(exc))
    url = build_amazon_url("cart", normalized)
    with _site_browser() as driver:
        driver.get(url)
        time.sleep(2.0)
        data = extract_cart(driver)
        _emit(data, json_output, format_cart)


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

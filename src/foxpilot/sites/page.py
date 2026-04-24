"""Typer command branch for generic page inspection."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Callable

import typer

from foxpilot.core import browser
from foxpilot.sites.page_service import (
    LinkFilter,
    extract_buttons,
    extract_forms,
    extract_inputs,
    extract_landmarks,
    extract_links,
    extract_metadata,
    extract_outline,
    format_buttons,
    format_forms,
    format_inputs,
    format_landmarks,
    format_links,
    format_metadata,
    format_outline,
)
from foxpilot.page_brain import understand_page


app = typer.Typer(
    help="Generic page inspection helpers for links, forms, metadata, and accessibility.",
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
def cmd_help():
    """Show generic page branch help and examples."""
    typer.echo(
        """foxpilot page - generic page inspection for agents

Common commands:
  foxpilot page outline
  foxpilot page links --external
  foxpilot page forms
  foxpilot page buttons
  foxpilot page inputs
  foxpilot page metadata --json
  foxpilot page landmarks

Workflow:
  foxpilot go https://example.com
  foxpilot page outline
  foxpilot page links --internal --limit 20
  foxpilot page forms --json

Modes:
  default claude: inspect the dedicated Foxpilot browser profile
  --zen: inspect your real Zen browser session
  --visible: show the claude-mode browser while inspecting
  --headless-mode: best effort for pages that work without persisted state

Run:
  foxpilot page <command> --help"""
    )


@app.command(name="outline")
def cmd_outline(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum headings to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract the visible heading outline from the current page."""
    with _site_browser() as driver:
        _emit(extract_outline(driver, limit=limit), json_output, format_outline)


@app.command(name="links")
def cmd_links(
    internal: bool = typer.Option(False, "--internal", help="Return same-origin links."),
    external: bool = typer.Option(False, "--external", help="Return cross-origin links."),
    all_links: bool = typer.Option(False, "--all", help="Return all visible links."),
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum links to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract visible links from the current page."""
    link_filter = _resolve_link_filter(internal=internal, external=external, all_links=all_links)
    with _site_browser() as driver:
        _emit(
            extract_links(driver, link_filter=link_filter, limit=limit),
            json_output,
            format_links,
        )


@app.command(name="forms")
def cmd_forms(
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum forms to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract forms and their visible controls from the current page."""
    with _site_browser() as driver:
        _emit(extract_forms(driver, limit=limit), json_output, format_forms)


@app.command(name="buttons")
def cmd_buttons(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum buttons to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract visible buttons and button-like controls from the current page."""
    with _site_browser() as driver:
        _emit(extract_buttons(driver, limit=limit), json_output, format_buttons)


@app.command(name="inputs")
def cmd_inputs(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum inputs to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract visible input, select, and textarea controls from the current page."""
    with _site_browser() as driver:
        _emit(extract_inputs(driver, limit=limit), json_output, format_inputs)


@app.command(name="metadata")
def cmd_metadata(
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract title, URL, canonical, social, and meta tags from the current page."""
    with _site_browser() as driver:
        _emit(extract_metadata(driver), json_output, format_metadata)


@app.command(name="landmarks")
def cmd_landmarks(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum landmarks to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Extract accessible page landmarks from the current page."""
    with _site_browser() as driver:
        _emit(extract_landmarks(driver, limit=limit), json_output, format_landmarks)


@app.command(name="understand")
def cmd_understand(
    limit: int = typer.Option(100, "--limit", "-n", help="Maximum DOM items per category."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
):
    """Return an agent-friendly map of the current page."""
    with _site_browser() as driver:
        page = understand_page(driver, limit=limit)
        _emit(page, json_output, _format_understanding)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(formatter(data))


def _resolve_link_filter(
    *,
    internal: bool,
    external: bool,
    all_links: bool,
) -> LinkFilter:
    selected = [internal, external, all_links]
    if sum(1 for value in selected if value) > 1:
        _exit_error("choose only one link filter: --internal, --external, or --all")
    if internal:
        return "internal"
    if external:
        return "external"
    return "all"


def _format_understanding(page: dict) -> str:
    lines = [
        f"title: {page.get('title', '')}",
        f"url: {page.get('url', '')}",
    ]
    for key in ("headings", "forms", "buttons", "inputs", "links", "dangerous_actions", "visible_errors"):
        values = page.get(key) or []
        lines.append(f"{key}: {len(values)}")
        for item in values[:10]:
            if isinstance(item, dict):
                label = item.get("text") or item.get("label") or item.get("href") or item.get("selector") or item
            else:
                label = item
            lines.append(f"  - {label}")
    suggestions = page.get("suggested_next_actions") or []
    if suggestions:
        lines.append("suggested_next_actions:")
        lines.extend(f"  - {item}" for item in suggestions[:10])
    return "\n".join(lines)


def _exit_error(message: str) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(1)

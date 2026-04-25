"""Built-in Wikipedia plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.wikipedia import app
from foxpilot.sites import wikipedia_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="wikipedia",
        help="Wikipedia article lookup, search, summary, and reference helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/wikipedia.md"),
        auth_notes="Public site, no login needed.",
        browser_modes=("claude", "visible", "zen", "headless"),
    )

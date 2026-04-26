"""Built-in Google Maps plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.maps import app
from foxpilot.sites import maps_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="maps",
        help="Google Maps search, place lookup, and directions helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/maps.md"),
        auth_notes=(
            "No login required for basic search and directions. "
            "Use --zen for consistent locale and signed-in Google features "
            "such as saved places."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

"""Built-in Figma plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.figma import app
from foxpilot.sites import figma_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="figma",
        help="Figma navigation, file listing, and search helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/figma.md"),
        auth_notes=(
            "Figma requires authentication for all content. "
            "Recommended mode is --zen so the user's already-signed-in "
            "Zen session is reused. All operations are read-only."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

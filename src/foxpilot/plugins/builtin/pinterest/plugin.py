"""Built-in Pinterest plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.pinterest import app
from foxpilot.sites import pinterest_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="pinterest",
        help="Pinterest navigation, profile, pins, boards, search, and save helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/pinterest.md"),
        auth_notes=(
            "Pinterest requires authentication to browse most content. "
            "Recommended mode is --zen so the user's already-signed-in "
            "Zen session is reused. Unauthenticated sessions will hit a "
            "login wall on most pages."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

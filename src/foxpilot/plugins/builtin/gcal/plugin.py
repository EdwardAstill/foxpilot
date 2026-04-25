"""Built-in Google Calendar plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.gcal import app
from foxpilot.sites import gcal_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="gcal",
        help="Google Calendar navigation, event listing, and event creation helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/gcal.md"),
        auth_notes=(
            "Sign into calendar.google.com once via `foxpilot login https://calendar.google.com/`; "
            "session cookies persist in the claude profile. --zen reuses the user's real Zen session."
        ),
        browser_modes=("claude", "visible", "zen"),
    )

"""Built-in Microsoft Teams plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.teams import app
from foxpilot.sites import teams_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="teams",
        help="Microsoft Teams web navigation and messaging helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/teams.md"),
        auth_notes=(
            "Default mode --zen reuses your Zen browser's existing M365 session "
            "for teams.microsoft.com. For claude profile run "
            "`foxpilot login https://teams.microsoft.com/` once."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

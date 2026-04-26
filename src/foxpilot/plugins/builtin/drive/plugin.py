"""Built-in Google Drive plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.drive import app
from foxpilot.sites import drive_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="drive",
        help="Google Drive navigation, search, and download helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/drive.md"),
        auth_notes=(
            "Sign into drive.google.com once via `foxpilot login https://drive.google.com`; "
            "session cookies persist in the automation profile. Cookie import via "
            "`foxpilot import-cookies --domain google.com --include-storage` also works."
        ),
        browser_modes=("claude", "visible", "zen"),
    )

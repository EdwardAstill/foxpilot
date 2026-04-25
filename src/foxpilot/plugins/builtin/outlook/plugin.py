"""Built-in Outlook on the web plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.outlook import app
from foxpilot.sites import outlook_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="outlook",
        help="Microsoft 365 Outlook on the web (mail + calendar) helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/outlook.md"),
        auth_notes=(
            "Sign into outlook.office.com once. UWA M365 users likely already "
            "have a session in their Zen browser; default mode is --zen. For "
            "the dedicated claude profile run `foxpilot login "
            "https://outlook.office.com/mail/`."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

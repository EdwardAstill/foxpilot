"""Built-in Gmail plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.gmail import app
from foxpilot.sites import gmail_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="gmail",
        help="Gmail navigation, message list/read/search, compose + thread actions.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/gmail.md"),
        auth_notes=(
            "Sign into mail.google.com once via `foxpilot login https://mail.google.com`; "
            "session cookies persist in the automation profile. Use `--zen` to reuse an existing "
            "Zen browser session if you already have Gmail signed-in there."
        ),
        browser_modes=("claude", "visible", "zen"),
    )

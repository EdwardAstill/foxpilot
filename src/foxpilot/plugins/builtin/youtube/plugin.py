"""Built-in YouTube plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.youtube import app
from foxpilot.sites import youtube_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="youtube",
        help="YouTube search, metadata, transcripts, and playlist helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/youtube.md"),
        auth_notes="Public pages often work without login; import youtube.com cookies for logged-in state.",
        browser_modes=("claude", "visible", "zen", "headless"),
    )

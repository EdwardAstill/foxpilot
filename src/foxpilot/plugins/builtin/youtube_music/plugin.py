"""Built-in YouTube Music plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.youtube_music import app
from foxpilot.sites import youtube_music_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="youtube-music",
        help="YouTube Music search, playback, and playlist helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/youtube-music.md"),
        auth_notes=(
            "Sign into music.youtube.com once with `foxpilot login "
            "https://music.youtube.com`. Or import cookies via "
            "`foxpilot import-cookies --domain youtube.com --include-storage`."
        ),
        browser_modes=("claude", "visible", "zen"),
    )

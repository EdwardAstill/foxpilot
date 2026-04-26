"""Built-in X / Twitter plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.twitter import app
from foxpilot.sites import twitter_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="twitter",
        help="X / Twitter navigation, profile, search, tweet, follow, and DM helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/twitter.md"),
        auth_notes=(
            "X (formerly Twitter) is very aggressive about anti-bot detection "
            "and new-device sessions. Recommended mode is --zen so the user's "
            "already-signed-in Zen session is reused. Most content requires "
            "authentication; write actions (tweet, follow, dm) will likely "
            "trigger challenges in a fresh session."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

"""Built-in Reddit plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.reddit import app
from foxpilot.sites import reddit_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="reddit",
        help="Reddit navigation, subreddits, posts, search, submit, and comment helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/reddit.md"),
        auth_notes=(
            "Reddit allows unauthenticated read-only browsing. Write actions "
            "(submit, comment) require a signed-in session. Recommended mode "
            "is --zen for write actions."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

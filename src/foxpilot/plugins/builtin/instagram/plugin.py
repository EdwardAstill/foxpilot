"""Built-in Instagram plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.instagram import app
from foxpilot.sites import instagram_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="instagram",
        help="Instagram navigation, profile, search, posts, and DM helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/instagram.md"),
        auth_notes=(
            "WARNING: Instagram is aggressive about anti-bot and new-device "
            "challenges. Recommended mode is --zen so the user's already-"
            "signed-in Zen session is reused. Signing in fresh in the claude "
            "profile will likely trigger a verification/challenge prompt — "
            "complete it manually with --visible before the plugin can drive "
            "the site."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

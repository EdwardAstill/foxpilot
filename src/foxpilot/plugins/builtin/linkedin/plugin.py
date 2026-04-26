"""Built-in LinkedIn plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.linkedin import app
from foxpilot.sites import linkedin_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="linkedin",
        help="LinkedIn navigation, profile, search, and messaging helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/linkedin.md"),
        auth_notes=(
            "WARNING: LinkedIn is aggressive about new-device challenges. "
            "Recommended mode is --zen so the user's already-signed-in Zen "
            "session is reused. Signing in fresh in the automation profile will "
            "likely trigger a verification/challenge prompt — complete it "
            "manually with --visible before the plugin can drive the site."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

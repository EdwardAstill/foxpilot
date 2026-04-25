"""Built-in UWA Blackboard Ultra plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.lms import app
from foxpilot.sites import lms_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="lms",
        help="UWA Blackboard Ultra (lms.uwa.edu.au) navigation, stream, courses, grades.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/lms.md"),
        auth_notes=(
            "Default mode is --zen (UWA students typically signed into LMS in Zen). "
            "For the claude profile, run `foxpilot login https://lms.uwa.edu.au/ultra/stream` "
            "or `foxpilot import-cookies --domain lms.uwa.edu.au --include-storage`. "
            "Headless is unsupported because UWA Pheme SSO requires a real session."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

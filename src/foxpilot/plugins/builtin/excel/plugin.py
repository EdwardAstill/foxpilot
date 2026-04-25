"""Built-in Excel Online plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.excel import app
from foxpilot.sites import excel_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="excel",
        help="Excel Online navigation and cell read/write helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/excel.md"),
        auth_notes=(
            "Sign into excel.cloud.microsoft once in the foxpilot browser; "
            "session cookies persist in the claude profile."
        ),
        browser_modes=("claude", "visible", "zen"),
    )

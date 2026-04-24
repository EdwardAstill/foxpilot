"""Built-in GitHub plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.github import app
from foxpilot.sites import github_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="github",
        help="GitHub browser helpers for repos, issues, PRs, Actions, files, and search.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/github.md"),
        auth_notes="Public pages often work without login; import github.com cookies for private repos.",
        browser_modes=("claude", "visible", "zen", "headless"),
    )

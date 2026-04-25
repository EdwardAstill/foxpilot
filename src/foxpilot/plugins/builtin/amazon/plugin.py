"""Built-in Amazon plugin registration."""

from __future__ import annotations

from pathlib import Path

from foxpilot.plugins import Plugin, PluginContext
from foxpilot.sites.amazon import app
from foxpilot.sites import amazon_service as service


def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="amazon",
        help="Amazon search, product, orders, cart, and tracking helpers.",
        source=context.source,
        cli_app=app,
        service=service,
        docs_path=Path("docs/commands/amazon.md"),
        auth_notes=(
            "Amazon is hostile to new-device sessions. Prefer --zen on a real "
            "signed-in browser; `foxpilot login https://www.amazon.com.au/` is "
            "supported but may trigger CAPTCHAs and OTP challenges."
        ),
        browser_modes=("zen", "visible", "claude"),
    )

"""Shared command result objects for CLI and MCP adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CommandResult:
    """A browser command outcome with optional page state."""

    ok: bool
    message: str
    title: str = ""
    url: str = ""
    visible_text: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_text(self) -> str:
        prefix = "OK" if self.ok else "x"
        lines = [f"{prefix} {self.message}"]
        if self.url:
            lines.append(f"url: {self.url}")
        if self.title:
            lines.append(f"title: {self.title}")
        if self.visible_text:
            lines.append("visible:")
            lines.extend(f"  {line}" for line in self.visible_text.splitlines())
        return "\n".join(lines)

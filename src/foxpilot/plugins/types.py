from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

PluginSource = Literal["builtin", "local"]


@dataclass(frozen=True)
class PluginContext:
    plugin_dir: Path
    project_root: Path
    source: PluginSource


@dataclass(frozen=True)
class Plugin:
    name: str
    help: str
    source: PluginSource
    cli_app: Any | None = None
    mcp_tools: tuple[Any, ...] = field(default_factory=tuple)
    service: Any | None = None
    docs_path: Path | str | None = None
    auth_notes: str | None = None
    browser_modes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LoadError:
    name: str
    source: PluginSource
    path: Path
    message: str


class PluginRegister(Protocol):
    def __call__(self, context: PluginContext) -> Plugin:
        ...


__all__ = ["LoadError", "Plugin", "PluginContext", "PluginRegister", "PluginSource"]

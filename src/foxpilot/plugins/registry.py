from __future__ import annotations

from dataclasses import replace

from .types import LoadError, Plugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._errors: dict[str, LoadError] = {}

    def add(self, plugin: Plugin) -> None:
        normalized = _normalize_name(plugin.name)
        if plugin.name != normalized:
            plugin = replace(plugin, name=normalized)
        existing = self._plugins.get(normalized)
        if existing is not None and existing.source == "builtin" and plugin.source != "builtin":
            return
        self._plugins[normalized] = plugin
        self._errors.pop(normalized, None)

    def add_error(self, error: LoadError) -> None:
        self._errors[_normalize_name(error.name)] = error

    def list(self) -> list[Plugin]:
        return [self._plugins[name] for name in sorted(self._plugins)]

    def info(self, name: str) -> Plugin | None:
        return self._plugins.get(_normalize_name(name))

    def load_error(self, name: str) -> LoadError | None:
        return self._errors.get(_normalize_name(name))

    def load_errors(self) -> list[LoadError]:
        return [self._errors[name] for name in sorted(self._errors)]


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


__all__ = ["PluginRegistry"]

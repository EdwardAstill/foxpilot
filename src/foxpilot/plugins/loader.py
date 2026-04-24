from __future__ import annotations

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path
from types import ModuleType

from .registry import PluginRegistry
from .types import LoadError, Plugin, PluginContext


def discover_plugins(
    *,
    local_plugin_dirs: list[Path] | tuple[Path, ...] | None = None,
    include_builtins: bool = True,
    project_root: Path | None = None,
) -> PluginRegistry:
    registry = PluginRegistry()
    root = project_root or Path.cwd()

    if include_builtins:
        _discover_builtins(registry, root)

    for plugin_root in local_plugin_dirs or (root / "plugins",):
        _discover_local_dir(registry, Path(plugin_root), root)

    return registry


def _discover_builtins(registry: PluginRegistry, project_root: Path) -> None:
    try:
        builtin_pkg = importlib.import_module("foxpilot.plugins.builtin")
    except Exception as exc:
        registry.add_error(
            LoadError(
                name="builtin",
                source="builtin",
                path=Path(__file__).with_name("builtin"),
                message=str(exc),
            )
        )
        return

    for module_info in pkgutil.iter_modules(builtin_pkg.__path__):
        if not module_info.ispkg:
            continue
        plugin_name = module_info.name
        module_name = f"foxpilot.plugins.builtin.{plugin_name}.plugin"
        try:
            module = importlib.import_module(module_name)
            plugin_dir = Path(module.__file__ or "").parent
            _register_module(registry, module, PluginContext(plugin_dir, project_root, "builtin"))
        except Exception as exc:
            path = _module_path(builtin_pkg, plugin_name)
            registry.add_error(LoadError(plugin_name, "builtin", path, str(exc)))


def _discover_local_dir(registry: PluginRegistry, plugin_root: Path, project_root: Path) -> None:
    if not plugin_root.exists():
        return
    for plugin_dir in sorted(path for path in plugin_root.iterdir() if path.is_dir()):
        module_path = plugin_dir / "plugin.py"
        if not module_path.exists():
            continue
        try:
            module = _load_local_module(module_path)
            context = PluginContext(plugin_dir=plugin_dir, project_root=project_root, source="local")
            _register_module(registry, module, context)
        except Exception as exc:
            registry.add_error(LoadError(plugin_dir.name, "local", plugin_dir, str(exc)))


def _register_module(
    registry: PluginRegistry,
    module: ModuleType,
    context: PluginContext,
) -> None:
    register = getattr(module, "register", None)
    if register is None:
        raise ValueError("plugin.py must define register(context)")
    plugin = register(context)
    if not isinstance(plugin, Plugin):
        raise TypeError("register(context) must return foxpilot.plugins.Plugin")
    if not plugin.name:
        raise ValueError("plugin name must not be empty")
    registry.add(plugin)


def _load_local_module(module_path: Path) -> ModuleType:
    module_name = f"foxpilot_local_plugin_{module_path.parent.name}_{abs(hash(module_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load plugin module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(module_name, None)
    return module


def _module_path(package: ModuleType, plugin_name: str) -> Path:
    package_file = getattr(package, "__file__", None)
    if package_file is None:
        return Path(plugin_name)
    return Path(package_file).parent / plugin_name


__all__ = ["discover_plugins"]

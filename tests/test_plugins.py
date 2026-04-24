import tempfile
import unittest
from pathlib import Path

from foxpilot.plugins import (
    LoadError,
    Plugin,
    PluginContext,
    PluginRegistry,
    discover_plugins,
)


class PluginRegistryTests(unittest.TestCase):
    def test_registry_lists_plugins_and_returns_info(self):
        registry = PluginRegistry()
        plugin = Plugin(
            name="example",
            help="Example workflows.",
            source="builtin",
            docs_path=Path("README.md"),
            auth_notes="No auth required.",
            browser_modes=("visible", "headless"),
        )

        registry.add(plugin)

        self.assertEqual(registry.list(), [plugin])
        self.assertIs(registry.info("example"), plugin)
        self.assertIsNone(registry.load_error("example"))

    def test_builtin_plugin_wins_name_conflicts(self):
        registry = PluginRegistry()
        local = Plugin(name="github", help="Local GitHub.", source="local")
        builtin = Plugin(name="github", help="Built-in GitHub.", source="builtin")

        registry.add(local)
        registry.add(builtin)

        self.assertIs(registry.info("github"), builtin)
        self.assertEqual(registry.list(), [builtin])

    def test_load_errors_are_reported_without_plugins(self):
        registry = PluginRegistry()
        error = LoadError(name="broken", source="local", path=Path("/tmp/broken"), message="boom")

        registry.add_error(error)

        self.assertEqual(registry.list(), [])
        self.assertIs(registry.load_error("broken"), error)


class PluginDiscoveryTests(unittest.TestCase):
    def test_discovers_local_plugin_register_functions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / "plugins" / "hello"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.py").write_text(
                "\n".join(
                    [
                        "from foxpilot.plugins import Plugin",
                        "",
                        "def register(context):",
                        "    return Plugin(",
                        "        name='hello',",
                        "        help=f'Hello from {context.source}',",
                        "        source=context.source,",
                        "        docs_path=context.plugin_dir / 'README.md',",
                        "    )",
                    ]
                ),
                encoding="utf-8",
            )

            registry = discover_plugins(local_plugin_dirs=[root / "plugins"], include_builtins=False)

        plugin = registry.info("hello")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.help, "Hello from local")
        self.assertEqual(plugin.source, "local")

    def test_broken_local_plugin_becomes_load_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plugin_dir = root / "plugins" / "broken"
            plugin_dir.mkdir(parents=True)
            (plugin_dir / "plugin.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

            registry = discover_plugins(local_plugin_dirs=[root / "plugins"], include_builtins=False)

        error = registry.load_error("broken")
        self.assertIsNotNone(error)
        self.assertIn("boom", error.message)
        self.assertEqual(registry.list(), [])

    def test_context_passes_plugin_root_and_project_root(self):
        context = PluginContext(
            plugin_dir=Path("/tmp/plugin"),
            project_root=Path("/tmp/project"),
            source="local",
        )

        self.assertEqual(context.plugin_dir, Path("/tmp/plugin"))
        self.assertEqual(context.project_root, Path("/tmp/project"))
        self.assertEqual(context.source, "local")


if __name__ == "__main__":
    unittest.main()

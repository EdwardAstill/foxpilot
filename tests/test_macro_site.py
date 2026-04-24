import json
import tempfile
import unittest
from pathlib import Path

from typer.testing import CliRunner

from foxpilot.sites import macro
from foxpilot.sites.macro_service import (
    MacroError,
    delete_macro,
    export_macro,
    format_macro,
    list_macros,
    load_macro,
    render_macro_steps,
    run_macro,
)


class MacroServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.macro_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_macro(self, name, data):
        path = self.macro_dir / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_list_macros_reads_json_files_from_configured_directory(self):
        self.write_macro(
            "daily-search",
            {
                "name": "daily-search",
                "description": "Open a daily search.",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test"]}],
            },
        )
        self.write_macro(
            "blank",
            {
                "name": "blank",
                "params": [],
                "steps": [],
            },
        )

        summaries = list_macros(self.macro_dir)

        self.assertEqual([item["name"] for item in summaries], ["blank", "daily-search"])
        self.assertEqual(summaries[1]["description"], "Open a daily search.")
        self.assertEqual(summaries[1]["params"], ["query"])

    def test_load_macro_rejects_path_traversal_names(self):
        with self.assertRaises(MacroError):
            load_macro("../outside", self.macro_dir)

    def test_render_macro_steps_substitutes_named_placeholders(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "params": ["query"],
                "steps": [
                    {
                        "command": "go",
                        "args": ["https://example.test/search?q={{query}}"],
                    },
                    {
                        "command": "fill",
                        "args": ["Search", "{{query}}"],
                        "options": {"submit": True},
                    },
                ],
            },
        )

        macro_def = load_macro("search", self.macro_dir)
        steps = render_macro_steps(macro_def, ["rust async"])

        self.assertEqual(
            steps,
            [
                ["go", "https://example.test/search?q=rust async"],
                ["fill", "Search", "rust async", "--submit"],
            ],
        )

    def test_render_macro_steps_errors_on_missing_parameter(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["{{query}}"]}],
            },
        )

        macro_def = load_macro("search", self.macro_dir)

        with self.assertRaises(MacroError):
            render_macro_steps(macro_def, [])

    def test_run_macro_calls_runner_for_each_rendered_step(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )
        calls = []

        def fake_runner(argv):
            calls.append(list(argv))
            return 0

        result = run_macro("search", ["python"], self.macro_dir, runner=fake_runner)

        self.assertEqual(result["name"], "search")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(calls, [["go", "https://example.test?q=python"]])

    def test_format_macro_includes_description_params_and_steps(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "description": "Search a page.",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )

        output = format_macro(load_macro("search", self.macro_dir))

        self.assertIn("name: search", output)
        self.assertIn("description: Search a page.", output)
        self.assertIn("params: query", output)
        self.assertIn("go https://example.test?q={{query}}", output)

    def test_delete_macro_removes_json_file(self):
        path = self.write_macro(
            "old",
            {
                "name": "old",
                "params": [],
                "steps": [],
            },
        )

        deleted = delete_macro("old", self.macro_dir)

        self.assertTrue(deleted)
        self.assertFalse(path.exists())

    def test_export_macro_outputs_shell_python_mcp_and_markdown(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "description": "Search a page.",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )

        shell = export_macro("search", ["rust async"], self.macro_dir, output_format="shell")
        python = export_macro("search", ["rust async"], self.macro_dir, output_format="python")
        mcp = export_macro("search", ["rust async"], self.macro_dir, output_format="mcp")
        markdown = export_macro("search", ["rust async"], self.macro_dir, output_format="markdown")

        self.assertIn("foxpilot go 'https://example.test?q=rust async'", shell)
        self.assertIn("subprocess.run", python)
        self.assertIn('"tool": "go"', mcp)
        self.assertIn("# Macro: search", markdown)


class MacroTyperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.macro_dir = Path(self.tmp.name)
        self.runner = CliRunner()

    def tearDown(self):
        self.tmp.cleanup()

    def write_macro(self, name, data):
        path = self.macro_dir / f"{name}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_help_and_core_commands_are_registered(self):
        result = self.runner.invoke(macro.app, ["help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("foxpilot macro list", result.stdout)
        self.assertIn("foxpilot macro run search-docs python", result.stdout)

    def test_list_command_outputs_json(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "description": "Search a page.",
                "params": ["query"],
                "steps": [],
            },
        )

        result = self.runner.invoke(
            macro.app,
            ["list", "--dir", str(self.macro_dir), "--json"],
        )

        self.assertEqual(result.exit_code, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data[0]["name"], "search")

    def test_show_command_outputs_macro_details(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "description": "Search a page.",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )

        result = self.runner.invoke(macro.app, ["show", "search", "--dir", str(self.macro_dir)])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("name: search", result.stdout)
        self.assertIn("go https://example.test?q={{query}}", result.stdout)

    def test_run_command_dry_run_prints_rendered_steps(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )

        result = self.runner.invoke(
            macro.app,
            ["run", "search", "python", "--dir", str(self.macro_dir), "--dry-run"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("go https://example.test?q=python", result.stdout)

    def test_delete_command_removes_macro_with_yes_flag(self):
        path = self.write_macro(
            "old",
            {
                "name": "old",
                "params": [],
                "steps": [],
            },
        )

        result = self.runner.invoke(
            macro.app,
            ["delete", "old", "--dir", str(self.macro_dir), "--yes"],
        )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("deleted macro: old", result.stdout)
        self.assertFalse(path.exists())

    def test_export_command_prints_requested_format(self):
        self.write_macro(
            "search",
            {
                "name": "search",
                "params": ["query"],
                "steps": [{"command": "go", "args": ["https://example.test?q={{query}}"]}],
            },
        )

        result = self.runner.invoke(
            macro.app,
            [
                "export",
                "search",
                "python",
                "--dir",
                str(self.macro_dir),
                "--format",
                "markdown",
            ],
        )

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("# Macro: search", result.stdout)
        self.assertIn("foxpilot go https://example.test?q=python", result.stdout)

    def test_record_and_edit_exit_nonzero_as_planned_placeholders(self):
        record = self.runner.invoke(macro.app, ["record", "new-flow"])
        edit = self.runner.invoke(macro.app, ["edit", "new-flow"])

        self.assertNotEqual(record.exit_code, 0)
        self.assertNotEqual(edit.exit_code, 0)
        self.assertIn("planned", record.stderr)
        self.assertIn("planned", edit.stderr)

    def test_command_runner_inherits_global_mode_prefix(self):
        calls = []

        class Completed:
            returncode = 0

        def fake_run(argv, check):
            calls.append((list(argv), check))
            return Completed()

        original_run = macro.subprocess.run
        try:
            macro.set_command_prefix_factory(lambda: ["--zen"])
            macro.subprocess.run = fake_run
            self.assertEqual(macro._run_foxpilot_command(["go", "https://example.test"]), 0)
        finally:
            macro.subprocess.run = original_run
            macro.set_command_prefix_factory(lambda: [])

        self.assertEqual(calls[0][0][-3:], ["--zen", "go", "https://example.test"])
        self.assertFalse(calls[0][1])


if __name__ == "__main__":
    unittest.main()

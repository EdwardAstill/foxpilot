import json
import unittest

from typer.testing import CliRunner

from foxpilot import cli


class PluginCliTests(unittest.TestCase):
    def test_plugins_list_includes_builtin_youtube_and_github(self):
        result = CliRunner().invoke(cli.app, ["plugins", "list", "--json"])

        self.assertEqual(result.exit_code, 0, result.output)
        names = {plugin["name"] for plugin in json.loads(result.output)}
        self.assertIn("youtube", names)
        self.assertIn("github", names)

    def test_plugins_info_reports_builtin_metadata(self):
        result = CliRunner().invoke(cli.app, ["plugins", "info", "youtube"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("name: youtube", result.output)
        self.assertIn("source: builtin", result.output)
        self.assertIn("docs:", result.output)

    def test_plugins_path_prints_roots(self):
        result = CliRunner().invoke(cli.app, ["plugins", "path"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("builtins:", result.output)
        self.assertIn("local:", result.output)


if __name__ == "__main__":
    unittest.main()

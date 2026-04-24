import unittest

from typer.testing import CliRunner

from foxpilot.sites.github import app
from foxpilot.sites.github_service import (
    build_actions_url,
    build_github_explore_url,
    build_file_url,
    build_github_search_url,
    build_issues_url,
    build_pr_url,
    build_prs_url,
    build_repo_url,
    extract_explore_results,
    format_actions_runs,
    format_explore_results,
    format_file_view,
    format_issue_results,
    format_repo_summary,
    parse_repo_slug,
)


class GitHubSiteTests(unittest.TestCase):
    def test_parse_repo_slug_accepts_common_repo_inputs(self):
        self.assertEqual(parse_repo_slug("owner/repo"), "owner/repo")
        self.assertEqual(parse_repo_slug("https://github.com/owner/repo"), "owner/repo")
        self.assertEqual(parse_repo_slug("https://github.com/owner/repo/pull/42"), "owner/repo")
        self.assertEqual(parse_repo_slug("git@github.com:owner/repo.git"), "owner/repo")

    def test_parse_repo_slug_rejects_non_repo_values(self):
        with self.assertRaises(ValueError):
            parse_repo_slug("https://example.com/owner/repo")

        with self.assertRaises(ValueError):
            parse_repo_slug("owner")

    def test_repo_and_file_urls_are_stable(self):
        self.assertEqual(build_repo_url("owner/repo"), "https://github.com/owner/repo")
        self.assertEqual(
            build_file_url("https://github.com/owner/repo", "src/fox pilot.py", branch="feature/a"),
            "https://github.com/owner/repo/blob/feature/a/src/fox%20pilot.py",
        )

    def test_issue_and_pr_urls_apply_state_filters(self):
        self.assertEqual(
            build_issues_url("owner/repo", state="closed"),
            "https://github.com/owner/repo/issues?q=is%3Aissue+is%3Aclosed",
        )
        self.assertEqual(
            build_prs_url("owner/repo", state="merged"),
            "https://github.com/owner/repo/pulls?q=is%3Apr+is%3Amerged",
        )
        self.assertEqual(
            build_prs_url("owner/repo", state="closed"),
            "https://github.com/owner/repo/pulls?q=is%3Apr+is%3Aclosed+-is%3Amerged",
        )

    def test_actions_and_pr_urls_are_stable(self):
        self.assertEqual(
            build_actions_url("owner/repo", branch="main"),
            "https://github.com/owner/repo/actions?query=branch%3Amain",
        )
        self.assertEqual(
            build_pr_url("owner/repo", "42"),
            "https://github.com/owner/repo/pull/42",
        )
        self.assertEqual(
            build_pr_url("owner/repo", "https://github.com/owner/repo/pull/42"),
            "https://github.com/owner/repo/pull/42",
        )

    def test_build_github_search_url_maps_types(self):
        self.assertEqual(
            build_github_search_url("browser automation", search_type="repos"),
            "https://github.com/search?q=browser+automation&type=repositories",
        )
        self.assertEqual(
            build_github_search_url("repo:owner/repo bug", search_type="prs"),
            "https://github.com/search?q=repo%3Aowner%2Frepo+bug&type=pullrequests",
        )

    def test_build_github_explore_url_supports_explore_topics_and_trending(self):
        self.assertEqual(build_github_explore_url(), "https://github.com/explore")
        self.assertEqual(
            build_github_explore_url(topic="Browser Automation"),
            "https://github.com/topics/browser-automation",
        )
        self.assertEqual(
            build_github_explore_url(language="Python", since="weekly"),
            "https://github.com/trending/python?since=weekly",
        )
        self.assertEqual(
            build_github_explore_url(trending=True, since="monthly"),
            "https://github.com/trending?since=monthly",
        )

        with self.assertRaisesRegex(ValueError, "cannot combine"):
            build_github_explore_url(topic="python", language="rust")

        with self.assertRaisesRegex(ValueError, "unknown trending window"):
            build_github_explore_url(trending=True, since="yearly")

    def test_format_repo_summary_is_agent_friendly(self):
        output = format_repo_summary(
            {
                "name": "owner/repo",
                "url": "https://github.com/owner/repo",
                "description": "Example repository",
                "default_branch": "main",
                "stars": "123",
                "forks": "4",
                "open_issues": "5",
            }
        )

        self.assertIn("name: owner/repo", output)
        self.assertIn("description: Example repository", output)
        self.assertIn("default_branch: main", output)

    def test_format_lists_and_file_view_are_stable(self):
        issues = format_issue_results(
            [
                {
                    "number": "12",
                    "title": "Fix labels",
                    "state": "open",
                    "author": "octo",
                    "url": "https://github.com/owner/repo/issues/12",
                }
            ],
            label="issues",
        )
        self.assertIn("[1] #12 Fix labels", issues)
        self.assertIn("state: open", issues)
        self.assertIn("author: octo", issues)

        actions = format_actions_runs(
            [
                {
                    "title": "CI",
                    "status": "passing",
                    "branch": "main",
                    "url": "https://github.com/owner/repo/actions/runs/1",
                }
            ]
        )
        self.assertIn("[1] CI", actions)
        self.assertIn("status: passing", actions)

        file_view = format_file_view(
            {
                "path": "README.md",
                "url": "https://github.com/owner/repo/blob/main/README.md",
                "text": "# Example\nRead me",
            }
        )
        self.assertIn("path: README.md", file_view)
        self.assertIn("# Example", file_view)

    def test_format_explore_results_is_stable(self):
        output = format_explore_results(
            [
                {
                    "name": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "description": "Example project",
                    "language": "Python",
                    "stars": "1.2k",
                    "updated": "Updated today",
                }
            ]
        )

        self.assertIn("[1] owner/repo", output)
        self.assertIn("description: Example project", output)
        self.assertIn("language: Python", output)
        self.assertIn("stars: 1.2k", output)

    def test_extract_explore_results_uses_browser_script(self):
        class FakeDriver:
            def __init__(self):
                self.calls = []

            def execute_script(self, script, limit):
                self.calls.append((script, limit))
                return [
                    {
                        "name": "owner/repo",
                        "url": "https://github.com/owner/repo",
                        "description": "Example project",
                    }
                ]

        driver = FakeDriver()

        result = extract_explore_results(driver, limit=5)

        self.assertEqual(result[0]["name"], "owner/repo")
        self.assertEqual(driver.calls[0][1], 5)

    def test_github_subapp_registers_commands(self):
        result = CliRunner().invoke(app, ["help"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("foxpilot github", result.stdout)
        for command in ("open", "repo", "issues", "prs", "pr", "actions", "file", "search", "explore"):
            self.assertIn(command, result.stdout)

    def test_browser_startup_failure_is_clear_error(self):
        from foxpilot.sites import github

        def broken_browser():
            raise RuntimeError("Marionette port never opened")

        github.set_browser_factory(broken_browser)
        try:
            result = CliRunner().invoke(app, ["repo"])
        finally:
            github.set_browser_factory(github._default_browser)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("browser unavailable: Marionette port never opened", result.output)
        self.assertIn("foxpilot doctor", result.output)
        self.assertNotIn("Traceback", result.output)

    def test_in_page_runtime_error_is_not_mislabeled_as_browser_failure(self):
        from foxpilot.sites import github

        class FakeBrowser:
            current_url = "https://example.com/not-github"

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        github.set_browser_factory(lambda: FakeBrowser())
        try:
            result = CliRunner().invoke(app, ["issues"])
        finally:
            github.set_browser_factory(github._default_browser)

        self.assertEqual(result.exit_code, 1)
        self.assertIn("current page is not inside a GitHub repository", result.output)
        self.assertNotIn("browser unavailable", result.output)


if __name__ == "__main__":
    unittest.main()

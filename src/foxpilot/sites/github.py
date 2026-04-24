"""Typer command branch for GitHub workflows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Optional

import typer

from foxpilot.core import browser
from foxpilot.sites.github_service import (
    build_actions_url,
    build_file_url,
    build_github_explore_url,
    build_github_search_url,
    build_issues_url,
    build_pr_url,
    build_prs_url,
    extract_actions_runs,
    extract_explore_results,
    extract_file_view,
    extract_issue_results,
    extract_pr_summary,
    extract_repo_summary,
    extract_search_results,
    format_actions_runs,
    format_explore_results,
    format_file_view,
    format_issue_results,
    format_repo_summary,
    format_search_results,
    normalize_github_url,
    parse_repo_slug,
    to_json,
)


app = typer.Typer(
    help="GitHub browser helpers for repos, issues, PRs, Actions, files, and search.",
    no_args_is_help=True,
)

BrowserFactory = Callable[[], object]


def _default_browser():
    return browser()


_browser_factory: BrowserFactory = _default_browser


def set_browser_factory(factory: BrowserFactory) -> None:
    """Set the browser factory used by this branch."""
    global _browser_factory
    _browser_factory = factory


@contextmanager
def _site_browser():
    try:
        manager = _browser_factory()
        driver = manager.__enter__()
    except RuntimeError as exc:
        _exit_error(
            f"browser unavailable: {exc}",
            next_step="run `foxpilot doctor`, or retry from a shell that can launch/control the browser",
        )
    try:
        yield driver
    except BaseException as exc:
        suppress = manager.__exit__(type(exc), exc, exc.__traceback__)
        if not suppress:
            raise
    else:
        manager.__exit__(None, None, None)


@app.command(name="help")
def cmd_help() -> None:
    """Show GitHub branch help and examples."""
    typer.echo(
        """foxpilot github - GitHub browser helpers for repos, issues, PRs, Actions, files, and search

Common commands:
  foxpilot github open owner/repo
  foxpilot github repo owner/repo --json
  foxpilot github issues owner/repo --state open --limit 10
  foxpilot github prs owner/repo --state merged --json
  foxpilot github pr 42 --repo owner/repo
  foxpilot github actions owner/repo --branch main
  foxpilot github file owner/repo README.md --branch main
  foxpilot github search "browser automation" --type repos
  foxpilot github explore --topic ai --json
  foxpilot github explore --language python --since weekly

Useful options:
  --json                     Return structured JSON where supported
  --state open|closed|all    Issue state filter
  --state open|closed|merged|all
                             Pull request state filter
  --branch BRANCH            Limit Actions or file view to a branch

Auth:
  Public GitHub pages often work without login. For private repos or logged-in UI state, run:
    foxpilot login https://github.com
    foxpilot import-cookies --domain github.com --include-storage

Modes:
  default claude: recommended dedicated profile
  --zen: use your real Zen browser for existing login state
  --headless-mode: best effort for public pages only

Run:
  foxpilot github <command> --help"""
    )


@app.command(name="open")
def cmd_open(
    target: str = typer.Argument(..., help="GitHub repo slug or URL."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open a GitHub repo slug or URL."""
    try:
        url = normalize_github_url(target)
    except ValueError as exc:
        _exit_error(str(exc), next_step="pass owner/repo or a github.com URL")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.0)
        data = {
            "title": driver.title,
            "url": driver.current_url,
            "repo": _repo_from_url(driver.current_url),
        }
        _emit(data, json_output, _format_open_result)


@app.command(name="repo")
def cmd_repo(
    repo_or_url: Optional[str] = typer.Argument(
        None,
        help="Optional GitHub repo slug or URL. Omit to inspect current page.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Extract a repository summary from GitHub."""
    with _site_browser() as driver:
        if repo_or_url:
            try:
                driver.get(normalize_github_url(repo_or_url))
            except ValueError as exc:
                _exit_error(str(exc), next_step="pass owner/repo or a github.com URL")
            time.sleep(1.0)
        data = extract_repo_summary(driver)
        _emit(data, json_output, format_repo_summary)


@app.command(name="issues")
def cmd_issues(
    repo: Optional[str] = typer.Argument(None, help="GitHub repo slug or URL. Omit to use current repo."),
    state: str = typer.Option("open", "--state", help="Issue state: open, closed, or all."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum issues to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List visible GitHub issues for a repo."""
    with _site_browser() as driver:
        try:
            target_repo = repo or _current_repo(driver)
            driver.get(build_issues_url(target_repo, state=state))
        except ValueError as exc:
            _exit_error(str(exc), url=getattr(driver, "current_url", ""), next_step="pass owner/repo or open a GitHub repo page")
        time.sleep(1.0)
        data = extract_issue_results(driver, limit=limit)
        _emit(data, json_output, lambda rows: format_issue_results(rows, label="issues"))


@app.command(name="prs")
def cmd_prs(
    repo: Optional[str] = typer.Argument(None, help="GitHub repo slug or URL. Omit to use current repo."),
    state: str = typer.Option("open", "--state", help="PR state: open, closed, merged, or all."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum PRs to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List visible GitHub pull requests for a repo."""
    with _site_browser() as driver:
        try:
            target_repo = repo or _current_repo(driver)
            driver.get(build_prs_url(target_repo, state=state))
        except ValueError as exc:
            _exit_error(str(exc), url=getattr(driver, "current_url", ""), next_step="pass owner/repo or open a GitHub repo page")
        time.sleep(1.0)
        data = extract_issue_results(driver, limit=limit)
        _emit(data, json_output, lambda rows: format_issue_results(rows, label="pull requests"))


@app.command(name="pr")
def cmd_pr(
    number_or_url: str = typer.Argument(..., help="PR number or GitHub pull request URL."),
    repo: Optional[str] = typer.Option(None, "--repo", help="Repo slug or URL when passing a PR number."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open and summarize a GitHub pull request."""
    with _site_browser() as driver:
        try:
            target_repo = repo or ("" if _looks_like_url(number_or_url) else _current_repo(driver))
            driver.get(build_pr_url(target_repo, number_or_url))
        except ValueError as exc:
            _exit_error(str(exc), url=getattr(driver, "current_url", ""), next_step="pass a PR URL or use --repo owner/repo with a PR number")
        time.sleep(1.0)
        data = extract_pr_summary(driver)
        _emit(data, json_output, format_repo_summary)


@app.command(name="actions")
def cmd_actions(
    repo: Optional[str] = typer.Argument(None, help="GitHub repo slug or URL. Omit to use current repo."),
    branch: Optional[str] = typer.Option(None, "--branch", help="Filter visible runs by branch."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """List visible GitHub Actions runs for a repo."""
    with _site_browser() as driver:
        try:
            target_repo = repo or _current_repo(driver)
            driver.get(build_actions_url(target_repo, branch=branch))
        except ValueError as exc:
            _exit_error(str(exc), url=getattr(driver, "current_url", ""), next_step="pass owner/repo or open a GitHub repo page")
        time.sleep(1.0)
        data = extract_actions_runs(driver)
        _emit(data, json_output, format_actions_runs)


@app.command(name="file")
def cmd_file(
    repo: str = typer.Argument(..., help="GitHub repo slug or URL."),
    path: str = typer.Argument(..., help="Repository file path."),
    branch: str = typer.Option("main", "--branch", help="Branch or tag name."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Open and read a file from GitHub."""
    with _site_browser() as driver:
        try:
            driver.get(build_file_url(repo, path, branch=branch))
        except ValueError as exc:
            _exit_error(str(exc), next_step="pass owner/repo, a file path, and optionally --branch")
        time.sleep(1.0)
        data = extract_file_view(driver, path=path)
        _emit(data, json_output, format_file_view)


@app.command(name="search")
def cmd_search(
    query: str = typer.Argument(..., help="GitHub search query."),
    search_type: str = typer.Option("repos", "--type", help="Search type: repos, code, issues, prs, or users."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum results to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Search GitHub in the browser."""
    with _site_browser() as driver:
        try:
            driver.get(build_github_search_url(query, search_type=search_type))
        except ValueError as exc:
            _exit_error(str(exc), next_step="use --type repos, code, issues, prs, or users")
        time.sleep(1.0)
        data = extract_search_results(driver, limit=limit)
        _emit(data, json_output, format_search_results)


@app.command(name="explore")
def cmd_explore(
    topic: str = typer.Option("", "--topic", help="GitHub topic to explore, e.g. ai or browser-automation."),
    language: str = typer.Option("", "--language", "-l", help="Trending language, e.g. python or rust."),
    since: str = typer.Option("daily", "--since", help="Trending window: daily, weekly, or monthly."),
    trending: bool = typer.Option(False, "--trending", help="Open GitHub Trending instead of the Explore home page."),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum repositories to return."),
    json_output: bool = typer.Option(False, "--json", help="Return JSON."),
) -> None:
    """Explore GitHub discovery, topics, or trending repositories."""
    try:
        url = build_github_explore_url(topic=topic, language=language, since=since, trending=trending)
    except ValueError as exc:
        _exit_error(str(exc), next_step="use --topic alone, or --trending/--language with --since daily|weekly|monthly")

    with _site_browser() as driver:
        driver.get(url)
        time.sleep(1.0)
        data = extract_explore_results(driver, limit=limit)
        _emit(data, json_output, format_explore_results)


def _emit(data, json_output: bool, formatter) -> None:
    if json_output:
        typer.echo(to_json(data))
    else:
        typer.echo(formatter(data))


def _format_open_result(data: dict[str, str]) -> str:
    return "\n".join(
        [
            f"title: {data.get('title', '')}",
            f"url: {data.get('url', '')}",
            f"repo: {data.get('repo', '')}",
        ]
    )


def _current_repo(driver) -> str:
    repo = _repo_from_url(driver.current_url)
    if not repo:
        raise ValueError("current page is not inside a GitHub repository")
    return repo


def _repo_from_url(url: str) -> str:
    try:
        return parse_repo_slug(url)
    except ValueError:
        return ""


def _looks_like_url(value: str) -> bool:
    return "://" in value or value.startswith("github.com/") or value.startswith("www.github.com/")


def _exit_error(
    message: str,
    *,
    url: str = "",
    reason: str = "",
    next_step: str = "",
) -> None:
    typer.echo(f"error: {message}", err=True)
    if url:
        typer.echo(f"url: {url}", err=True)
    if reason:
        typer.echo(f"reason: {reason}", err=True)
    if next_step:
        typer.echo(f"next: {next_step}", err=True)
    raise typer.Exit(1)

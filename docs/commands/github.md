# `foxpilot github`

GitHub helpers for browser-first agent workflows: open repositories, inspect repo pages, list issues and pull requests, view PRs, check Actions, open files, search GitHub, and explore discovery pages.

This branch does not require the `gh` CLI. It drives GitHub through the same browser modes as the rest of Foxpilot.

## Status

`foxpilot github` is available today as a built-in Typer command branch backed by `src/foxpilot/sites/github.py` and `src/foxpilot/sites/github_service.py`.

The plugin registry now exposes GitHub as a built-in `github` plugin while reusing the existing command branch and service module. Use the commands below as the source of truth for the current CLI.

## Authentication

Public repositories, issues, pull requests, Actions pages, files, and search results often work without login. Private repositories and logged-in UI state require an authenticated browser profile.

Use the dedicated Foxpilot profile when possible:

```bash
foxpilot login https://github.com
foxpilot import-cookies --domain github.com --include-storage
```

Use `--zen` only when the command needs your real browser session.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | yes | best effort |
| `repo` | yes | yes | yes | best effort |
| `issues` | yes | yes | yes | best effort |
| `prs` | yes | yes | yes | best effort |
| `pr` | yes | yes | yes | best effort |
| `actions` | yes | yes | yes | best effort |
| `file` | yes | yes | yes | best effort |
| `search` | yes | yes | yes | best effort |
| `explore` | yes | yes | yes | best effort |

`headless` is best effort because GitHub may render different logged-out pages, hide private data, or require interactive verification.

## Commands

### `help`

Show branch examples, auth notes, and mode guidance.

```bash
foxpilot github help
```

### `open <repo-or-url>`

Open a GitHub repository slug or URL.

```bash
foxpilot github open owner/repo
foxpilot github open https://github.com/owner/repo/pull/42
foxpilot github open owner/repo --json
```

### `repo [repo-or-url]`

Extract a repository summary from the current GitHub page or from a provided repo.

```bash
foxpilot github repo
foxpilot github repo owner/repo
foxpilot github repo https://github.com/owner/repo --json
```

Returned fields include name, URL, title, description, default branch, visibility, stars, forks, watchers, open issues, language, license, and last updated when visible.

### `issues [repo]`

List visible issues for a repository.

```bash
foxpilot github issues owner/repo
foxpilot github issues owner/repo --state closed
foxpilot github issues owner/repo --state all --limit 50 --json
```

State values: `open`, `closed`, `all`.

If `repo` is omitted, Foxpilot uses the repository from the current GitHub page.

### `prs [repo]`

List visible pull requests for a repository.

```bash
foxpilot github prs owner/repo
foxpilot github prs owner/repo --state merged
foxpilot github prs owner/repo --state closed --limit 10 --json
```

State values: `open`, `closed`, `merged`, `all`. The `closed` filter excludes merged PRs.

If `repo` is omitted, Foxpilot uses the repository from the current GitHub page.

### `pr <number-or-url>`

Open and summarize a pull request.

```bash
foxpilot github pr 42 --repo owner/repo
foxpilot github pr https://github.com/owner/repo/pull/42
foxpilot github pr 42 --json
```

When passing a number without `--repo`, the current browser page must already be inside the target GitHub repository.

### `actions [repo]`

List visible GitHub Actions runs for a repository.

```bash
foxpilot github actions owner/repo
foxpilot github actions owner/repo --branch main
foxpilot github actions owner/repo --json
```

If `repo` is omitted, Foxpilot uses the repository from the current GitHub page.

The current command lists visible workflow runs. The plugin roadmap adds more focused failure commands such as `actions failed` and `actions logs`, but those are not available in this command branch unless `foxpilot github --help` shows them in your checkout.

### `file <repo> <path>`

Open and read a file from GitHub.

```bash
foxpilot github file owner/repo README.md
foxpilot github file owner/repo src/foxpilot/cli.py --branch main
foxpilot github file owner/repo pyproject.toml --json
```

The command opens the GitHub file page and extracts visible source or rendered markdown text.

### `search <query>`

Search GitHub in the browser.

```bash
foxpilot github search "browser automation"
foxpilot github search "repo:owner/repo bug" --type issues
foxpilot github search "repo:owner/repo is:pr review" --type prs --json
```

Search types: `repos`, `code`, `issues`, `prs`, `users`.

### `explore`

Open GitHub Explore, Topics, or Trending pages and extract visible repository cards.

```bash
foxpilot github explore
foxpilot github explore --topic ai
foxpilot github explore --topic browser-automation --json
foxpilot github explore --trending --since weekly
foxpilot github explore --language python --since monthly --limit 10
```

Options:

- `--topic TOPIC`: open `github.com/topics/<topic>`. Spaces become hyphens.
- `--trending`: open GitHub Trending.
- `--language LANGUAGE`: open GitHub Trending for a language.
- `--since daily|weekly|monthly`: choose the Trending window.
- `--limit N`: cap extracted repositories.

`--topic` cannot be combined with `--language` or `--trending`.

## JSON Output

Commands with `--json` return stable dictionaries or lists rather than human-readable text.

Repository summary shape:

```json
{
  "name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "title": "GitHub - owner/repo: Example",
  "description": "Example repository",
  "default_branch": "main",
  "visibility": "public",
  "stars": "123",
  "forks": "4",
  "open_issues": "5"
}
```

Issue, PR, Actions, and search list commands return arrays of visible result objects with `title`, `url`, and page-specific fields when available.

Explore returns repository objects with `name`, `url`, `description`, `language`, `stars`, `forks`, `updated`, and `topics` when visible.

Use `--json` for agent handoffs, CI diagnostics, and scripts. Text output is intended for quick human inspection and may be less stable.

## Actions Failure Workflow

Until dedicated `actions failed` and `actions logs` plugin commands exist, use this browser-first workflow:

```bash
foxpilot github actions owner/repo --json
foxpilot github open https://github.com/owner/repo/actions/runs/RUN_ID
foxpilot read
foxpilot find "failed"
foxpilot screenshot /tmp/github-actions-failure.png
```

If the repository is private or logs require authentication, sign in first:

```bash
foxpilot login https://github.com
foxpilot import-cookies --domain github.com --include-storage
```

When the plugin migration adds log-specific commands, the expected shape is:

```bash
foxpilot github actions failed owner/repo --json
foxpilot github actions logs owner/repo RUN_ID --json
```

Those future commands should report the workflow name, run id, status, conclusion, failed jobs, useful log excerpts, and likely cause when it can be inferred from the page.

## Failure Modes

- Private repository or logged-in UI state missing: run `foxpilot login https://github.com` or import cookies.
- Missing access to Actions logs: confirm the account can view the repository in the browser, then retry with the authenticated profile or `--zen`.
- Current-page commands cannot infer a repository: pass `owner/repo` explicitly.
- Rate limiting or verification page: switch to a logged-in profile and capture evidence with `screenshot` or `html` for implementation follow-up.
- Browser unavailable or Marionette port errors: run `foxpilot doctor`; Foxpilot needs local WebDriver socket access and a writable claude profile directory.
- GitHub DOM changed: retry with `--visible`, then inspect the page with generic `read`, `find`, and `html` commands.
- Explore pages changed or returned sparse results: retry with `--visible`; discovery pages are more dynamic than repository pages.
- Headless blocked or incomplete: retry in the default `claude` profile or with `--zen`.

## Plugin Migration Notes

The plugin command shape keeps the current top-level branch:

```bash
foxpilot github repo owner/repo --json
foxpilot github pr 42 --repo owner/repo --json
foxpilot github actions owner/repo --json
```

The built-in plugin metadata points at the existing GitHub service so CLI and future MCP site tools can share the same behavior.

## Sources

- GitHub Explore: <https://github.com/explore>
- GitHub Trending: <https://github.com/trending>
- GitHub Topics: <https://github.com/topics/python>

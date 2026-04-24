# Site Command Branches Design

Date: 2026-04-24

Status: Draft

Owner: Foxpilot

## Summary

Foxpilot should add site-specific command branches for high-value websites and web workflows. The first branch should be `foxpilot youtube`, followed by `github`, `docs`, Google Workspace helpers, generic page inspection helpers, synchronization commands, and reusable macros.

The core idea is simple: Foxpilot already exposes powerful browser primitives such as `go`, `read`, `click`, `fill`, `search`, `tabs`, screenshots, design inspection, and MCP tools. Site command branches should compose those primitives into predictable, documented workflows for places agents visit often.

Example:

```bash
foxpilot youtube help
foxpilot youtube search "rust async tutorial"
foxpilot youtube open "https://www.youtube.com/watch?v=..."
foxpilot youtube transcript "https://www.youtube.com/watch?v=..."
foxpilot youtube metadata
```

Each branch must be discoverable from the CLI, documented in the repository, testable without needing a live browser where possible, and structured so new sites can be added without turning `src/foxpilot/cli.py` into a large monolith.

## Goals

1. Make common website workflows faster and less fragile for agents.
2. Provide `foxpilot <site> help` for every site branch, in addition to Typer's native `--help`.
3. Keep site branches thin wrappers over reusable browser primitives and site modules.
4. Add a stable documentation standard for every CLI branch.
5. Support both human CLI use and eventual MCP exposure.
6. Keep the first implementation small enough to ship, while designing a path to many branches.
7. Prefer structured outputs where agents need to consume results.
8. Respect Foxpilot's existing modes: default `claude`, `--visible`, `--zen`, and `--headless-mode`.

## Non-goals

1. Do not build a general browser extension system in the first phase.
2. Do not replace the existing generic commands.
3. Do not use official site APIs as the primary path unless that API is already configured and clearly better than browser automation.
4. Do not promise that every site branch works in headless mode. Many logged-in or anti-automation flows need the dedicated `claude` profile or `--zen`.
5. Do not build a large plugin marketplace before the core site-branch shape is proven.

## Current State

Foxpilot is a Python CLI using Typer. It exposes a single top-level `app` in `src/foxpilot/cli.py`.

Current capabilities include:

- Browser modes: `claude`, `zen`, and `headless`.
- Observation commands: `tabs`, `url`, `read`, `find`, `screenshot`, `html`.
- Action commands: `go`, `search`, `click`, `fill`, `select`, `scroll`, `back`, `forward`, `key`.
- Tab commands: `tab`, `new-tab`, `close-tab`.
- Claude profile lifecycle commands: `login`, `show`, `hide`, `status`, `import-cookies`.
- Design inspection: `styles`, `assets`, `fullpage`, `burst`, `record`, `canvas-screenshot`.
- Escape hatches: `js`, `css-click`, `css-fill`.
- MCP server mirror in `src/foxpilot/mcp_server.py`.

The main risk in adding site branches is code growth inside `cli.py`. The design should move site-specific behavior into separate modules and register subcommands from a small CLI assembly layer.

## Product Principles

### Site branches are shortcuts, not a second automation engine

Site branches should reuse the same `browser()` context manager and shared Selenium helpers. If a behavior is useful across websites, it belongs in a generic module or generic CLI command first.

### Every branch must teach itself

For every site branch, these must work:

```bash
foxpilot <site> help
foxpilot <site> --help
foxpilot <site> <command> --help
```

The help output should include:

- Available commands.
- Short examples.
- Required authentication state.
- Mode support.
- Common failure modes.

### Output must be agent-friendly

Human-readable text remains the default. Commands that return structured information should support `--json` so an agent can consume stable fields without scraping text.

Example:

```bash
foxpilot youtube metadata --json
```

### Browser mode compatibility must be explicit

Each command should document whether it supports:

- `claude`: dedicated logged-in profile, hidden by default.
- `--visible`: dedicated profile visible for login or inspection.
- `--zen`: user's real browser session.
- `--headless-mode`: throwaway browser, best for public stateless pages.

### Site branches should fail with next actions

Failures should explain what to do next:

- "Not signed in. Run `foxpilot login https://youtube.com` or `foxpilot import-cookies --domain youtube.com --include-storage`."
- "Transcript button not found. Try `--visible` and inspect the page, or pass `--lang`."
- "This command needs the current page to be a YouTube watch page. Run `foxpilot youtube open <url>` first."

## Proposed Architecture

### Package layout

Add a `sites` package and move each branch into a focused module:

```text
src/foxpilot/
  cli.py
  core.py
  mcp_server.py
  search.py
  sites/
    __init__.py
    common.py
    youtube.py
    github.py
    docs.py
    google.py
    page.py
    macro.py
    wait.py
```

Responsibilities:

- `cli.py`: top-level Typer app, global mode callback, subapp registration.
- `sites/common.py`: shared helpers for formatting, JSON output, URL validation, command help text, browser-mode diagnostics.
- `sites/youtube.py`: YouTube-specific browser workflows and Typer app.
- `sites/github.py`: GitHub-specific browser workflows and Typer app.
- `sites/docs.py`: documentation search/open/read workflows.
- `sites/google.py`: Gmail/Drive/Calendar/Docs helper workflows.
- `sites/page.py`: richer generic page understanding commands.
- `sites/macro.py`: record/replay browser workflows.
- `sites/wait.py`: wait/expect synchronization commands.

The first implementation can add only `common.py` and `youtube.py`, while reserving this layout.

### Typer subapp registration

`cli.py` should register each branch as a Typer subapp:

```python
from foxpilot.sites.youtube import app as youtube_app

app.add_typer(youtube_app, name="youtube", help="YouTube navigation and extraction helpers.")
```

Each site module owns its own app:

```python
app = typer.Typer(
    help="YouTube helpers for search, video pages, transcripts, playlists, and metadata.",
    no_args_is_help=True,
)
```

Each site module also exposes an explicit `help` command:

```python
@app.command(name="help")
def help_command():
    """Show YouTube command examples and mode notes."""
```

Typer already supports `--help`, but the explicit `help` command satisfies the user-facing requirement that `foxpilot youtube help` works.

### Shared branch contract

Every site branch must provide:

1. A Typer subapp.
2. A `help` command.
3. A docs section in `README.md` or a dedicated file under `docs/commands/`.
4. At least one command registration test.
5. A mode support table.
6. A short authentication note.
7. Consistent error messages.
8. Optional `--json` for structured commands.

### Shared result types

Introduce lightweight dataclasses or typed dictionaries for common result shapes:

```python
VideoResult = TypedDict("VideoResult", {
    "title": str,
    "url": str,
    "channel": str,
    "duration": str,
    "published": str,
    "views": str,
})

TranscriptResult = TypedDict("TranscriptResult", {
    "url": str,
    "title": str,
    "language": str,
    "segments": list[dict],
    "text": str,
})
```

These are internal contracts. CLI output can format them as text or JSON.

### JSON option helper

Add a small shared helper:

```python
def emit(data: object, json_output: bool = False) -> None:
    if json_output:
        typer.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        typer.echo(format_human(data))
```

Each command can use its own formatter, but the JSON handling should be consistent.

## Command Branches

## `foxpilot youtube`

### Purpose

YouTube is a high-value target for agents because it combines search, videos, channels, playlists, transcripts, comments, and recommendations. A YouTube branch should let agents navigate and extract useful information without repeatedly hand-rolling generic `go`, `click`, `read`, and `find` sequences.

### Initial command set

```bash
foxpilot youtube help
foxpilot youtube search <query> [--limit N] [--json]
foxpilot youtube open <url-or-query> [--kind video|channel|playlist|search] [--json]
foxpilot youtube metadata [url] [--json]
foxpilot youtube transcript [url] [--lang LANG] [--format text|segments|srt|json]
foxpilot youtube comments [url] [--limit N] [--sort top|newest] [--json]
foxpilot youtube channel [url-or-name] [--json]
foxpilot youtube playlist [url] [--limit N] [--json]
foxpilot youtube related [url] [--limit N] [--json]
```

### MVP commands

The first shippable version should include:

```bash
foxpilot youtube help
foxpilot youtube search <query> [--limit N] [--json]
foxpilot youtube open <url-or-query> [--json]
foxpilot youtube metadata [url] [--json]
foxpilot youtube transcript [url] [--format text|json]
```

This covers the most valuable workflows while keeping the first patch manageable.

### URL handling

Accepted YouTube inputs:

- Full video URL: `https://www.youtube.com/watch?v=VIDEO_ID`
- Short video URL: `https://youtu.be/VIDEO_ID`
- Shorts URL: `https://www.youtube.com/shorts/VIDEO_ID`
- Playlist URL: `https://www.youtube.com/playlist?list=PLAYLIST_ID`
- Channel URL: `https://www.youtube.com/@handle`
- Search query: any non-URL string

`open` should infer the input type unless `--kind` is provided.

### Search behavior

`youtube search` should navigate to:

```text
https://www.youtube.com/results?search_query=<encoded query>
```

Then extract visible video results from the page.

Target fields:

- `title`
- `url`
- `video_id`
- `channel`
- `channel_url`
- `duration`
- `views`
- `published`
- `thumbnail`

Human output example:

```text
[1] Rust Async Explained
    https://www.youtube.com/watch?v=abc123
    channel: Example Channel
    duration: 18:42
    views: 120K
    published: 2 years ago
```

JSON output example:

```json
[
  {
    "title": "Rust Async Explained",
    "url": "https://www.youtube.com/watch?v=abc123",
    "video_id": "abc123",
    "channel": "Example Channel",
    "channel_url": "https://www.youtube.com/@example",
    "duration": "18:42",
    "views": "120K views",
    "published": "2 years ago",
    "thumbnail": "https://i.ytimg.com/..."
  }
]
```

Extraction should use DOM selectors first and fall back to page text only if the selectors fail.

### Open behavior

`youtube open` should:

1. Resolve a URL or search query.
2. Navigate to the best target.
3. Wait for the page to become usable.
4. Return page title, URL, and inferred entity type.

For a search query, `open` can either:

- Open YouTube search results.
- If `--kind video` is passed, open the first video result.

Default should be conservative: open search results for queries, direct page for URLs.

### Metadata behavior

`youtube metadata` should work on the current page if no URL is passed.

For videos, target fields:

- `title`
- `url`
- `video_id`
- `channel`
- `channel_url`
- `description`
- `published`
- `views`
- `likes` when visible
- `duration` when available
- `is_live`
- `is_short`

For channels:

- `name`
- `url`
- `handle`
- `subscriber_count`
- `description`
- `tabs`

For playlists:

- `title`
- `url`
- `playlist_id`
- `channel`
- `video_count`
- `videos`

The MVP can focus only on videos.

### Transcript behavior

`youtube transcript` is the most valuable command and likely the hardest.

It should support:

```bash
foxpilot youtube transcript
foxpilot youtube transcript https://www.youtube.com/watch?v=abc123
foxpilot youtube transcript --lang en
foxpilot youtube transcript --format json
foxpilot youtube transcript --format srt
```

Preferred extraction order:

1. Use YouTube's page data if transcript JSON is available in the loaded page.
2. Use YouTube's transcript panel by clicking "Show transcript" and reading segments.
3. Use timed text endpoints only when discoverable from the page and not requiring a separate API key.
4. Fail with a clear message when no transcript exists.

Output formats:

- `text`: plain transcript text.
- `segments`: timestamped text lines.
- `srt`: subtitle format for external use.
- `json`: structured result.

Segment shape:

```json
{
  "start": 12.34,
  "duration": 4.21,
  "text": "Example transcript text."
}
```

Failure cases:

- Captions disabled.
- Transcript hidden behind UI changes.
- Age-restricted or members-only content.
- Video unavailable in region.
- Login required.

The command should never pretend an unavailable transcript is empty. It should exit non-zero and explain why.

### Comments behavior

`youtube comments` should be a later phase because comments are lazy-loaded and sometimes hostile to automation.

Behavior:

1. Open video if URL passed.
2. Scroll to comments.
3. Wait for comments container.
4. Extract author, text, likes, relative time, and reply count.
5. Respect `--limit`.

Sorting is best-effort because YouTube UI can change and may require clicking dropdowns.

### Channel behavior

`youtube channel` should summarize a channel page:

- Channel title.
- Handle.
- Subscriber count.
- Description.
- Home URL.
- Videos tab URL.
- Recent videos.
- Playlists.

It should accept channel URLs, handles, and names.

### Playlist behavior

`youtube playlist` should list videos in order:

- Index.
- Title.
- URL.
- Duration.
- Channel.

It should support `--limit` and `--json`.

### Related behavior

`youtube related` should extract recommendations from the current watch page:

- Title.
- URL.
- Channel.
- Duration.

This is useful for research chains, but it should come after metadata and transcript.

### Authentication notes

Public YouTube search and public videos should work without login in many cases. However, logged-in behavior matters for:

- Age-restricted videos.
- Region or consent flows.
- YouTube Premium-only features.
- Personalized recommendations.
- Saved playlists and subscriptions.

Documentation should recommend:

```bash
foxpilot login https://youtube.com
foxpilot import-cookies --domain youtube.com --include-storage
```

Use `import-cookies` when login is blocked by automation detection.

### Mode support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `search` | yes | yes | yes | maybe |
| `open` | yes | yes | yes | maybe |
| `metadata` | yes | yes | yes | maybe |
| `transcript` | yes | yes | yes | maybe |
| `comments` | yes | yes | yes | no/fragile |
| `channel` | yes | yes | yes | maybe |
| `playlist` | yes | yes | yes | maybe |
| `related` | yes | yes | yes | maybe |

`maybe` means the command should try, but docs should warn about consent pages, script-heavy rendering, and anti-automation.

## `foxpilot github`

### Purpose

GitHub is the other high-value website for agents. Some workflows are better handled by the `gh` CLI, but browser automation is useful for logged-in UI state, rich pages, checks views, rendered markdown, Actions logs, issue forms, and PR review pages.

### Proposed commands

```bash
foxpilot github help
foxpilot github open <repo-or-url>
foxpilot github repo [repo-or-url] [--json]
foxpilot github issues [repo] [--state open|closed|all] [--limit N] [--json]
foxpilot github prs [repo] [--state open|closed|merged|all] [--limit N] [--json]
foxpilot github pr <number-or-url> [--json]
foxpilot github actions [repo] [--branch BRANCH] [--json]
foxpilot github file <repo> <path> [--branch BRANCH]
foxpilot github search <query> [--type repos|code|issues|prs|users] [--json]
```

### Integration policy

If `gh` is available and authenticated, future versions can optionally use it for structured data. The browser path should remain the common denominator.

The spec for this branch should explicitly decide whether to:

- Stay browser-only for consistency.
- Prefer `gh` for data and browser for rendered pages.
- Offer `--backend browser|gh|auto`.

Recommendation: start browser-only, then add `--backend auto` later.

## `foxpilot docs`

### Purpose

Agents constantly need official documentation. A `docs` branch should reduce the friction of finding, opening, and reading docs pages.

### Proposed commands

```bash
foxpilot docs help
foxpilot docs search <query> [--site SITE] [--json]
foxpilot docs open <query-or-url> [--site SITE]
foxpilot docs read [selector] [--full]
foxpilot docs links [--json]
foxpilot docs examples [--lang LANG] [--json]
```

### Site registry

Support known docs targets through a registry:

```text
python -> docs.python.org
mdn -> developer.mozilla.org
react -> react.dev
typescript -> typescriptlang.org/docs
typer -> typer.tiangolo.com
selenium -> selenium.dev/documentation
```

Do not hardcode too much into CLI parsing. Use a simple mapping in `sites/docs.py` or a future config file.

## `foxpilot google`

### Purpose

Google Workspace flows are useful but authentication-sensitive. This branch should be designed cautiously.

### Proposed commands

```bash
foxpilot google help
foxpilot google mail search <query> [--limit N]
foxpilot google mail open <query-or-index>
foxpilot google drive search <query> [--limit N]
foxpilot google drive open <query-or-url>
foxpilot google calendar today
foxpilot google docs open <query-or-url>
```

### Constraints

Google sign-in often blocks WebDriver-controlled browsers. Documentation must point users toward:

```bash
foxpilot import-cookies --domain google.com --include-storage
```

This branch should not be built until the branch framework and YouTube branch are stable.

## `foxpilot page`

### Purpose

Some ideas are not site-specific. They improve agent understanding of any page.

### Proposed commands

```bash
foxpilot page help
foxpilot page outline [--json]
foxpilot page links [--internal|--external|--all] [--json]
foxpilot page forms [--json]
foxpilot page buttons [--json]
foxpilot page inputs [--json]
foxpilot page tables [--json]
foxpilot page metadata [--json]
foxpilot page landmarks [--json]
```

These commands would turn generic page inspection into stable data. They should be useful before and after site-specific branches.

### Why this matters

Agents often need to answer questions like:

- What can I click?
- What forms exist?
- What links are important?
- What is the current page about?
- What table data is visible?
- What accessible landmarks exist?

Today, agents can approximate this with `read`, `find`, `html`, and `js`, but a structured page branch would be faster and less brittle.

## `foxpilot wait` and `foxpilot expect`

### Purpose

Browser automation is flaky when commands assume a page is ready. Foxpilot should add synchronization and assertion commands.

### Proposed commands

```bash
foxpilot wait text <text> [--timeout SEC]
foxpilot wait selector <selector> [--timeout SEC]
foxpilot wait url <substring-or-regex> [--timeout SEC]
foxpilot wait gone <selector> [--timeout SEC]
foxpilot wait idle [--timeout SEC]

foxpilot expect text <text> [--in SELECTOR]
foxpilot expect selector <selector>
foxpilot expect url <substring-or-regex>
foxpilot expect title <substring-or-regex>
```

The existing `assert` command can either remain as-is or become an alias under `expect`.

### Behavior

- `wait` polls until a condition is true or times out.
- `expect` checks immediately and exits non-zero if false.
- Both should print current URL on failure.
- Both should support `--json` later for structured test runners.

## `foxpilot macro`

### Purpose

Macros let users turn repeated browser workflows into reusable commands without needing new Python code each time.

### Proposed commands

```bash
foxpilot macro help
foxpilot macro record <name>
foxpilot macro run <name> [args...]
foxpilot macro list
foxpilot macro show <name>
foxpilot macro edit <name>
foxpilot macro delete <name>
```

### Macro format

Use a simple file format under:

```text
~/.local/share/foxpilot/macros/
```

Example:

```yaml
name: youtube-search
description: Search YouTube and open the first result.
params:
  - query
steps:
  - go: "https://www.youtube.com/results?search_query={{query|urlencode}}"
  - wait:
      selector: "ytd-video-renderer"
      timeout: 15
  - click:
      selector: "ytd-video-renderer a#video-title"
  - wait:
      url: "watch?v="
      timeout: 15
```

This should be a later phase. The first phase should not build a macro system before there are enough stable primitives.

## `foxpilot site`

### Purpose

As site branches grow, users need discovery.

### Proposed commands

```bash
foxpilot site help
foxpilot site list
foxpilot site info <name>
foxpilot site docs <name>
foxpilot site diagnose <name>
```

This branch can be added after two or more site branches exist.

## Documentation Standard

### Repository documentation

Add a docs directory:

```text
docs/
  commands/
    youtube.md
    github.md
    docs.md
    google.md
    page.md
    wait-expect.md
    macro.md
```

The README should contain a concise index and link to the detailed files.

### Per-branch documentation template

Each branch doc should include:

1. Summary.
2. Authentication/session requirements.
3. Mode support table.
4. Commands.
5. Examples.
6. JSON output schema.
7. Failure modes.
8. Testing notes.
9. Known limitations.

### CLI help template

`foxpilot <branch> help` should be shorter than the docs file but richer than plain command listing.

Example outline:

```text
foxpilot youtube - YouTube search, video metadata, transcripts, and playlists

Common commands:
  foxpilot youtube search "query"
  foxpilot youtube open "query or url"
  foxpilot youtube metadata
  foxpilot youtube transcript

Auth:
  Public pages often work without login.
  For logged-in YouTube, run:
    foxpilot login https://youtube.com
    foxpilot import-cookies --domain youtube.com --include-storage

Modes:
  default claude: recommended
  --zen: use your real browser
  --headless-mode: best effort only

Run:
  foxpilot youtube <command> --help
```

## Error Handling Standard

Errors should include:

- What failed.
- The current URL if a browser was involved.
- The likely reason.
- The next command to try.

Example:

```text
error: no transcript found
url: https://www.youtube.com/watch?v=abc123
reason: transcript panel was unavailable or captions are disabled
next: try `foxpilot --visible youtube transcript`, or verify the video has captions
```

For CLI failures, exit code should be non-zero.

## Testing Strategy

### Unit tests

Tests should not require a live browser for:

- URL parsing.
- YouTube video ID extraction.
- YouTube URL normalization.
- Human output formatting.
- JSON output formatting.
- Help command registration.
- Branch app registration.

Suggested tests:

```text
tests/test_youtube_urls.py
tests/test_youtube_formatting.py
tests/test_cli_site_branches.py
```

### CLI registration tests

Use Typer's `CliRunner`:

```python
result = runner.invoke(app, ["youtube", "help"])
assert result.exit_code == 0
assert "youtube search" in result.output
```

Also test:

```python
runner.invoke(app, ["youtube", "--help"])
runner.invoke(app, ["youtube", "search", "--help"])
```

### Browser integration tests

Live browser tests should be marked separately because they depend on:

- Firefox or Zen.
- Geckodriver.
- Network.
- YouTube DOM stability.
- Auth state for some flows.

Suggested marker:

```ini
[tool.pytest.ini_options]
markers = [
  "browser: requires live browser automation",
  "network: requires network access",
]
```

### Golden output tests

For structured commands, keep sample extracted data and assert formatter output. This prevents help and output regressions without requiring live YouTube.

## MCP Strategy

The CLI should lead. MCP can mirror stable commands after the CLI contracts settle.

For the first YouTube phase, MCP tools could be:

```text
youtube_search
youtube_open
youtube_metadata
youtube_transcript
```

MCP tools should return strings initially to match existing `mcp_server.py` style. Later, if the server supports richer structured responses, the same underlying result dictionaries can be reused.

Do not duplicate browser logic in `mcp_server.py`. Both CLI and MCP should call functions in `sites/youtube.py` or a lower-level service module.

Recommended internal layering:

```text
sites/youtube.py
  Typer commands
  human formatting

sites/youtube_service.py
  URL parsing
  Selenium extraction
  result dictionaries

mcp_server.py
  thin wrappers calling youtube_service
```

For the first patch, `youtube.py` can contain both CLI and service helpers if it stays small. Split when it grows.

## Implementation Plan

### Phase 1: Branch framework and YouTube MVP

Deliver:

- `src/foxpilot/sites/__init__.py`
- `src/foxpilot/sites/common.py`
- `src/foxpilot/sites/youtube.py`
- Register `youtube` in `cli.py`.
- Add `foxpilot youtube help`.
- Add `youtube search`.
- Add `youtube open`.
- Add `youtube metadata` for current video pages.
- Add `youtube transcript` best-effort.
- Add tests for URL parsing, formatting, help, and registration.
- Add documentation for YouTube branch.

Keep browser extraction conservative. If transcript extraction proves unstable, ship `search`, `open`, and `metadata` first, then transcript as Phase 1b.

### Phase 2: Generic page and wait/expect commands

Deliver:

- `foxpilot page outline`
- `foxpilot page links`
- `foxpilot page forms`
- `foxpilot page buttons`
- `foxpilot page metadata`
- `foxpilot wait text`
- `foxpilot wait selector`
- `foxpilot expect text`
- `foxpilot expect selector`

This improves all site branches and makes YouTube automation more reliable.

### Phase 3: YouTube expansion

Deliver:

- `youtube comments`
- `youtube channel`
- `youtube playlist`
- `youtube related`
- Improved transcript language support.
- Optional SRT output.

### Phase 4: GitHub branch

Deliver browser-first GitHub workflows:

- Repo summary.
- PR summary.
- Issues list.
- Actions status.
- File open/read helper.

Evaluate whether `gh` integration should be optional.

### Phase 5: Docs branch

Deliver:

- Known docs site registry.
- Docs search.
- Docs open.
- Docs read.
- Examples extraction.

### Phase 6: Google Workspace branch

Deliver only after cookie import and auth docs are mature.

Start with read-only workflows:

- Gmail search/open.
- Drive search/open.
- Calendar today.
- Docs open.

### Phase 7: Macros and site registry

Deliver:

- Macro storage format.
- Macro run/list/show.
- Optional record later.
- `foxpilot site list`
- `foxpilot site info`
- `foxpilot site diagnose`

## Detailed First-Patch Design

### `sites/common.py`

Functions:

```python
def emit_json_or_text(data: object, json_output: bool, formatter: Callable[[object], str]) -> None:
    ...

def require_youtube_watch_url(url: str) -> str:
    ...

def current_page_summary(driver) -> dict:
    ...

def wait_for_selector(driver, selector: str, timeout_s: float = 10.0):
    ...

def command_error(message: str, *, url: str = "", reason: str = "", next_step: str = "") -> NoReturn:
    ...
```

Keep this module small. Only move a helper here when at least two branches need it.

### `sites/youtube.py`

Top-level pieces:

```python
app = typer.Typer(...)

@app.command(name="help")
def cmd_help(): ...

@app.command(name="search")
def cmd_search(...): ...

@app.command(name="open")
def cmd_open(...): ...

@app.command(name="metadata")
def cmd_metadata(...): ...

@app.command(name="transcript")
def cmd_transcript(...): ...
```

Internal helpers:

```python
def is_youtube_url(value: str) -> bool: ...
def normalize_youtube_url(value: str) -> str: ...
def extract_video_id(value: str) -> str | None: ...
def youtube_search_url(query: str) -> str: ...
def extract_search_results(driver, limit: int) -> list[dict]: ...
def extract_video_metadata(driver) -> dict: ...
def extract_transcript(driver, lang: str | None = None) -> dict: ...
```

### `cli.py` changes

Add only the import and registration:

```python
from foxpilot.sites.youtube import app as youtube_app

app.add_typer(youtube_app, name="youtube", help="YouTube search, metadata, transcripts, and playlists.")
```

Avoid placing YouTube behavior directly in `cli.py`.

### Documentation changes

Add:

```text
docs/commands/youtube.md
```

Update README CLI section with a short "Site branches" section:

````markdown
### Site branches

Site branches bundle common workflows for high-value websites.

```bash
foxpilot youtube help
foxpilot youtube search "rust async tutorial"
foxpilot youtube transcript https://www.youtube.com/watch?v=...
```
````

## Risks and Mitigations

### YouTube DOM instability

Risk: YouTube frequently changes markup.

Mitigation:

- Use multiple selectors.
- Keep extraction helpers isolated.
- Add formatter and parser tests.
- Keep failure messages clear.
- Prefer page data when available.

### Anti-automation and login friction

Risk: Some pages block WebDriver or show consent/login walls.

Mitigation:

- Recommend `claude` profile by default.
- Document `import-cookies`.
- Add `diagnose` later.
- Keep `--visible` examples prominent.

### CLI sprawl

Risk: Site branches make `cli.py` too large.

Mitigation:

- Register subapps only in `cli.py`.
- Put branch logic under `sites/`.
- Split service modules when site files grow.

### Duplicated CLI and MCP logic

Risk: Browser workflows get copied into MCP tools.

Mitigation:

- Put extraction logic in service helpers.
- Keep MCP wrappers thin.
- Add MCP after CLI contracts stabilize.

### Overbuilding too early

Risk: Macro registry, site registry, and many branches delay the useful YouTube MVP.

Mitigation:

- Ship YouTube MVP first.
- Add generic `page` and `wait` helpers next.
- Defer macros until command primitives are stable.

## Open Questions

1. Should YouTube transcript extraction use browser-only methods at first, or is a non-browser timed-text endpoint acceptable when discovered from the page?
2. Should `--json` be added globally to all structured commands, or only branch commands that need it?
3. Should MCP mirror site commands immediately or wait until CLI behavior is proven?
4. Should `foxpilot assert` be kept as-is, aliased to `expect`, or eventually replaced by `expect`?
5. Should site docs live entirely in `docs/commands/`, or should README contain full command docs for the first few branches?

## Recommendation

Build this in this order:

1. Create the site branch framework.
2. Ship `foxpilot youtube help`, `search`, `open`, and `metadata`.
3. Add `transcript` once extraction is verified against several public videos.
4. Add `page` and `wait/expect` because they make every site branch stronger.
5. Add GitHub and docs branches.
6. Defer Google Workspace and macros until auth and primitives are stronger.

This gives Foxpilot immediate value without locking the project into a heavy plugin architecture too early.

# Foxpilot Plugin Expansion Spec

Date: 2026-04-24

Status: Draft

Owner: Foxpilot

## Summary

Foxpilot should evolve from a browser automation CLI with site-specific branches into a small agent browser platform with a plugin folder, built-in YouTube and GitHub plugins, reusable workflow recording, evidence capture, self-healing selectors, and higher-level mission execution.

The core change is to make website workflows installable and discoverable as plugins instead of hard-coding every site branch into `src/foxpilot/cli.py`. Built-in plugins should ship with Foxpilot for common workflows, while user plugins should live in a local plugin directory.

The first plugin targets are:

1. `youtube`: search videos, open videos, extract metadata, extract transcripts, inspect playlists.
2. `github`: inspect repositories, explore topics, read issues and pull requests, inspect Actions failures, collect logs and summaries.

The larger roadmap layers on top of the plugin system:

1. Mission Mode.
2. Evidence Bundles.
3. Self-Healing Click and Fill.
4. Macro Recorder That Becomes Code.
5. Page Brain.
6. Agent Safety Layer.
7. Workflow Branches.
8. Doctor With Fix Commands.
9. Visual QA Mode.
10. Local Plugin System.

## Goals

1. Add a `plugins/` folder model for built-in and user-defined Foxpilot plugins.
2. Convert YouTube and GitHub site workflows into first-class plugins.
3. Keep the existing CLI shape simple: `foxpilot <plugin> <command>`.
4. Make plugins usable from both CLI and MCP without duplicating implementation logic.
5. Give every plugin help text, docs, structured output support, and tests.
6. Add an evidence system so agent browser work leaves auditable artifacts.
7. Make element actions less brittle through selector memory and fallback strategies.
8. Add a mission layer that can execute multi-step browser tasks with checkpoints.
9. Keep the first implementation incremental and shippable.

## Non-Goals

1. Do not build a public marketplace in the first pass.
2. Do not require users to publish packages to create local plugins.
3. Do not replace generic browser commands such as `go`, `read`, `click`, `fill`, and `screenshot`.
4. Do not use official site APIs as the main path unless the plugin explicitly opts into them.
5. Do not make all plugins work in headless mode. Authenticated and anti-automation-heavy flows may require `claude` mode or `--zen`.
6. Do not add autonomous destructive actions without confirmation boundaries.

## Existing Context

Foxpilot currently provides:

- Browser modes: `claude`, `--visible`, `--zen`, and `--headless-mode`.
- Generic browser commands: `go`, `read`, `click`, `fill`, `find`, `screenshot`, `html`, `js`, and related helpers.
- Site branches under `src/foxpilot/sites/`.
- CLI registration in `src/foxpilot/cli.py`.
- MCP exposure in `src/foxpilot/mcp_server.py`.
- Tests under `tests/`.
- Command docs under `docs/commands/`.

The current site branch direction is useful, but it will become hard to maintain if every site is a direct import in the CLI. A plugin registry gives Foxpilot a stable expansion point.

## Proposed File Layout

```text
src/foxpilot/
  cli.py
  core.py
  mcp_server.py
  actions.py
  results.py
  plugins/
    __init__.py
    registry.py
    types.py
    loader.py
    builtin/
      __init__.py
      youtube/
        __init__.py
        plugin.py
        service.py
        README.md
      github/
        __init__.py
        plugin.py
        service.py
        README.md
  safety.py
  evidence.py
  selector_memory.py
  mission.py

plugins/
  README.md
  examples/
    simple_site/
      plugin.py
      README.md

docs/
  commands/
    plugins.md
    youtube.md
    github.md
    mission.md
    evidence.md
    qa.md
```

There are two plugin roots:

1. `src/foxpilot/plugins/builtin/` for plugins shipped with Foxpilot.
2. `plugins/` at the repository root for local examples and development plugins.

A future user-level plugin root can be added later:

```text
~/.config/foxpilot/plugins/
```

## Plugin Contract

Every plugin must expose a `plugin.py` file with a `register()` function.

Conceptual shape:

```python
def register(context: PluginContext) -> Plugin:
    return Plugin(
        name="youtube",
        help="YouTube search, video metadata, transcripts, and playlists.",
        cli_app=build_cli_app(context),
        mcp_tools=build_mcp_tools(context),
        docs_path="README.md",
    )
```

The plugin contract should support:

- Plugin name.
- Short help text.
- Typer CLI app.
- Optional MCP tool definitions.
- Optional service object for shared implementation.
- Docs path.
- Required authentication notes.
- Supported browser modes.
- Test fixture hooks.

Plugins must not own browser lifecycle directly. They receive a browser factory or command context from Foxpilot.

## Plugin Discovery

Foxpilot should discover plugins in this order:

1. Built-in plugins under `src/foxpilot/plugins/builtin/`.
2. Project-local plugins under `./plugins/`.
3. User-local plugins under `~/.config/foxpilot/plugins/` in a later phase.

If two plugins use the same name, the built-in plugin wins by default. A later override flag can allow local development to shadow a built-in plugin.

Plugin load failures should not break the whole CLI. Foxpilot should report a concise warning in `foxpilot plugins list --verbose` and skip broken plugins during normal command use.

## CLI Surface

New plugin commands:

```bash
foxpilot plugins list
foxpilot plugins info youtube
foxpilot plugins doctor
foxpilot plugins path
```

Plugin commands remain natural:

```bash
foxpilot youtube search "rust async tutorial"
foxpilot youtube metadata --json
foxpilot youtube transcript --format json
foxpilot github repo owner/repo
foxpilot github actions failed --json
foxpilot github pr 123 --json
```

The top-level CLI should register plugin subcommands dynamically after global mode options are parsed.

## MCP Surface

MCP should expose plugin tools through the same plugin registry. Tool names should be stable and explicit:

```text
youtube_search
youtube_metadata
youtube_transcript
github_repo
github_actions_failed
github_pr
mission_run
evidence_bundle
page_understand
qa_run
```

MCP adapters must remain thin. They should call plugin service functions and return structured results.

## Built-In YouTube Plugin

### Purpose

The YouTube plugin helps agents search, inspect, and extract useful information from YouTube pages without fragile manual browsing.

### Commands

```bash
foxpilot youtube help
foxpilot youtube search "query" [--json] [--limit 10]
foxpilot youtube open URL_OR_ID
foxpilot youtube metadata [--json]
foxpilot youtube transcript [--format text|json] [--lang en]
foxpilot youtube playlist [--json]
foxpilot youtube comments [--json] [--limit 50]
```

### Structured Results

Video metadata should include:

- `title`
- `url`
- `video_id`
- `channel`
- `channel_url`
- `duration`
- `views`
- `published`
- `description`
- `chapters`

Transcript results should include:

- `title`
- `url`
- `language`
- `segments`
- `text`
- `source`

### Failure Behavior

Failures should explain the next action:

- If transcript controls are missing, suggest `--visible` and evidence capture.
- If YouTube blocks automation, suggest `foxpilot import-cookies --domain youtube.com --include-storage`.
- If the current page is not a watch page, suggest `foxpilot youtube open <url>`.

## Built-In GitHub Plugin

### Purpose

The GitHub plugin helps agents inspect repositories, pull requests, issues, Actions failures, releases, and project activity through the browser session.

### Commands

```bash
foxpilot github help
foxpilot github repo owner/repo [--json]
foxpilot github explore --topic ai [--json]
foxpilot github issue owner/repo 123 [--json]
foxpilot github pr owner/repo 123 [--json]
foxpilot github actions owner/repo [--json]
foxpilot github actions failed owner/repo [--json]
foxpilot github actions logs owner/repo RUN_ID [--json]
foxpilot github releases owner/repo [--json]
```

### Structured Results

Repository results should include:

- `owner`
- `repo`
- `url`
- `description`
- `default_branch`
- `stars`
- `forks`
- `open_issues`
- `latest_commit`
- `languages`

Pull request results should include:

- `title`
- `state`
- `author`
- `branch`
- `base`
- `checks`
- `files_changed`
- `review_state`
- `conversation_summary`

Actions results should include:

- `workflow`
- `run_id`
- `status`
- `conclusion`
- `failed_jobs`
- `log_excerpt`
- `likely_cause`

### Failure Behavior

Failures should explain whether the issue is authentication, missing access, a private repository, rate limiting, or a page shape change.

## Mission Mode

Mission Mode lets a user describe a browser task in plain language and receive a planned, auditable execution.

Example:

```bash
foxpilot mission "download the latest invoice from OneDrive"
```

Mission Mode should:

1. Translate the request into steps.
2. Show the plan unless `--yes` is passed.
3. Execute one browser action at a time.
4. Capture evidence at each checkpoint.
5. Stop before dangerous actions unless confirmed.
6. Return a final summary with links to evidence files.

Initial commands:

```bash
foxpilot mission run "task"
foxpilot mission resume MISSION_ID
foxpilot mission status MISSION_ID
foxpilot mission cancel MISSION_ID
```

Mission state should be saved under:

```text
~/.local/share/foxpilot/missions/
```

## Evidence Bundles

Evidence Bundles save the state of browser work so an agent or human can audit what happened.

Command:

```bash
foxpilot evidence bundle /tmp/task-name
```

Each bundle should include:

```text
bundle.json
screenshot.png
fullpage.png
page.html
readable.txt
url.txt
console.json
actions.jsonl
```

`bundle.json` should include:

- timestamp
- browser mode
- title
- URL
- command name
- plugin name, if any
- artifact paths
- redaction summary

Evidence capture should be available as:

1. A standalone command.
2. A `--evidence DIR` option on key commands.
3. Automatic capture inside Mission Mode.

## Self-Healing Click and Fill

Foxpilot should remember successful element targets and use that memory as a fallback when page structure changes.

For each successful click or fill, store:

- URL pattern.
- Domain.
- Action type.
- User description.
- Element tag.
- Role.
- Text.
- ARIA label.
- Placeholder.
- Name.
- ID.
- CSS path.
- XPath fallback.
- Nearby label text.
- Screenshot crop path, if evidence is enabled.

Storage path:

```text
~/.local/share/foxpilot/selector-memory.jsonl
```

Lookup order:

1. Exact semantic match from current page.
2. Stored role/text/label match for same domain.
3. Stored CSS path if still valid.
4. Stored XPath fallback.
5. JavaScript click fallback.

Every fallback should explain what happened in command output.

## Macro Recorder That Becomes Code

Macro recording should capture browser actions and convert them into durable automation artifacts.

Commands:

```bash
foxpilot macro record NAME
foxpilot macro run NAME
foxpilot macro export NAME --format shell
foxpilot macro export NAME --format python
foxpilot macro export NAME --format mcp
foxpilot macro export NAME --format markdown
```

Exports should support:

- Shell script.
- Python test.
- MCP tool recipe.
- Markdown runbook.

Macros should use semantic actions where possible instead of raw selectors.

## Page Brain

Page Brain should turn the current page into an agent-friendly map.

Command:

```bash
foxpilot page understand [--json]
```

Output should include:

- Page title and URL.
- Login/auth state guess.
- Main headings.
- Forms.
- Buttons.
- Links.
- Tables.
- Inputs.
- Dangerous actions.
- Suggested next actions.
- Visible error messages.

This should be powered by DOM inspection and readable text extraction, not by screenshots alone.

## Agent Safety Layer

Foxpilot should add safety controls for real-browser and authenticated sessions.

Initial controls:

- Domain allowlist.
- Dangerous action detection.
- Confirmation before destructive actions.
- Redaction for screenshots, HTML, logs, and evidence bundles.
- `--dry-run` support for Mission Mode.
- Clear distinction between `claude`, `--zen`, and `--headless-mode`.

Dangerous action examples:

- Delete.
- Purchase.
- Send.
- Submit payment.
- Publish.
- Merge pull request.
- Transfer ownership.

Safety should be strictest in `--zen` mode because that mode operates on the user's real browser session.

## Workflow Branches

After YouTube and GitHub, the next plugins should be:

1. `gmail`: search, summarize thread, draft reply.
2. `calendar`: find free time, open event, extract details.
3. `docs`: search documentation, open canonical page, extract examples.
4. `drive`: locate, preview, download, and summarize files.
5. `local`: inspect local dev servers, screenshots, wait checks, smoke flows.
6. `github-actions`: this may remain inside `github` or become a separate plugin if it grows.

## Doctor With Fix Commands

`foxpilot doctor` should grow from diagnostics into repair guidance.

Commands:

```bash
foxpilot doctor
foxpilot doctor --fix
foxpilot doctor plugins
foxpilot doctor browser
foxpilot doctor hyprland
```

`--fix` should only perform safe, reversible repairs:

- Create missing Foxpilot data directories.
- Validate profile path writability.
- Write expected Marionette prefs.
- Check geckodriver availability.
- Print exact install commands for missing system dependencies.

It should not install system packages without explicit user approval.

## Visual QA Mode

Visual QA Mode checks whether a web page is usable across common viewports.

Command:

```bash
foxpilot qa http://localhost:3000
```

Checks:

- Desktop screenshot.
- Mobile screenshot.
- Console errors.
- Blank page detection.
- Missing image detection.
- Text overflow detection.
- Basic contrast warnings.
- Full-page screenshot artifact.

Outputs:

```text
qa-report.json
desktop.png
mobile.png
fullpage.png
summary.md
```

This is especially useful for agents building web apps.

## Implementation Phases

### Phase 1: Plugin Registry Foundation

Deliver:

- `src/foxpilot/plugins/registry.py`
- `src/foxpilot/plugins/types.py`
- `src/foxpilot/plugins/loader.py`
- `foxpilot plugins list`
- `foxpilot plugins info <name>`
- Tests for plugin discovery and conflict handling.

Acceptance:

- Built-in plugins can be discovered without direct imports in `cli.py`.
- Broken plugins do not break the whole CLI.
- Plugin metadata can be printed in human and JSON formats.

### Phase 2: Convert YouTube and GitHub to Built-In Plugins

Deliver:

- `src/foxpilot/plugins/builtin/youtube/`
- `src/foxpilot/plugins/builtin/github/`
- CLI registration through plugin registry.
- Shared service functions for CLI and MCP.
- Command docs.
- Tests for command registration and service formatting.

Acceptance:

- Existing `foxpilot youtube ...` commands still work.
- Existing `foxpilot github ...` commands still work.
- The CLI no longer needs direct imports for those branches.
- MCP uses the same service functions.

### Phase 3: Evidence Bundles

Deliver:

- `src/foxpilot/evidence.py`
- `foxpilot evidence bundle DIR`
- `--evidence DIR` for high-value commands.
- Evidence capture in YouTube and GitHub plugin workflows.

Acceptance:

- A bundle contains screenshot, URL, HTML, readable text, and metadata.
- Evidence files are redacted where possible.
- Bundle output is stable enough for tests.

### Phase 4: Self-Healing Selectors

Deliver:

- `src/foxpilot/selector_memory.py`
- Selector memory writes after successful `click` and `fill`.
- Fallback lookup before failure.
- Clear output when fallback is used.

Acceptance:

- Fake-driver tests prove fallback order.
- Existing click/fill behavior remains compatible.

### Phase 5: Macro Export Upgrade

Deliver:

- Macro export formats: shell, Python, MCP, markdown.
- Macro docs.
- Tests for exported content.

Acceptance:

- A recorded workflow can be exported as a runnable shell script.
- Python export uses Foxpilot APIs or CLI commands.
- Markdown export is readable as a runbook.

### Phase 6: Page Brain

Deliver:

- `foxpilot page understand`
- Structured DOM map.
- Dangerous action detection feed for safety layer.

Acceptance:

- Fixture tests cover forms, buttons, headings, tables, and errors.
- JSON output is stable.

### Phase 7: Agent Safety Layer

Deliver:

- Domain allowlist config.
- Dangerous action confirmation.
- Redaction utilities.
- Stricter `--zen` mode warnings.

Acceptance:

- Dangerous actions are detected in fixture pages.
- Mission Mode can pause before destructive actions.
- Redaction tests cover common secret patterns.

### Phase 8: Mission Mode

Deliver:

- `foxpilot mission run`
- Mission state storage.
- Step execution.
- Evidence checkpoints.
- Resume/status/cancel.

Acceptance:

- A mission can run against local fixtures.
- Failed missions save enough state to debug.
- Dangerous actions require confirmation.

### Phase 9: Visual QA Mode

Deliver:

- `foxpilot qa URL`
- Desktop and mobile screenshots.
- Console error capture.
- Basic visual checks.
- Report bundle.

Acceptance:

- QA command works against a local fixture server.
- Report includes screenshots and machine-readable findings.

## Testing Strategy

Use local fixture pages wherever possible. Live browser smoke tests should remain optional and skippable in restricted environments.

Required tests:

- Plugin registry discovery.
- Built-in plugin metadata.
- Broken plugin handling.
- YouTube service output formatting.
- GitHub service output formatting.
- CLI registration for plugin commands.
- MCP adapter calls into plugin services.
- Evidence bundle artifact creation.
- Selector memory fallback order.
- Macro export formatting.
- Page Brain DOM extraction.
- Safety dangerous-action detection.
- Mission state transitions.
- QA report generation.

Primary command:

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

## Documentation Strategy

Add or update:

- `README.md`
- `docs/commands/plugins.md`
- `docs/commands/youtube.md`
- `docs/commands/github.md`
- `docs/commands/mission.md`
- `docs/commands/evidence.md`
- `docs/commands/qa.md`
- `plugins/README.md`

Each plugin doc should include:

- What the plugin does.
- Auth requirements.
- Browser mode support.
- Command examples.
- JSON output examples.
- Common failures and next actions.

## Open Questions

1. Should local project plugins be enabled by default, or only when `--enable-local-plugins` is set?
2. Should plugin name conflicts be hard errors or warnings?
3. Should Mission Mode require confirmation before every step at first?
4. Should evidence capture default to off for privacy, or on for mission workflows?
5. Should GitHub Actions become a subcommand under `github` or a separate `github-actions` plugin?
6. Should plugin MCP tools be auto-exposed or require explicit opt-in metadata?

## Recommended First Build

Start with the smallest useful version:

1. Add the plugin registry.
2. Move YouTube and GitHub into built-in plugins.
3. Add `foxpilot plugins list` and `foxpilot plugins info`.
4. Add `plugins/README.md` with a local plugin example.
5. Add Evidence Bundles.
6. Add Self-Healing Selectors.

This sequence improves architecture without forcing the high-risk Mission Mode work too early. Once plugins, evidence, and selector memory are solid, Mission Mode can reuse those foundations instead of inventing its own browser control path.

# Plugin vs Site Module — Decision Guide

Foxpilot has two layers for adding domain-specific browser automation:

1. **Site module** — `src/foxpilot/sites/<name>.py` (Typer CLI) + `src/foxpilot/sites/<name>_service.py` (URL helpers, extraction, formatting). Wired into the top-level CLI in `src/foxpilot/cli.py`.
2. **Plugin** — `src/foxpilot/plugins/builtin/<name>/plugin.py` calling `register(context)` and returning a `Plugin` dataclass. The plugin can wrap an existing site module *and* expose it via the plugin registry, MCP tool surface, and `foxpilot plugins` discovery.

Site modules and plugins are not alternatives. **Plugins wrap site modules.** The question is not "module *or* plugin", it is "site module only, or site module *plus* plugin wrapper".

## TL;DR

- **Always start with a site module.** That is where the actual logic lives.
- **Add a plugin wrapper when** the site is reusable enough that you want it discoverable, MCP-callable, and shipped with auth + mode metadata.
- **Skip the plugin wrapper when** the work is one-off, exploratory, or tightly coupled to a specific mission/script.

## When to use a Site Module only

Use a site module without a plugin wrapper when **any** of these are true:

- The work is a one-off scrape or workflow you do not expect to repeat across sessions or share with other agents.
- The site is internal to a specific mission, macro, or test scaffold rather than a stable target.
- The selectors are still being explored and a stable command surface would freeze a moving target.
- You only need CLI + Python access, never MCP discovery or `foxpilot plugins list`.

A site module on its own already gives you:

- A `foxpilot <name> ...` CLI subcommand.
- A reusable Python service module callable from other site modules and tests.
- Browser-mode injection via `set_browser_factory`.

`onedrive` is an example of this state today: full site module + CLI commands, no plugin registration. It works as a CLI but does not show up under `foxpilot plugins list`, has no `auth_notes` / `browser_modes` metadata, and is not exposed through the MCP plugin surface.

## When to add a Plugin wrapper

Add a plugin wrapper on top of an existing site module when **any** of these are true:

- The site is a stable target you (or other agents) will hit repeatedly.
- You want it to appear in `foxpilot plugins list` and `foxpilot plugins info <name>` so it is discoverable without grepping the source tree.
- Auth requirements (cookies, login URL, supported `--zen` / `--headless-mode`) need to be declared in one canonical place.
- The site should be callable from MCP tools (`mcp__foxpilot__<name>_*`) so agents can use it without writing Python.
- You want load failures to be reported through the plugin diagnostics layer rather than blowing up the CLI on import.

A plugin adds, on top of the site module:

- A `Plugin` registry entry with `help`, `auth_notes`, `browser_modes`, `docs_path`.
- Automatic discovery from `src/foxpilot/plugins/builtin/<name>/plugin.py` — no manual import wiring.
- Source tracking (`builtin` vs `local`) so project-local plugins under `plugins/<name>/` are isolated from built-ins.
- Future MCP tool generation off the same `service` module.

## Local Plugins

Use a local plugin under `plugins/<name>/plugin.py` (not `src/foxpilot/plugins/builtin/`) when:

- The plugin is project-specific and should not ship inside the foxpilot package.
- You are prototyping a new built-in plugin and want fast iteration without modifying the package source.
- The site is sensitive (private SaaS, internal tools) and should not be visible upstream.

Promote local → built-in by moving the directory into `src/foxpilot/plugins/builtin/<name>/` once it stabilises.

## Decision Flow

```
       new browser-automation work
                  │
                  ▼
        will I run this more than
        once across sessions?
        ┌────────┴────────┐
       no                yes
        │                 │
        ▼                 ▼
  one-off js /     site module (sites/<name>.py
  evidence cmd      + sites/<name>_service.py)
                          │
                          ▼
                  do I want it discoverable
                  via `plugins list` / MCP /
                  with auth+mode metadata?
                  ┌────────┴────────┐
                 no                yes
                  │                 │
                  ▼                 ▼
            site module only   add plugin wrapper
            (e.g. current      (e.g. youtube,
            onedrive)          github, excel)
                                    │
                                    ▼
                          should it ship with the
                          package or stay project-local?
                          ┌────────┴────────┐
                         ship              local
                          │                 │
                          ▼                 ▼
                src/foxpilot/plugins/   plugins/<name>/
                builtin/<name>/        plugin.py
```

## Anti-patterns

- **Plugin without a site module.** Putting all the logic inside `plugin.py` means CLI, MCP, and Python callers cannot share the same code paths. Always factor logic into `sites/<name>_service.py`.
- **Site module without registering it in `cli.py`.** The plugin registry will discover the plugin, but the user-facing CLI subcommand only exists if `cli.py` calls `app.add_typer(...)`. Keep both in sync.
- **Plugin metadata that lies.** If `browser_modes=("claude", "headless")` is declared but headless never works because of auth walls, fix the metadata or the command — do not leave it stale.
- **Heavy logic in `plugin.py` itself.** Plugin module should only register; logic belongs in the site module / service. This keeps `register(context)` cheap and load-failure-safe.

## Current State (2026-04-25)

| Site | Site module | Plugin wrapper | Notes |
|---|---|---|---|
| `youtube` | yes | yes (built-in) | reference example |
| `github` | yes | yes (built-in) | reference example |
| `excel` | yes | yes (built-in) | new |
| `onedrive` | yes | **no** | candidate for promotion to plugin |
| `docs`, `page`, `macro`, `wait`, `expect` | yes | no | generic helpers, intentionally unwrapped |

If you wrap `onedrive` as a plugin, copy the `excel/plugin.py` shape: import the existing `app` and `service`, declare `auth_notes` + `browser_modes`, point `docs_path` at `docs/commands/onedrive.md`.

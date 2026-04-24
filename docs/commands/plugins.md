# `foxpilot plugins`

Foxpilot includes a plugin registry for discoverable built-in and project-local site workflows. YouTube and GitHub are registered as built-in plugins while keeping their existing `foxpilot youtube ...` and `foxpilot github ...` command shapes.

## Commands

```bash
foxpilot plugins list
foxpilot plugins info youtube
foxpilot plugins doctor
foxpilot plugins path
```

| Command | Purpose |
|---|---|
| `plugins list` | Show built-in and local plugins that loaded successfully. |
| `plugins info NAME` | Show help, source, docs path, modes, auth notes, and load errors for one plugin. |
| `plugins doctor` | Check plugin directories and report import failures without breaking the whole CLI. |
| `plugins path` | Print plugin search roots. |

## Search Roots

Planned discovery order:

1. Built-ins under `src/foxpilot/plugins/builtin/`.
2. Project-local plugins under `./plugins/`.
3. User-local plugins under `~/.config/foxpilot/plugins/` in a later phase.

If two plugins use the same name, the built-in plugin should win by default. A future development override may allow a local plugin to shadow a built-in.

## Current Built-In Direction

YouTube and GitHub are the first built-in plugin entries:

```bash
foxpilot youtube search "browser automation" --json
foxpilot youtube transcript --format json
foxpilot github repo owner/repo --json
foxpilot github actions owner/repo --json
```

The current built-ins reuse the existing `src/foxpilot/sites/` command apps and service modules. That keeps the command shape stable while allowing the registry and MCP layer to discover plugin metadata.

## Local Plugin Authoring

See [`plugins/README.md`](../../plugins/README.md) for the project-local plugin layout and `register()` contract.

# `foxpilot macro`

Reusable browser workflow macros stored as JSON files.

## Storage

By default, macros live in:

```text
~/.local/share/foxpilot/macros
```

Use `--dir PATH` on `list`, `show`, `run`, `export`, and `delete` to use another directory.

## Macro Format

```json
{
  "name": "search-docs",
  "description": "Open a documentation search.",
  "params": ["query"],
  "steps": [
    {
      "command": "go",
      "args": ["https://example.test/search?q={{query}}"]
    },
    {
      "command": "read",
      "args": [],
      "options": {"full": true}
    }
  ]
}
```

Supported step shapes:

- `{"command": "go", "args": ["https://example.test"]}`
- `{"argv": ["go", "https://example.test"]}`
- `{"go": "https://example.test"}`
- `["go", "https://example.test"]`
- `"status"`

Options are rendered as CLI flags. Boolean `true` becomes a flag, `false` and `null` are omitted.

## Commands

### `help`

```bash
foxpilot macro help
```

### `list`

```bash
foxpilot macro list
foxpilot macro list --json
foxpilot macro list --dir /tmp/foxpilot-macros
```

### `show <name>`

```bash
foxpilot macro show search-docs
foxpilot macro show search-docs --json
```

### `run <name> [args...]`

```bash
foxpilot macro run search-docs python
foxpilot macro run search-docs python --dry-run
foxpilot macro run search-docs python --json
```

`--dry-run` prints the commands without running them.

Macro steps inherit the global browser mode from the `macro run` invocation. For example, `foxpilot --zen macro run search-docs python` runs each rendered step with `--zen`.

### `export <name> [args...]`

Render a macro into a durable automation artifact.

```bash
foxpilot macro export search-docs python --format shell
foxpilot macro export search-docs python --format python
foxpilot macro export search-docs python --format mcp
foxpilot macro export search-docs python --format markdown
```

Formats:

| Format | Output |
|---|---|
| `shell` | Bash script that invokes `foxpilot ...` commands. |
| `python` | Python script using `subprocess.run([sys.executable, "-m", "foxpilot.cli", ...])`. |
| `mcp` | JSON recipe with tool names and argument arrays. |
| `markdown` | Human-readable runbook. |

Exported commands inherit the global browser mode prefix from the `macro export` invocation.

### `delete <name>`

```bash
foxpilot macro delete old-flow --yes
```

Without `--yes`, Foxpilot asks for confirmation.

### `record` and `edit`

```bash
foxpilot macro record new-flow
foxpilot macro edit search-docs
```

These commands are reserved and currently exit non-zero with a clear planned-feature message. Create or edit JSON files directly for now.

## Safety

Macro names are limited to letters, numbers, dots, dashes, and underscores. Relative path traversal is rejected. Macros invoke Foxpilot commands in sequence and stop on the first non-zero exit code.

# `foxpilot wait` and `foxpilot expect`

Synchronization and assertion helpers for browser automation scripts.

`wait` polls until a condition becomes true or the timeout expires. `expect` checks the current page immediately and exits non-zero on failure. Both commands print the current URL and title when available, which makes failures easier to debug in shell scripts and agent runs.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `wait help` | yes | yes | yes | yes |
| `wait text` | yes | yes | yes | yes |
| `wait selector` | yes | yes | yes | yes |
| `wait url` | yes | yes | yes | yes |
| `wait gone` | yes | yes | yes | yes |
| `wait idle` | yes | yes | yes | yes |
| `expect help` | yes | yes | yes | yes |
| `expect text` | yes | yes | yes | yes |
| `expect selector` | yes | yes | yes | yes |
| `expect url` | yes | yes | yes | yes |
| `expect title` | yes | yes | yes | yes |

## Commands

### `wait help`

Show wait command examples and options.

```bash
foxpilot wait help
```

### `wait text <text>`

Wait until visible page text contains the requested text.

```bash
foxpilot wait text "Signed in"
foxpilot wait text "Dashboard" --in main --timeout 15
foxpilot wait text "done" --case-sensitive
```

### `wait selector <selector>`

Wait until a CSS selector exists and is visible.

```bash
foxpilot wait selector "button[type=submit]"
foxpilot wait selector ".toast-success" --timeout 20 --poll 0.5
```

### `wait url <substring-or-regex>`

Wait until the current URL matches a substring. Use `--regex` for regular expressions.

```bash
foxpilot wait url "dashboard"
foxpilot wait url "/items/[0-9]+$" --regex
```

### `wait gone <selector>`

Wait until a CSS selector is absent or hidden.

```bash
foxpilot wait gone ".spinner"
foxpilot wait gone "[aria-busy=true]" --timeout 30
```

### `wait idle`

Wait until `document.readyState` is complete and recent resource activity has been quiet for the configured window.

```bash
foxpilot wait idle
foxpilot wait idle --quiet-ms 1000 --timeout 20
```

### `expect help`

Show expect command examples and options.

```bash
foxpilot expect help
```

### `expect text <text>`

Assert that visible page text contains the requested text.

```bash
foxpilot expect text "Signed in"
foxpilot expect text "Dashboard" --in main
foxpilot expect text "Done" --case-sensitive
```

### `expect selector <selector>`

Assert that a CSS selector exists and is visible.

```bash
foxpilot expect selector "button[type=submit]"
```

### `expect url <substring-or-regex>`

Assert that the current URL matches a substring. Use `--regex` for regular expressions.

```bash
foxpilot expect url "dashboard"
foxpilot expect url "/items/[0-9]+$" --regex
```

### `expect title <substring-or-regex>`

Assert that the current page title matches a substring. Use `--regex` for regular expressions.

```bash
foxpilot expect title "Settings"
foxpilot expect title "^Issue #[0-9]+" --regex
```

## Failure Modes

- Text not found: use `foxpilot read` or `foxpilot html` to inspect what the browser can see.
- Selector not found: verify the CSS selector with `foxpilot js 'return document.querySelector(...)'`.
- URL or title mismatch: retry with `--regex` when the dynamic part of the value changes.
- Page never idle: wait for a specific selector or text instead of relying on network quietness.

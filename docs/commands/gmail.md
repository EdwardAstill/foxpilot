# `foxpilot gmail`

Gmail (`mail.google.com`) helpers: open labels, list / search / read messages, compose drafts, and apply thread actions (`archive`, `star`, `delete`).

## Status

`foxpilot gmail` is a built-in Typer command branch backed by `src/foxpilot/sites/gmail.py` and `src/foxpilot/sites/gmail_service.py`, registered as the built-in `gmail` plugin under `src/foxpilot/plugins/builtin/gmail/`.

The browser layer is best-effort. Gmail uses dynamic class names heavily, so DOM selectors live in named `_find_*` helpers in `gmail_service.py` and are expected to drift over time. URL helpers (`build_gmail_search_url`, `label_url`) and formatters are stable and unit-tested.

## Authentication

Sign into Gmail once in the foxpilot browser. Default mode is the **claude** profile:

```bash
foxpilot login https://mail.google.com
```

After the login window auto-hides, cookies persist in the automation profile across runs. To reuse an existing Zen session instead, pass `--zen`:

```bash
foxpilot --zen gmail list
```

The Gmail Lite UI is intentionally **not** supported; selectors target the standard web interface only.

## Mode Support

| Command   | claude | visible | zen | headless     |
|-----------|-------:|--------:|----:|-------------:|
| help      |    yes |     yes | yes |          yes |
| open      |    yes |     yes | yes | best effort  |
| list      |    yes |     yes | yes | best effort  |
| search    |    yes |     yes | yes | best effort  |
| read      |    yes |     yes | yes | best effort  |
| compose   |    yes |     yes | yes |           no |
| send      |    yes |     yes | yes |           no |
| star      |    yes |     yes | yes | best effort  |
| archive   |    yes |     yes | yes | best effort  |
| delete    |    yes |     yes | yes | best effort  |

`claude` is the default. `--visible` brings the claude window onto the active workspace. `--zen` reuses your real Zen browser session.

## Confirmation Gates

| Command   | Gated? | How to bypass        |
|-----------|--------|----------------------|
| open / list / search / read / compose / star / archive | no | n/a |
| `send`    | yes    | `--yes` or answer `y` to the interactive prompt |
| `delete`  | yes    | `--yes` or answer `y` to the interactive prompt |

## Commands

### `foxpilot gmail help`
Show usage examples.

### `foxpilot gmail open [label]`
Navigate to the Gmail inbox or a label.

```bash
foxpilot gmail open                # inbox
foxpilot gmail open Starred
foxpilot gmail open Important
foxpilot gmail open "Work/Reports"  # user label
```

System labels recognised: `inbox`, `starred`, `snoozed`, `important`, `sent`, `drafts`, `scheduled`, `all`, `spam`, `trash`, `chats`. Anything else is treated as a user label.

### `foxpilot gmail list [--label X] [--limit N] [--unread] [--json]`
List visible messages in the current Gmail view.

```bash
foxpilot gmail list --limit 20
foxpilot gmail list --label Starred --unread --json
```

### `foxpilot gmail search "<query>" [--limit N] [--json]`
Run a Gmail search via the `#search/<query>` URL fragment.

```bash
foxpilot gmail search "from:alice has:attachment"
foxpilot gmail search "in:inbox is:unread newer_than:2d"
```

### `foxpilot gmail read <id-or-query> [--json]`
Open a thread and dump headers + body. The argument may be a Gmail thread id or a search string that uniquely selects a thread.

### `foxpilot gmail compose --to <addr> [--subject S] [--body B] [--json]`
Open the compose pane and fill `To`, `Subject`, and `Body`.

```bash
foxpilot gmail compose --to alice@example.com --subject "Hi" --body "Quick note"
```

### `foxpilot gmail send [--yes] [--json]`
Send the currently open compose draft. Requires `--yes` or an interactive `y` confirmation.

### `foxpilot gmail star <id> [--json]`
Star a thread.

### `foxpilot gmail archive <id> [--json]`
Archive a thread (move out of inbox; reversible — no confirmation gate).

### `foxpilot gmail delete <id> [--yes] [--json]`
Move a thread to Trash. Requires `--yes` or an interactive `y` confirmation.

## JSON Shapes

`open`:
```json
{ "title": "Inbox - ...", "url": "https://mail.google.com/...", "label": "inbox" }
```

`list` / `search` (each item):
```json
{
  "id": "186a...",
  "from": "Alice <alice@example.com>",
  "subject": "Quarterly review",
  "snippet": "Hi team — attaching the Q1 deck...",
  "age": "2 days",
  "unread": true,
  "aria": "...",
  "text": "..."
}
```

`read`:
```json
{
  "subject": "Quarterly review",
  "from": "Alice <alice@example.com>",
  "date": "Apr 23, 2026, 10:14 AM",
  "headers": { "from": "...", "to": "...", "date": "...", "subject": "..." },
  "body": "Hi team...",
  "url": "https://mail.google.com/.../thread-id"
}
```

`compose`:
```json
{ "state": "filled", "to": "alice@example.com", "subject": "Hi", "body": "..." }
```

`send` / `star` / `archive` / `delete`:
```json
{ "action": "send", "target": "compose", "result": "clicked" }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `could not find Gmail Compose button` | Gmail still loading; wrong account view | wait + retry; `foxpilot gmail open` first |
| `compose field not found` | UI changed | tune `_find_compose_*` helpers in `gmail_service.py` |
| `could not find Send button in compose pane` | Draft not focused | re-run `compose` then `send` |
| Empty `list` output | Loading or pinned to `Lite`; not signed in | confirm with `foxpilot gmail open`; check session via `foxpilot --visible gmail open` |
| Sign-in redirect | Session expired | run `foxpilot login https://mail.google.com` again |

All errors emit on stderr as `error: <message>` plus optional `url:`, `reason:`, `next:` lines, and exit non-zero (matches the youtube / excel pattern).

## Limitations

- Gmail Lite UI is not supported.
- Bulk operations (multi-select archive/delete) are not yet exposed.
- Attachments are not yet downloaded — `read` returns the body text only.
- Selectors are best-effort; expect drift. Tune `_find_message_rows`, `_find_compose_*`, `_find_thread_action_button` in `gmail_service.py` when Gmail changes its DOM.
- OAuth and the official Gmail API are intentionally out of scope; this plugin drives the web UI.

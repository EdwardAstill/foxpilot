# `foxpilot teams`

Microsoft Teams web (`teams.microsoft.com`) helpers: open Teams sections, list chats and joined teams, read messages, and post into chats or channels.

## Status

`foxpilot teams` is a built-in Typer command branch backed by `src/foxpilot/sites/teams.py` and `src/foxpilot/sites/teams_service.py`, registered as the built-in `teams` plugin under `src/foxpilot/plugins/builtin/teams/`.

## Authentication

Default mode is `--zen` so the plugin reuses your real Zen browser's existing Microsoft 365 session (the most reliable path for UWA student M365). For claude-mode, sign in once:

```bash
foxpilot login https://teams.microsoft.com/
```

Cookie state then persists across runs in the claude profile.

Teams web sometimes embeds content inside `iframe#embedded-page-container`. The service layer's `_switch_to_main_iframe(driver)` helper switches into that iframe before scraping; if Teams stops embedding the iframe, helpers gracefully fall back to top-level DOM.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes (after login) | yes | **default** | no (SSO) |
| `chats` | yes | yes | yes | no |
| `chat` | yes | yes | yes | no |
| `messages` | yes | yes | yes | no |
| `post` | yes | yes | yes | no |
| `teams` | yes | yes | yes | no |
| `channel` | yes | yes | yes | no |

## Commands

### `foxpilot teams help`
Show command examples.

### `foxpilot teams open [section] [--json]`
Open Teams at a high-level section. Sections: `chat`, `teams`, `calendar`, `calls`, `activity`. A full Teams URL is also accepted.

```bash
foxpilot teams open
foxpilot teams open calendar
foxpilot teams open https://teams.microsoft.com/_#/conversations/...
```

### `foxpilot teams chats [--limit N] [--json]`
List recent chats with peer name, last-message snippet, timestamp, and unread flag.

### `foxpilot teams chat <name> [--json]`
Open a 1:1 or group chat by visible name.

### `foxpilot teams messages [--chat NAME] [--limit N] [--json]`
List recent messages in the active chat. With `--chat`, opens that chat first.

### `foxpilot teams post <chat-or-channel> "<message>" --yes [--json]`
Post a message. **Requires `--yes`** — without it the command refuses with a confirmation hint.

```bash
foxpilot teams post "Alice" "ack, on my way" --yes
```

### `foxpilot teams teams [--json]`
List joined teams with their channels (best effort).

### `foxpilot teams channel <team> <channel> [--json]`
Navigate to the Teams pane and open `<channel>` under `<team>`.

## JSON Shapes

`open`:
```json
{ "title": "Chat | Microsoft Teams", "url": "https://...", "section": "chat" }
```

`chats`:
```json
[ { "name": "Alice", "snippet": "see you then", "timestamp": "10:42", "unread": false } ]
```

`messages`:
```json
[ { "author": "Alice", "body": "hi", "timestamp": "10:42" } ]
```

`teams`:
```json
[ { "name": "Project X", "channels": ["General", "Random"] } ]
```

`post`:
```json
{ "status": "posted", "target": "Alice", "message": "hi", "url": "https://..." }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `post requires --yes confirmation` | Safety gate | re-run with `--yes` |
| `no visible Teams chat matching '<name>'` | Wrong name or chat off-screen | run `foxpilot teams chats` to see visible names |
| `could not find Teams compose box` | Chat not open / loading | retry with `--visible`, ensure chat opened first |
| SSO redirect | Session expired | `foxpilot --zen teams open chat` and complete sign-in |

## Limitations

- Selectors are best-effort against Teams' shifting `data-tid` markup; tune `_find_compose_box`, `extract_chats`, `extract_messages`, and `extract_teams` in `teams_service.py` if Teams ships UI changes.
- Headless mode is not supported (M365 SSO + WebDriver detection).
- No call control, screen share, or meeting join surfaces yet.
- `post` posts only into chats/channels reachable from the existing Teams left rail; it does not start new conversations.

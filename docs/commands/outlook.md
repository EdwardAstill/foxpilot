# `foxpilot outlook`

Microsoft 365 Outlook on the web (`outlook.office.com/mail/` and `/calendar/`) helpers: open folders, list and read messages, search, compose, send, and view calendar events.

## Status

`foxpilot outlook` is a built-in Typer command branch backed by `src/foxpilot/sites/outlook.py` and `src/foxpilot/sites/outlook_service.py`, registered as the built-in `outlook` plugin under `src/foxpilot/plugins/builtin/outlook/`.

## Authentication

UWA M365 students will most likely already have an active Outlook session in their Zen browser. The default recommended mode is therefore `--zen`:

```bash
foxpilot --zen outlook open
```

For the dedicated `claude` profile:

```bash
foxpilot login https://outlook.office.com/mail/
```

Outlook (Office 365) goes through SSO; headless modes are not supported.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes | yes | **default** | no (SSO) |
| `list` | yes | yes | yes | no |
| `read` | yes | yes | yes | no |
| `search` | yes | yes | yes | no |
| `compose` | yes | yes | yes | no |
| `send` | yes | yes | yes | no |
| `calendar` | yes | yes | yes | no |

## Commands

### `foxpilot outlook help`
Shows command examples.

### `foxpilot outlook open [folder]`
Open Outlook on the web at a folder. Default `inbox`.

Folders: `inbox`, `sent`, `drafts`, `archive`. A full Outlook URL also works.

```bash
foxpilot outlook open
foxpilot outlook open sent
foxpilot outlook open drafts
```

### `foxpilot outlook list [--limit N] [--unread] [--folder F] [--json]`
List visible message rows in a folder. `--unread` filters to messages whose row aria-label flags as unread.

### `foxpilot outlook read <subject-or-search>`
Run a search for the term and open the first matching message in the Reading pane, returning subject, sender, and body text.

### `foxpilot outlook search "<query>" [--folder F] [--limit N] [--json]`
Run an Outlook server-side search inside a folder.

### `foxpilot outlook compose --to ... [--cc ...] [--bcc ...] [--subject ...] [--body ...]`
Open the compose pane and fill in the fields. Does **not** send; use `send --yes` to actually send.

### `foxpilot outlook send --yes`
Send the currently open compose draft. The `--yes` flag is **required**; running `send` without it exits with an error explaining the destructive-action gate.

### `foxpilot outlook calendar [--view V] [--from D] [--to D] [--limit N] [--json]`
Open Outlook calendar at a view (`day` / `week` / `workweek` / `month`) and list visible events.

## JSON Shapes

`open`:
```json
{ "title": "...", "url": "https://outlook.office.com/mail/inbox", "folder": "inbox" }
```

`list` / `search`:
```json
[
  { "subject": "...", "from": "...", "snippet": "...", "received": "", "unread": false }
]
```

`read`:
```json
{ "subject": "...", "from": "...", "body": "...", "url": "https://..." }
```

`compose`:
```json
{ "status": "drafted", "to": ["a@b.com"], "cc": [], "bcc": [], "subject": "...", "url": "..." }
```

`send`:
```json
{ "status": "sent", "url": "https://outlook.office.com/mail/inbox" }
```

`calendar`:
```json
{ "view": "week", "from": null, "to": null, "url": "...", "events": [
  { "title": "...", "when": "...", "location": "", "organizer": "" }
] }
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `browser unavailable` | Foxpilot cannot launch the browser | run `foxpilot doctor` |
| `not an Outlook URL` | URL passed to `open` is for a different host | use a folder name or a real outlook.office.com URL |
| `send requires explicit confirmation` | `send` invoked without `--yes` | re-run with `--yes` to actually send |
| `no matching Outlook message` | Search returned zero rows | run `foxpilot outlook search ...` to inspect |
| `could not find Outlook 'New mail' button` | Compose surface still loading or markup changed | retry with `--visible` and verify selectors |
| SSO redirect to `login.microsoftonline.com` | Session expired | `foxpilot --zen outlook open` and finish SSO, or re-run `foxpilot login` for the claude profile |

## Limitations

- Selectors target current Outlook on the web markup (`div[role='option']` for message rows, `[aria-label='Reading pane']` for the body). If Microsoft changes the markup, retune helpers in `outlook.py` and `outlook_service.py`.
- Calendar view is read-only here; create/edit flows are intentionally out of scope. For Google Calendar, see `foxpilot gcal`.
- `read` opens the first search hit, not by stable id; ambiguous queries may pick the wrong message.
- Attachment download is not implemented yet — see `foxpilot onedrive download` for a downloads pattern to mirror.
- Confirmation gate covers `send` only; `compose` deliberately drafts without sending.

# `foxpilot gcal`

Google Calendar (`calendar.google.com`) helpers: open views, list events, open event detail panels, and pre-fill the create-event dialog.

## Status

`foxpilot gcal` is a built-in Typer command branch backed by `src/foxpilot/sites/gcal.py` and `src/foxpilot/sites/gcal_service.py`, registered as the built-in `gcal` plugin under `src/foxpilot/plugins/builtin/gcal/`.

## Authentication

Sign into `https://calendar.google.com/` once in the foxpilot browser. Session cookies persist in the automation profile across runs.

```bash
foxpilot login https://calendar.google.com/
```

`--zen` reuses your real Zen browser session if you are already signed-in there.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | **default** | yes | yes | best effort |
| `today` | **default** | yes | yes | best effort |
| `events` | **default** | yes | yes | best effort |
| `event` | yes | yes | yes | best effort |
| `create` | yes | yes | yes | unlikely |

Default browser mode is **`claude`**.

## Commands

### `foxpilot gcal help`
Show command examples.

### `foxpilot gcal open [VIEW]`
Open Google Calendar. Optional `VIEW` is one of `day`, `week`, `month`, `agenda`. Without an argument, opens the user's default landing view.

```bash
foxpilot gcal open
foxpilot gcal open week
foxpilot gcal open month --on 2026-05-01
foxpilot gcal open day --on +1d
```

### `foxpilot gcal today [--json]`
Open today's day view and list today's visible events.

### `foxpilot gcal events [--from D] [--to D] [--view V] [--json]`
List events between two dates. Date inputs accept `YYYY-MM-DD`, `YYYYMMDD`, `today`, `tomorrow`, `yesterday`, or relative offsets like `+7d`, `-3d`.

Defaults: `--from today`, `--to +7d`, `--view agenda`.

```bash
foxpilot gcal events --from today --to +7d
foxpilot gcal events --from 2026-04-25 --to 2026-04-30 --json
```

URL form: `https://calendar.google.com/calendar/u/0/r/agenda?dates=YYYYMMDD/YYYYMMDD`.

### `foxpilot gcal event <TITLE-OR-ID> [--json]`
Open the first event chip on the current view whose aria-label contains the target text, then dump the detail panel.

```bash
foxpilot gcal event "Standup"
```

### `foxpilot gcal create --title T --when W [--duration M] [--invitees ...] [--location L] [--details D] [--yes] [--json]`
Open the Google Calendar create-event dialog with the title, time, duration, invitees, location and description prefilled via Calendar's `eventedit` URL.

By default the dialog opens prefilled but **is not saved** — you can review the dialog and click Save yourself. Pass `--yes` to confirm and have foxpilot click Save for you.

```bash
foxpilot gcal create --title "Lunch with Alex" --when "2026-04-25 12:30" --duration 45
foxpilot gcal create --title "Sync" --when "2026-04-25 14:00" --invitees alice@example.com,bob@example.com --yes
```

`--when` accepts `YYYY-MM-DD HH:MM`, `YYYY-MM-DDTHH:MM`, or a bare date (defaults to 09:00).

## JSON Shapes

`open`:
```json
{ "title": "Google Calendar", "url": "https://calendar.google.com/...", "view": "week" }
```

`events` / `today`:
```json
[ { "title": "Standup", "when": "09:00", "calendar": "Work", "location": "" } ]
```

`event`:
```json
{ "title": "Standup", "when": "Today, 09:00 - 09:15", "location": "", "description": "...", "url": "https://calendar.google.com/..." }
```

`create`:
```json
{
  "title": "Lunch",
  "when": "2026-04-25 12:30",
  "duration_minutes": 45,
  "invitees": ["alice@example.com"],
  "location": "",
  "details": "",
  "url": "https://calendar.google.com/calendar/render?...",
  "saved": false,
  "confirmed": false
}
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `unknown view: ...` | Bad view argument | use one of `day`, `week`, `month`, `agenda` |
| `invalid date: ...` | Bad `--from` / `--to` | use `YYYY-MM-DD`, `today`, `+7d` |
| `no event chip matched ...` | Event not on current view | open the right week/month with `foxpilot gcal open week --on YYYY-MM-DD` then retry |
| `invalid datetime: ...` | Bad `--when` | use `YYYY-MM-DD HH:MM` |
| `saved: no` after `--yes` | Save button selectors changed | inspect dialog, update `_click_save_button` xpaths in `gcal.py` |

## Limitations

- Event listing is a best-effort scrape of visible event chips; it depends on Google Calendar's DOM markup and may need selector tuning over time.
- Recurring-event editing (this/all) is not implemented — `create --yes` only handles one-off events.
- Calendars sharing, reminders, and notification settings are not exposed.
- The `event` command opens the *first* matching chip — disambiguation by id is not yet supported.
- Single-account only — paths use `/u/0/`.

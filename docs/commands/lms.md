# `foxpilot lms`

UWA Blackboard Ultra (`lms.uwa.edu.au`) helpers: navigate sections, list stream items, courses, assignments, grades, and announcements.

## Status

`foxpilot lms` is a built-in Typer command branch backed by `src/foxpilot/sites/lms.py` and `src/foxpilot/sites/lms_service.py`, registered as the built-in `lms` plugin under `src/foxpilot/plugins/builtin/lms/`.

## Why this works the way it does

Blackboard Ultra is a React-rendered SPA. Class names are unstable. The plugin targets the most stable hooks available — `data-testid` attributes, `[role='grid']` and `[role='listitem']`, and `aria-label` text — and centralises every fragile selector in a private `_find_*` helper inside `lms_service.py`. Re-tuning the plugin when Blackboard ships a UI change is a one-edit operation per surface.

## Authentication

Default mode is **`--zen`**, because most UWA students are already signed into LMS in their Zen browser. Pheme SSO will not run cleanly in headless.

For the dedicated `claude` profile:

```bash
foxpilot login https://lms.uwa.edu.au/ultra/stream
```

Or import cookies from another browser:

```bash
foxpilot import-cookies --domain lms.uwa.edu.au --include-storage
```

If a command lands on `auth.uwa.edu.au` or `sso.uwa.edu.au`, the plugin reports `error: session expired` with a `next:` hint to re-run with `--zen` and complete SSO.

## Mode Support

| Command | claude | visible | zen | headless |
|---|---:|---:|---:|---:|
| `help` | yes | yes | yes | yes |
| `open` | yes (after login) | yes | **default** | no (SSO) |
| `stream` | yes (after login) | yes | **default** | no |
| `courses` | yes (after login) | yes | **default** | no |
| `course` | yes (after login) | yes | **default** | no |
| `assignments` | yes (after login) | yes | **default** | no |
| `grades` | yes (after login) | yes | **default** | no |
| `announcements` | yes (after login) | yes | **default** | no |
| `download` | yes (after login) | yes | **default** | no |

## Commands

### `foxpilot lms help`
Print branch usage and examples.

### `foxpilot lms open [section]`
Navigate to a section. `section` is one of `stream` (default), `courses`, `calendar`, `grades`, `messages`.

```bash
foxpilot lms open
foxpilot lms open courses
foxpilot lms open grades --json
```

### `foxpilot lms stream [--limit N] [--json]`
List recent stream items with title, course, kind, timestamp, and link.

### `foxpilot lms courses [--json]`
List enrolled courses with title, code, term, and link.

### `foxpilot lms course <id-or-name>`
Open a course landing page. Match is case-insensitive substring against title or code.

```bash
foxpilot lms course "GENG2000"
foxpilot lms course "Engineering Mathematics"
```

### `foxpilot lms assignments [--course X] [--due-soon] [--json]`
List assignment items. `--course` filters by course name/code substring. `--due-soon` keeps only rows that have a due date string.

### `foxpilot lms grades [--course X] [--json]`
List grade items: name, score, weight, posted-at.

### `foxpilot lms announcements [--limit N] [--course X] [--json]`
List announcements with course and posted-at.

### `foxpilot lms download <assignment> [--to DIR]`
Open the matching assignment and prepare a save target. Returns the assignment URL plus the target directory; attachment download itself is best-effort and may need site-specific tuning.

## JSON Shapes

`open`:
```json
{ "title": "Stream | Blackboard Learn", "url": "https://lms.uwa.edu.au/ultra/stream", "section": "stream" }
```

`stream` (list):
```json
[
  {
    "title": "Lab 3 due Friday",
    "course": "GENG2000",
    "kind": "assignment",
    "timestamp": "2 hours ago",
    "url": "https://lms.uwa.edu.au/..."
  }
]
```

`courses` (list):
```json
[
  { "title": "Engineering Mathematics", "code": "GENG2000", "term": "S1 2026", "url": "https://..." }
]
```

`assignments` (list):
```json
[
  { "name": "Lab 3", "course": "GENG2000", "due": "Fri 5pm", "status": "submitted" }
]
```

`grades` (list):
```json
[
  { "name": "Quiz 1", "score": "8/10", "weight": "5%", "posted_at": "2 days ago" }
]
```

`announcements` (list):
```json
[
  { "title": "Welcome to GENG2000", "course": "GENG2000", "posted_at": "1 week ago" }
]
```

## Failure Modes & Next Actions

| Failure | Likely cause | Next step |
|---|---|---|
| `error: session expired` (URL on `auth.uwa.edu.au`) | Pheme SSO redirect | `foxpilot --zen lms open stream` and complete SSO interactively |
| Empty `stream` / `courses` / `grades` list | Page still rendering or selectors drifted | retry once; if persistent, run `foxpilot --visible lms open <section>` and update `_find_*` helpers in `lms_service.py` |
| `error: invalid lms section` | Bad section name | use `stream`, `courses`, `calendar`, `grades`, or `messages` |
| `error: could not find course matching ...` | No substring match | run `foxpilot lms courses` to see exact titles, then retry |
| `error: invalid course id-or-name` / `invalid assignment name` | Disallowed characters | stick to letters, digits, spaces, and common punctuation |

## Limitations

- Bulk attachment download is a stub: `download` opens the assignment page and prepares a target dir but does not yet stream files. Mirror onedrive's `wait-download` snapshot+poll pattern when adding it.
- Calendar parsing is not yet implemented; `open calendar` only navigates.
- Messages are not parsed; `open messages` only navigates.
- Selectors live in `_find_stream_items`, `_find_course_cards`, `_find_assignment_rows`, `_find_grade_rows`, `_find_announcement_rows` in `lms_service.py` — update them in one place when Ultra changes its markup.
- Headless is unsupported: UWA Pheme SSO needs a real, interactive session.
